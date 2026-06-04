package com.exem.inspector.screen.config;

import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import javax.sql.DataSource;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import com.exem.inspector.common.db.DbType;
import com.exem.inspector.config.ServiceConfig;

/**
 * Config Dump 서비스 — 원본 config_dump.py 의 api_config_dump 와 1:1 동등.
 *
 * <p>screen 4 와 별도 화면. 선택한 메뉴(들)에 속한 tables + sequences 를
 * SELECT * 결과로 dump → 정렬/검색/JSON 다운로드 FE 화면에 전달.
 *
 * <p>repository DataSource 가 미설정이거나 테이블이 존재하지 않으면 해당 항목은 skip.
 */
@Service
public class ConfigDumpService {

    private static final Logger log = LoggerFactory.getLogger(ConfigDumpService.class);
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss");

    private final ObjectProvider<DataSource> dataSourceProvider;
    private final ServiceConfig serviceConfig;

    public ConfigDumpService(ObjectProvider<DataSource> dataSourceProvider,
                              ServiceConfig serviceConfig) {
        this.dataSourceProvider = dataSourceProvider;
        this.serviceConfig = serviceConfig;
    }

    /** 메뉴 정의 노출 — 원본 MENU_DEFS 5개. */
    public Collection<ConfigDumpMenu> menus() {
        return ConfigDumpMenu.defaults().values();
    }

    /**
     * 선택한 메뉴 키들에 대해 tables + sequences 를 dump.
     * 알 수 없는 키는 무시. 빈 리스트면 모든 메뉴 dump.
     */
    public ConfigDumpPayload dump(List<String> menuKeys) {
        Map<String, ConfigDumpMenu> all = ConfigDumpMenu.defaults();
        List<ConfigDumpMenu> selected = new ArrayList<>();
        if (menuKeys == null || menuKeys.isEmpty()) {
            selected.addAll(all.values());
        } else {
            for (String k : menuKeys) {
                ConfigDumpMenu m = all.get(k);
                if (m != null) selected.add(m);
            }
        }

        String dbType = serviceConfig.repository().dbType();
        DbType type = DbType.fromConfigValue(dbType);
        String filenameBase = "config_dump_" + LocalDateTime.now().format(TS);

        Map<String, List<Map<String, Object>>> tableDumps = new LinkedHashMap<>();
        Map<String, Object> sequenceValues = new LinkedHashMap<>();
        List<String> skipped = new ArrayList<>();

        DataSource ds = dataSourceProvider.getIfAvailable();
        if (ds == null) {
            // Repository 미설정 — 메타만 반환
            return new ConfigDumpPayload(filenameBase, dbType, selectedKeys(selected),
                    tableDumps, sequenceValues, skipped);
        }

        JdbcTemplate jdbc = new JdbcTemplate(ds);

        for (ConfigDumpMenu menu : selected) {
            for (String table : menu.getTables()) {
                try {
                    List<Map<String, Object>> rows = jdbc.queryForList("SELECT * FROM " + table);
                    tableDumps.put(table, sanitize(rows));
                } catch (RuntimeException e) {
                    log.debug("table dump skip: {} ({})", table, e.getMessage());
                    skipped.add(table);
                }
            }
            for (String seq : menu.getSequences()) {
                try {
                    Long v = querySequenceValue(jdbc, seq, type);
                    sequenceValues.put(seq, v);
                } catch (RuntimeException e) {
                    log.debug("sequence skip: {} ({})", seq, e.getMessage());
                    skipped.add(seq);
                }
            }
        }

        return new ConfigDumpPayload(filenameBase, dbType, selectedKeys(selected),
                tableDumps, sequenceValues, skipped);
    }

    private static List<String> selectedKeys(List<ConfigDumpMenu> menus) {
        List<String> out = new ArrayList<>(menus.size());
        for (ConfigDumpMenu m : menus) out.add(m.getKey());
        return out;
    }

    /** Timestamp/Decimal 등 JSON 직렬화 불가 객체 → ISO 문자열 / 문자열로 변환. */
    private List<Map<String, Object>> sanitize(List<Map<String, Object>> rows) {
        List<Map<String, Object>> out = new ArrayList<>(rows.size());
        for (Map<String, Object> r : rows) {
            Map<String, Object> safe = new LinkedHashMap<>();
            for (Map.Entry<String, Object> e : r.entrySet()) {
                safe.put(e.getKey(), safeValue(e.getValue()));
            }
            out.add(safe);
        }
        return out;
    }

    /** 원본 _json_safe 1:1 — Timestamp/Date/Decimal/byte[] 처리. */
    static Object safeValue(Object v) {
        if (v == null) return null;
        if (v instanceof Timestamp) return v.toString();
        if (v instanceof java.sql.Date) return v.toString();
        if (v instanceof java.sql.Time) return v.toString();
        if (v instanceof java.math.BigDecimal) {
            // 정수면 long, 아니면 double
            java.math.BigDecimal bd = (java.math.BigDecimal) v;
            if (bd.scale() <= 0) return bd.longValueExact();
            return bd.doubleValue();
        }
        if (v instanceof byte[]) return "[binary " + ((byte[]) v).length + "B]";
        return v;
    }

    private Long querySequenceValue(JdbcTemplate jdbc, String seq, DbType type) {
        String sql;
        if (type == DbType.POSTGRESQL) {
            sql = "SELECT last_value FROM " + seq;
        } else {
            // Oracle: SELECT seq.NEXTVAL 은 값을 증가시키므로 CURRVAL 사용 — 단, 세션 초기 미사용 시 ORA-08002.
            // 우선 USER_SEQUENCES 의 LAST_NUMBER 사용.
            sql = "SELECT LAST_NUMBER FROM USER_SEQUENCES WHERE SEQUENCE_NAME = UPPER('" + seq + "')";
        }
        return jdbc.queryForObject(sql, Long.class);
    }

    /** 미사용 — Collections.emptyList 캐시 회피 javac warning 억제. */
    @SuppressWarnings("unused")
    private static <T> List<T> emptyL() { return Collections.emptyList(); }
}
