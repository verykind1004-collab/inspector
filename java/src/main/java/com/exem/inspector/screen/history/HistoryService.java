package com.exem.inspector.screen.history;

import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.BiFunction;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

import com.exem.inspector.common.db.DbType;
import com.exem.inspector.common.web.screen.ColumnDef;
import com.exem.inspector.common.web.screen.ColumnRole;
import com.exem.inspector.common.web.screen.ColumnType;
import com.exem.inspector.common.web.screen.ScreenResponse;
import com.exem.inspector.config.ServiceConfig;

/**
 * History 화면 — INSP_*_HISTORY 5 view 의 단일 통합 서비스.
 *
 * <p>원본 pages/history.py (1294라인) 의 표 부분과 동등(차트는 후속). view 별 컬럼 메타 + SQL 호출.
 */
@Service
public class HistoryService {

    /** view → (제목, 컬럼 메타, SQL 호출). */
    private static final Map<String, ViewSpec> SPECS = new java.util.LinkedHashMap<>();

    static {
        SPECS.put("os", new ViewSpec(
                "OS History",
                Arrays.asList(
                        col("collected_at", "Collected At", ColumnType.DATETIME),
                        col("cpu_percent",  "CPU %",        ColumnType.NUMBER),
                        col("cpu_user",     "CPU User",     ColumnType.NUMBER),
                        col("cpu_system",   "CPU System",   ColumnType.NUMBER),
                        col("cpu_iowait",   "CPU IO Wait",  ColumnType.NUMBER),
                        col("mem_total_gb", "Mem Total GB", ColumnType.NUMBER),
                        col("mem_used_gb",  "Mem Used GB",  ColumnType.NUMBER),
                        col("mem_percent",  "Mem %",        ColumnType.NUMBER)),
                HistoryMapper::findOsHistory));
        SPECS.put("tbs", new ViewSpec(
                "Tablespace History",
                Arrays.asList(
                        col("collected_at", "Collected At", ColumnType.DATETIME),
                        col("tbs_name",     "Tablespace",   ColumnType.STRING),
                        col("used_gb",      "Used GB",      ColumnType.NUMBER),
                        col("total_gb",     "Total GB",     ColumnType.NUMBER),
                        col("free_gb",      "Free GB",      ColumnType.NUMBER),
                        col("used_percent", "Used %",       ColumnType.NUMBER)),
                HistoryMapper::findTbsHistory));
        SPECS.put("service", new ViewSpec(
                "Service History",
                Arrays.asList(
                        col("collected_at", "Collected At", ColumnType.DATETIME),
                        col("service_name", "Service",      ColumnType.STRING),
                        col("status",       "Status",       ColumnType.STRING)),
                HistoryMapper::findServiceHistory));
        SPECS.put("qcnt", new ViewSpec(
                "Query Count History",
                Arrays.asList(
                        col("collected_at", "Collected At", ColumnType.DATETIME),
                        col("qcnt",  "Query Count",  ColumnType.NUMBER)),
                HistoryMapper::findQcntHistory));
        SPECS.put("summary", new ViewSpec(
                "Summary Check History",
                Arrays.asList(
                        col("collected_at",  "Collected At", ColumnType.DATETIME),
                        col("summary_type",  "Summary Type", ColumnType.STRING),
                        col("instance_name", "Instance",     ColumnType.STRING),
                        col("status",        "Status",       ColumnType.STRING)),
                HistoryMapper::findSummaryHistory));
    }

    private static ColumnDef col(String key, String label, ColumnType type) {
        return ColumnDef.of(key, label, type, ColumnRole.PLAIN);
    }

    private final ObjectProvider<HistoryMapper> mapperProvider;
    private final ServiceConfig serviceConfig;

    public HistoryService(ObjectProvider<HistoryMapper> mapperProvider, ServiceConfig serviceConfig) {
        this.mapperProvider = mapperProvider;
        this.serviceConfig = serviceConfig;
    }

    public ScreenResponse find(String view, int days, int limit) {
        ViewSpec spec = SPECS.get(view);
        if (spec == null) {
            throw new IllegalArgumentException("Unknown view: " + view);
        }
        if (days <= 0) days = 7;
        if (days > 365) days = 365;
        if (limit <= 0) limit = 500;
        if (limit > 5000) limit = 5000;

        DbType dbType = DbType.fromConfigValue(serviceConfig.repository().dbType());
        HistoryMapper mapper = mapperProvider.getIfAvailable();
        List<LinkedHashMap<String, Object>> rows = Collections.emptyList();
        if (mapper != null) {
            List<LinkedHashMap<String, Object>> r = spec.fetch.apply(mapper, new int[]{days, limit});
            if (r != null) rows = r;
        }

        ScreenResponse.Builder b = ScreenResponse.builder("history_" + view, spec.title, dbType.name());
        for (ColumnDef c : spec.columns) b.column(c);
        for (LinkedHashMap<String, Object> row : rows) b.rowFromMap(row);
        return b.build();
    }

    public static java.util.Set<String> views() { return SPECS.keySet(); }

    private static final class ViewSpec {
        final String title;
        final List<ColumnDef> columns;
        final BiFunction<HistoryMapper, int[], List<LinkedHashMap<String, Object>>> fetch;

        ViewSpec(String title, List<ColumnDef> columns,
                 TriCall fetch) {
            this.title = title;
            this.columns = columns;
            this.fetch = (m, args) -> fetch.call(m, args[0], args[1]);
        }
    }

    /** mapper method 시그니처 통일을 위한 헬퍼 인터페이스. */
    @FunctionalInterface
    private interface TriCall {
        List<LinkedHashMap<String, Object>> call(HistoryMapper m, int days, int limit);
    }
}
