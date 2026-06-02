package com.exem.inspector.screen.script;

import java.util.Collections;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.exem.inspector.common.db.DbType;
import com.exem.inspector.common.web.screen.ColumnDef;
import com.exem.inspector.common.web.screen.ColumnRole;
import com.exem.inspector.common.web.screen.ColumnType;
import com.exem.inspector.common.web.screen.ScreenResponse;

/**
 * Script Manager 화면 서비스. 검증·실행·표준응답 조립을 담당한다.
 *
 * <p>원본 api_script_run / api_script_schemas 와 동등(HTML 대신 표준 JSON).
 * HTML 렌더는 프런트 2층 ScreenTable 이 일관 처리 → 백엔드는 컬럼/행만 반환한다(I절 공통화).
 */
@Service
public class ScriptService {

    private static final Logger log = LoggerFactory.getLogger(ScriptService.class);

    /** 결과 행 상한 — 원본 MAX_SCRIPT_ROWS 동일. 초과 시 truncated 배너로 안내. */
    public static final int MAX_SCRIPT_ROWS = 1000;

    private final ScriptExecutor executor;

    public ScriptService(ScriptExecutor executor) {
        this.executor = executor;
    }

    /** PG schemas 목록. 오류 시 빈 리스트(원본 api_script_schemas 동일). */
    public ScriptSchemasResult schemas() {
        try {
            return new ScriptSchemasResult(executor.listPgSchemas());
        } catch (Exception e) {
            log.warn("PG schemas 목록 조회 실패 — 빈 리스트 응답", e);
            return new ScriptSchemasResult(Collections.emptyList());
        }
    }

    /**
     * SQL 실행 — 검증 통과 후 executor 호출.
     *
     * @throws IllegalArgumentException 입력 검증 실패(빈 SQL, SELECT 외 prefix)
     * @throws IllegalStateException    리포지토리 미설정
     * @throws RuntimeException         실 실행 오류(메시지에 DB 에러 코드 포함)
     */
    public ScriptRunResult run(ScriptRunRequest req) {
        String sql = req == null ? null : req.getSql();
        if (sql == null || sql.trim().isEmpty()) {
            throw new IllegalArgumentException("No SQL provided");
        }
        String verr = ScriptValidator.validateSelectOnly(sql);
        if (verr != null) {
            throw new IllegalArgumentException(verr);
        }
        String schema = ScriptValidator.sanitizeSchema(req.getSchema());

        ScriptExecutor.Result raw;
        try {
            raw = executor.run(sql, schema, MAX_SCRIPT_ROWS);
        } catch (IllegalStateException ise) {
            throw ise;
        } catch (Exception e) {
            String msg = e.getMessage() == null ? "execution failed" : e.getMessage();
            throw new RuntimeException(msg);
        }

        ScreenResponse screen = toScreen(raw, executor.currentDbType());
        return new ScriptRunResult(screen, raw.rows.size(), raw.truncated, MAX_SCRIPT_ROWS);
    }

    /**
     * ExecutionResult → ScreenResponse. 동적 컬럼은 ColumnRole.PLAIN 으로 통일하고
     * java.sql.Types 만 ColumnType(NUMBER/DATETIME/STRING) 으로 매핑해 FE 정렬에 보조한다.
     */
    private ScreenResponse toScreen(ScriptExecutor.Result raw, DbType dbType) {
        ScreenResponse.Builder b =
                ScreenResponse.builder("script_manager", "Script Manager", dbType.name());
        for (ScriptExecutor.ColumnInfo col : raw.columns) {
            b.column(ColumnDef.of(col.label, col.label, mapType(col.sqlType), ColumnRole.PLAIN));
        }
        for (Map<String, Object> row : raw.rows) {
            b.rowFromMap(row);
        }
        return b.build();
    }

    /** java.sql.Types → ColumnType. 분류 외는 STRING 으로 안전 폴백. */
    private ColumnType mapType(int sqlType) {
        switch (sqlType) {
            case java.sql.Types.BIGINT:
            case java.sql.Types.INTEGER:
            case java.sql.Types.SMALLINT:
            case java.sql.Types.TINYINT:
            case java.sql.Types.DECIMAL:
            case java.sql.Types.NUMERIC:
            case java.sql.Types.DOUBLE:
            case java.sql.Types.FLOAT:
            case java.sql.Types.REAL:
                return ColumnType.NUMBER;
            case java.sql.Types.DATE:
            case java.sql.Types.TIME:
            case java.sql.Types.TIMESTAMP:
            case java.sql.Types.TIMESTAMP_WITH_TIMEZONE:
            case java.sql.Types.TIME_WITH_TIMEZONE:
                return ColumnType.DATETIME;
            default:
                return ColumnType.STRING;
        }
    }
}
