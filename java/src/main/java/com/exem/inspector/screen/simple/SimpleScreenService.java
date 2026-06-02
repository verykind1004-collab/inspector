package com.exem.inspector.screen.simple;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

import com.exem.inspector.common.db.DbType;
import com.exem.inspector.common.web.screen.ColumnDef;
import com.exem.inspector.common.web.screen.ColumnRole;
import com.exem.inspector.common.web.screen.ColumnType;
import com.exem.inspector.common.web.screen.ScreenResponse;
import com.exem.inspector.config.ServiceConfig;

/**
 * 원본 _db_page 패턴 단순 점검 화면 일괄 서비스. 각 화면 spec(컬럼 메타 + 매퍼 호출자)을 보유한다.
 *
 * <p>I절 규약 준수: 화면 코드에 SQL/커넥션 분기를 두지 않음. 컬럼 메타는 화면 고정.
 * Oracle/PG 컬럼 alias 가 다른 화면(capacity 등)은 dbType 별 별도 메타 정의.
 */
@Service
public class SimpleScreenService {

    private final ObjectProvider<SimpleScreenMapper> mapperProvider;
    private final ServiceConfig serviceConfig;

    public SimpleScreenService(ObjectProvider<SimpleScreenMapper> mapperProvider, ServiceConfig serviceConfig) {
        this.mapperProvider = mapperProvider;
        this.serviceConfig = serviceConfig;
    }

    /** 화면 spec: 메타 + dbType 별 컬럼 + 매퍼 호출. */
    private static final class Spec {
        final String key;
        final String title;
        final List<ColumnDef> oracleCols;
        final List<ColumnDef> pgCols;
        final Function<SimpleScreenMapper, List<LinkedHashMap<String, Object>>> fetch;
        final boolean oracleSupported;
        final boolean pgSupported;
        Spec(String key, String title,
             List<ColumnDef> oracleCols, List<ColumnDef> pgCols,
             boolean oracleSupported, boolean pgSupported,
             Function<SimpleScreenMapper, List<LinkedHashMap<String, Object>>> fetch) {
            this.key = key; this.title = title;
            this.oracleCols = oracleCols; this.pgCols = pgCols;
            this.oracleSupported = oracleSupported; this.pgSupported = pgSupported;
            this.fetch = fetch;
        }
    }

    private static ColumnDef plain(String key, String label) {
        return ColumnDef.of(key, label, ColumnType.STRING, ColumnRole.PLAIN);
    }
    private static ColumnDef inst(String key, String label) {
        return ColumnDef.of(key, label, ColumnType.STRING, ColumnRole.INSTANCE);
    }
    private static ColumnDef id(String key, String label) {
        return ColumnDef.of(key, label, ColumnType.NUMBER, ColumnRole.ID);
    }
    private static ColumnDef num(String key, String label) {
        return ColumnDef.of(key, label, ColumnType.NUMBER, ColumnRole.PLAIN);
    }
    private static ColumnDef dt(String key, String label) {
        return ColumnDef.of(key, label, ColumnType.DATETIME, ColumnRole.PLAIN);
    }

    private static final Map<String, Spec> SPECS = new LinkedHashMap<>();
    static {
        // capacity — Oracle: tablespace_name/Used/Total/PERCENT, PG: schema_name/size_gb
        register(new Spec("capacity", "Capacity Check",
                Arrays.asList(plain("TABLESPACE_NAME", "Tablespace Name"),
                              plain("Used", "Used"),
                              plain("Total", "Total"),
                              plain("PERCENT", "Percent")),
                Arrays.asList(plain("schema_name", "Schema Name"),
                              plain("size_gb", "Size")),
                true, true, SimpleScreenMapper::findCapacity));

        // license — Oracle/PG 동일 컬럼
        List<ColumnDef> licenseCols = Arrays.asList(
                id("db_id", "DB ID"),
                inst("instance_name", "Instance Name"),
                plain("sid", "SID"),
                plain("rts_version", "RTS Version"),
                plain("host_ip", "Host IP"),
                plain("os_type", "OS Type"),
                plain("RTS PORT", "RTS Port"),
                plain("lsnr_port", "Listener Port"));
        register(new Spec("license", "Instance List", licenseCols, licenseCols, true, true,
                SimpleScreenMapper::findLicense));

        // alert — Oracle: DB ID/INSTANCE NAME/ALARM NAME/COUNT. PG 함수는 동일 컬럼 가정.
        List<ColumnDef> alertCols = Arrays.asList(
                id("DB ID", "DB ID"),
                inst("INSTANCE NAME", "Instance Name"),
                plain("ALARM NAME", "Alarm Name"),
                num("COUNT", "Count"));
        register(new Spec("alert", "Alert Check", alertCols, alertCols, true, true,
                SimpleScreenMapper::findAlert));

        // query — Oracle: DB ID/instance_name/plan_status/bind_status/tablespace_status/parameter_status
        List<ColumnDef> queryCols = Arrays.asList(
                id("DB ID", "DB ID"),
                inst("instance_name", "Instance Name"),
                plain("plan_status", "Plan Status"),
                plain("bind_status", "Bind Status"),
                plain("tablespace_status", "Tablespace Status"),
                plain("parameter_status", "Parameter Status"));
        register(new Spec("query", "Query Check", queryCols, queryCols, true, true,
                SimpleScreenMapper::findQuery));

        // top_segment — Oracle 대문자 / PG 소문자
        register(new Spec("top_segment", "Top Segment",
                Arrays.asList(plain("SCHEMA_NAME", "Schema"),
                              plain("TABLE_NAME", "Table Name"),
                              plain("TOTAL_SIZE", "Total Size"),
                              plain("TABLE_SIZE", "Table Size"),
                              plain("INDEX_SIZE", "Index Size")),
                Arrays.asList(plain("schema_name", "Schema"),
                              plain("table_name", "Table Name"),
                              plain("total_size", "Total Size"),
                              plain("table_size", "Table Size"),
                              plain("index_size", "Index Size")),
                true, true, SimpleScreenMapper::findTopSegment));

        // temp_table — Oracle/PG 동일 alias("SCHEMA"/"TEMP TABLE")
        List<ColumnDef> tempCols = Arrays.asList(
                plain("SCHEMA", "Schema"),
                plain("TEMP TABLE", "Temp Table"));
        register(new Spec("temp_table", "Temp Table", tempCols, tempCols, true, true,
                SimpleScreenMapper::findTempTable));

        // vacuum (PG 전용)
        register(new Spec("vacuum", "Vacuum Check",
                null,
                Arrays.asList(plain("schema", "Schema"),
                              plain("table_name", "Table Name"),
                              num("dead_tuples", "Dead Tuples"),
                              num("vacuum_threshold", "Vacuum Threshold"),
                              dt("last_autovacuum", "Last Autovacuum")),
                false, true, SimpleScreenMapper::findVacuum));

        // age (PG 전용)
        register(new Spec("age", "Age Check",
                null,
                Arrays.asList(plain("dbname", "Database"),
                              plain("parameter_max_age", "Max Age (param)"),
                              plain("max_age", "Max Age"),
                              plain("current_txid", "Current TxID")),
                false, true, SimpleScreenMapper::findAge));
    }

    private static void register(Spec s) {
        SPECS.put(s.key, s);
    }

    /** 사용 가능한 화면 키 집합(컨트롤러 라우트 화이트리스트로 사용). */
    public static java.util.Set<String> screenKeys() {
        return SPECS.keySet();
    }

    public ScreenResponse find(String key) {
        Spec spec = SPECS.get(key);
        if (spec == null) {
            throw new IllegalArgumentException("미지원 화면 키: " + key);
        }
        DbType dbType = DbType.fromConfigValue(serviceConfig.repository().dbType());
        boolean supported = (dbType == DbType.ORACLE) ? spec.oracleSupported : spec.pgSupported;
        if (!supported) {
            throw new IllegalStateException("현재 DB 타입에서는 지원하지 않는 화면입니다: " + key);
        }

        SimpleScreenMapper mapper = mapperProvider.getIfAvailable();
        if (mapper == null) {
            throw new IllegalStateException("리포지토리가 설정되지 않았습니다(service_config.json 확인).");
        }
        List<LinkedHashMap<String, Object>> rows = spec.fetch.apply(mapper);
        if (rows == null) rows = new ArrayList<>();

        List<ColumnDef> cols = (dbType == DbType.ORACLE) ? spec.oracleCols : spec.pgCols;
        ScreenResponse.Builder b = ScreenResponse.builder(spec.key, spec.title, dbType.name());
        for (ColumnDef c : cols) b.column(c);
        for (LinkedHashMap<String, Object> row : rows) b.rowFromMap(row);
        return b.build();
    }
}
