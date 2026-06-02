package com.exem.inspector.screen.overview;

import java.io.IOException;
import java.nio.file.FileStore;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

import com.exem.inspector.common.db.DbType;
import com.exem.inspector.config.ServiceConfig;

/**
 * Overview Disk/Tablespace 카드 데이터 조립.
 *
 * <p>원본 {@code overview.py::_tablespace_card_html} (Oracle) /
 * {@code _disk_for_overview} (PG) 와 등가:
 * <ul>
 *   <li>Oracle: {@link OverviewDiskMapper#findOracleTablespaces()} 결과 리스트 + overall status</li>
 *   <li>PG: {@code pg_data_dir}(미설정 시 "/") 의 {@link FileStore} stat — total/used/free/percent</li>
 * </ul>
 * 임계는 {@code _pct_status(80, 90)} 보존.
 */
@Service
public class OverviewDiskService {

    private final ObjectProvider<OverviewDiskMapper> mapperProvider;
    private final ServiceConfig serviceConfig;

    static final int DISK_WARN = 80;
    static final int DISK_CRIT = 90;

    public OverviewDiskService(ObjectProvider<OverviewDiskMapper> mapperProvider,
                               ServiceConfig serviceConfig) {
        this.mapperProvider = mapperProvider;
        this.serviceConfig = serviceConfig;
    }

    /**
     * 응답 페이로드 — type 으로 Oracle/PG 구분.
     * Oracle: {@code {type: "tablespace", items: [{name,total_gb,used_gb,free_gb,percent,status}, ...], overall: "ok"|...}}
     * PG:     {@code {type: "disk", path, total_gb, used_gb, free_gb, percent, status}}
     */
    public Map<String, Object> disk() {
        DbType dbType = DbType.fromConfigValue(serviceConfig.repository().dbType());
        if (dbType == DbType.ORACLE) {
            return tablespaceOracle();
        }
        return diskPg();
    }

    private Map<String, Object> tablespaceOracle() {
        OverviewDiskMapper m = mapperProvider.getIfAvailable();
        if (m == null) {
            return error("tablespace", "리포지토리가 설정되지 않았습니다(service_config.json 확인).");
        }
        List<TablespaceRow> rows;
        try {
            rows = m.findOracleTablespaces();
        } catch (Exception e) {
            return error("tablespace", "tablespace 조회 실패: " + e.getMessage());
        }
        if (rows == null || rows.isEmpty()) {
            return error("tablespace", "No tablespace data available.");
        }
        List<Map<String, Object>> items = new ArrayList<>(rows.size());
        String overall = "ok";
        for (TablespaceRow r : rows) {
            double pct = nz(r.getPercent());
            String status = OverviewService.pctStatus(pct, DISK_WARN, DISK_CRIT);
            overall = worse(overall, status);
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("name",      r.getName());
            item.put("total_gb",  nz(r.getTotalGb()));
            item.put("used_gb",   nz(r.getUsedGb()));
            item.put("free_gb",   nz(r.getFreeGb()));
            item.put("percent",   pct);
            item.put("status",    status);
            items.add(item);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("type",    "tablespace");
        out.put("overall", overall);
        out.put("items",   items);
        return out;
    }

    private Map<String, Object> diskPg() {
        String configured = serviceConfig.repository().pgDataDir();
        String pathStr = configured.isEmpty() ? "/" : configured;
        Path path = Paths.get(pathStr);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("type", "disk");
        out.put("path", pathStr);
        try {
            FileStore fs = Files.getFileStore(path);
            long total = fs.getTotalSpace();
            long free  = fs.getUsableSpace();
            long used  = total - free;
            double pct = total > 0L ? round1(used / (double) total * 100.0) : 0.0;
            out.put("total_gb", round1(total / 1073741824.0));
            out.put("used_gb",  round1(used  / 1073741824.0));
            out.put("free_gb",  round1(free  / 1073741824.0));
            out.put("percent",  pct);
            out.put("status",   OverviewService.pctStatus(pct, DISK_WARN, DISK_CRIT));
        } catch (IOException e) {
            out.put("total_gb", 0.0);
            out.put("used_gb",  0.0);
            out.put("free_gb",  0.0);
            out.put("percent",  0.0);
            out.put("status",   "ok");
            out.put("error",    e.getMessage());
        }
        return out;
    }

    private static Map<String, Object> error(String type, String message) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("type",    type);
        m.put("overall", "warning");
        m.put("items",   new ArrayList<>());
        m.put("error",   message);
        return m;
    }

    private static double nz(Double v) { return v == null ? 0.0 : v; }

    private static double round1(double v) { return Math.round(v * 10.0) / 10.0; }

    /** 두 상태 중 더 나쁜 쪽 — critical > warning > ok. */
    private static String worse(String a, String b) {
        int ra = rank(a), rb = rank(b);
        return ra >= rb ? a : b;
    }

    private static int rank(String s) {
        if ("critical".equals(s)) return 2;
        if ("warning".equals(s))  return 1;
        return 0;
    }
}
