package com.exem.inspector.screen.script;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import javax.sql.DataSource;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Component;

import com.exem.inspector.common.db.DbType;
import com.exem.inspector.config.ServiceConfig;

/**
 * 원본 {@code _run_oracle_readonly} / {@code _run_pg_readonly} 와 1:1 동등한 JDBC 실행기.
 *
 * <ul>
 *   <li>리포지토리 미설정 → DataSource 빈 미등록(부팅 허용) → 실행 시 IllegalStateException.</li>
 *   <li>Oracle: ALTER SESSION NLS_DATE_FORMAT → SET TRANSACTION READ ONLY → execute → rollback.</li>
 *   <li>PG: SET statement_timeout='30s' →(search_path TO ...) → SET TRANSACTION READ ONLY →
 *       PL/pgSQL 함수 본문은 split 해 순차 실행 → 마지막 ResultSet 사용 → rollback.</li>
 *   <li>fetchmany(max+1) 동등: ResultSet 의 (maxRows+1) 번째 행이 있으면 truncated 플래그 on.</li>
 * </ul>
 */
@Component
public class JdbcScriptExecutor implements ScriptExecutor {

    /** sqlplus directive 라인 — 원본 _strip_oracle_directives 와 동일 패턴. */
    private static final Pattern ORACLE_DIRECTIVE_LINE = Pattern.compile(
            "^\\s*(SET|COLUMN|WHENEVER|PROMPT|SPOOL|TTITLE|BTITLE)\\b.*$|^\\s*EXIT\\s*;?\\s*$",
            Pattern.CASE_INSENSITIVE);

    /** PG plpgsql 함수 본문 종료 — 원본 _split_pg_stmts 와 동일 패턴. */
    private static final Pattern PG_PLPGSQL_END = Pattern.compile(
            "\\$\\$\\s+LANGUAGE\\s+plpgsql\\s*;",
            Pattern.CASE_INSENSITIVE | Pattern.DOTALL);

    /** psql 백슬래시 메타 명령 라인(원본 _strip_pg_directives). */
    private static final Pattern PG_BACKSLASH_DIRECTIVE = Pattern.compile("^\\s*\\\\.*$");

    /** PG schema 목록 SQL — 원본 api_script_schemas 본문 그대로. */
    private static final String PG_SCHEMA_SQL =
            "SELECT nspname FROM pg_namespace "
            + "WHERE nspname NOT IN ('pg_catalog','information_schema','pg_toast','public') "
            + "AND nspname NOT LIKE 'pg_temp%' AND nspname NOT LIKE 'pg_toast_temp%' "
            + "ORDER BY nspname";

    /** statement_timeout(원본 30s) / connect timeout(원본 30s) 동등. */
    private static final int QUERY_TIMEOUT_SECONDS = 30;
    private static final String PG_STATEMENT_TIMEOUT = "30s";

    private final ObjectProvider<DataSource> dataSourceProvider;
    private final ServiceConfig serviceConfig;

    public JdbcScriptExecutor(ObjectProvider<DataSource> dataSourceProvider, ServiceConfig serviceConfig) {
        this.dataSourceProvider = dataSourceProvider;
        this.serviceConfig = serviceConfig;
    }

    @Override
    public DbType currentDbType() {
        return DbType.fromConfigValue(serviceConfig.repository().dbType());
    }

    @Override
    public List<String> listPgSchemas() throws SQLException {
        DbType dbType = currentDbType();
        if (dbType != DbType.POSTGRESQL) {
            return Collections.emptyList();
        }
        DataSource ds = requireDataSource();
        List<String> out = new ArrayList<>();
        try (Connection conn = ds.getConnection();
             PreparedStatement ps = conn.prepareStatement(PG_SCHEMA_SQL);
             ResultSet rs = ps.executeQuery()) {
            ps.setQueryTimeout(QUERY_TIMEOUT_SECONDS);
            while (rs.next()) {
                String s = rs.getString(1);
                if (s != null && !s.trim().isEmpty()) out.add(s.trim());
            }
        }
        return out;
    }

    @Override
    public Result run(String sql, String searchPath, int maxRows) throws SQLException {
        DbType dbType = currentDbType();
        DataSource ds = requireDataSource();
        if (dbType == DbType.ORACLE) {
            return runOracle(ds, sql, maxRows);
        }
        return runPg(ds, sql, searchPath, maxRows);
    }

    private DataSource requireDataSource() {
        DataSource ds = dataSourceProvider.getIfAvailable();
        if (ds == null) {
            throw new IllegalStateException("리포지토리가 설정되지 않았습니다(service_config.json 확인).");
        }
        return ds;
    }

    // ── Oracle ───────────────────────────────────────────────────────────────

    private Result runOracle(DataSource ds, String sqlBody, int maxRows) throws SQLException {
        Connection conn = null;
        try {
            conn = ds.getConnection();
            conn.setAutoCommit(false);
            try (Statement st = conn.createStatement()) {
                st.setQueryTimeout(QUERY_TIMEOUT_SECONDS);
                st.execute("ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD HH24:MI:SS'");
                st.execute("SET TRANSACTION READ ONLY");
            }
            String cleaned = trimTrailingSemicolons(stripOracleDirectives(sqlBody).trim()).trim();
            try (Statement st = conn.createStatement()) {
                st.setQueryTimeout(QUERY_TIMEOUT_SECONDS);
                if (maxRows > 0) {
                    st.setFetchSize(Math.min(maxRows + 1, 1000));
                }
                boolean hasRs = st.execute(cleaned);
                if (!hasRs) {
                    throw new SQLException("Only SELECT statements are allowed.");
                }
                try (ResultSet rs = st.getResultSet()) {
                    Result r = readCapped(rs, maxRows);
                    try { conn.rollback(); } catch (SQLException ignore) { /* best-effort */ }
                    return r;
                }
            }
        } catch (SQLException e) {
            try { if (conn != null) conn.rollback(); } catch (SQLException ignore) { /* best-effort */ }
            String msg = e.getMessage() == null ? "" : e.getMessage();
            if (msg.contains("ORA-01456") || msg.contains("ORA-01453")) {
                throw new SQLException("Only SELECT statements are allowed (read-only transaction).");
            }
            if (msg.startsWith("Only SELECT")) {
                throw e;
            }
            throw new SQLException("Oracle error: " + msg);
        } finally {
            close(conn);
        }
    }

    /** 원본 _strip_oracle_directives — sqlplus 라인 명령 제거. */
    static String stripOracleDirectives(String sql) {
        if (sql == null) return "";
        StringBuilder out = new StringBuilder();
        boolean first = true;
        for (String line : sql.split("\n", -1)) {
            if (ORACLE_DIRECTIVE_LINE.matcher(line).matches()) continue;
            if (!first) out.append("\n");
            out.append(line);
            first = false;
        }
        return out.toString();
    }

    /** 원본 {@code rstrip(";").strip()} 와 동등(말단 ; 반복 제거). */
    static String trimTrailingSemicolons(String sql) {
        int end = sql.length();
        while (end > 0 && sql.charAt(end - 1) == ';') end--;
        return sql.substring(0, end);
    }

    // ── PG ───────────────────────────────────────────────────────────────────

    private Result runPg(DataSource ds, String sqlBody, String searchPath, int maxRows) throws SQLException {
        Connection conn = null;
        try {
            conn = ds.getConnection();
            conn.setAutoCommit(false);
            try (Statement st = conn.createStatement()) {
                st.setQueryTimeout(QUERY_TIMEOUT_SECONDS);
                st.execute("SET statement_timeout = '" + PG_STATEMENT_TIMEOUT + "'");
                if (searchPath != null && !searchPath.isEmpty()) {
                    // ScriptValidator.sanitizeSchema 로 [A-Za-z0-9_]+ 만 통과한 값.
                    st.execute("SET search_path TO " + searchPath + ", public");
                }
                st.execute("SET TRANSACTION READ ONLY");
            }

            Result last = new Result(Collections.emptyList(), Collections.emptyList(), false);
            for (String stmt : splitPgStatements(sqlBody)) {
                if (stmt == null || stmt.trim().isEmpty()) continue;
                try (Statement st = conn.createStatement()) {
                    st.setQueryTimeout(QUERY_TIMEOUT_SECONDS);
                    if (maxRows > 0) {
                        st.setFetchSize(Math.min(maxRows + 1, 1000));
                    }
                    boolean hasRs = st.execute(stmt);
                    if (hasRs) {
                        try (ResultSet rs = st.getResultSet()) {
                            last = readCapped(rs, maxRows);
                        }
                    }
                }
            }
            try { conn.rollback(); } catch (SQLException ignore) { /* best-effort */ }
            return last;
        } catch (SQLException e) {
            try { if (conn != null) conn.rollback(); } catch (SQLException ignore) { /* best-effort */ }
            String msg = e.getMessage() == null ? "" : e.getMessage();
            if (msg.toLowerCase().contains("read-only transaction")) {
                throw new SQLException("Only SELECT statements are allowed (read-only transaction).");
            }
            throw new SQLException("PG error: " + msg);
        } finally {
            close(conn);
        }
    }

    /** 원본 _strip_pg_directives — 앞쪽 공백 후 백슬래시(\\)로 시작하는 라인을 모두 제거. */
    static String stripPgDirectives(String sql) {
        if (sql == null) return "";
        StringBuilder out = new StringBuilder();
        boolean first = true;
        for (String line : sql.split("\n", -1)) {
            if (PG_BACKSLASH_DIRECTIVE.matcher(line).matches()) continue;
            if (!first) out.append("\n");
            out.append(line);
            first = false;
        }
        return out.toString();
    }

    /**
     * 원본 _split_pg_stmts — psql 메타 명령 제거 후 PL/pgSQL 함수 본문이 있으면 분리한다.
     * 일반 SELECT 만 들어오는 경우 단일 statement 그대로 반환.
     */
    static List<String> splitPgStatements(String sql) {
        String stripped = stripPgDirectives(sql);
        if (!stripped.contains("$$")) {
            return Collections.singletonList(stripped.trim());
        }
        Matcher m = PG_PLPGSQL_END.matcher(stripped);
        if (m.find()) {
            String func = stripped.substring(0, m.end()).trim();
            String rest = stripped.substring(m.end()).trim();
            if (rest.isEmpty()) {
                return Collections.singletonList(func);
            }
            return Arrays.asList(func, rest);
        }
        return Collections.singletonList(stripped.trim());
    }

    // ── Common ───────────────────────────────────────────────────────────────

    /**
     * ResultSet 을 maxRows+1 까지 읽어 truncated 판정 후 maxRows 행만 반환한다.
     *
     * <p>Date/Timestamp/Time 은 getString 으로 받아 NLS_DATE_FORMAT/JDBC 기본 ISO 문자열로 응답한다
     * (원본 _cursor_to_table_text 가 str(val) 로 평면화하던 것과 동등).
     */
    private Result readCapped(ResultSet rs, int maxRows) throws SQLException {
        ResultSetMetaData md = rs.getMetaData();
        int n = md.getColumnCount();
        List<ColumnInfo> cols = new ArrayList<>(n);
        for (int i = 1; i <= n; i++) {
            cols.add(new ColumnInfo(md.getColumnLabel(i), md.getColumnType(i)));
        }
        List<Map<String, Object>> rows = new ArrayList<>();
        boolean truncated = false;
        while (rs.next()) {
            if (maxRows > 0 && rows.size() >= maxRows) {
                truncated = true;
                break;
            }
            Map<String, Object> row = new LinkedHashMap<>();
            for (int i = 1; i <= n; i++) {
                Object v = rs.getObject(i);
                if (v instanceof java.sql.Timestamp || v instanceof java.sql.Date || v instanceof java.sql.Time) {
                    v = rs.getString(i);
                }
                row.put(cols.get(i - 1).label, v);
            }
            rows.add(row);
        }
        return new Result(cols, rows, truncated);
    }

    private static void close(Connection conn) {
        if (conn == null) return;
        try { conn.close(); } catch (SQLException ignore) { /* best-effort */ }
    }
}
