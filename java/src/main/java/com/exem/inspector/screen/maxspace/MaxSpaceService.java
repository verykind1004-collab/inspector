package com.exem.inspector.screen.maxspace;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Pattern;

import javax.sql.DataSource;

import org.apache.ibatis.session.SqlSession;
import org.apache.ibatis.session.SqlSessionFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

import com.exem.inspector.screen.maxspace.dto.InstanceRow;
import com.exem.inspector.screen.maxspace.dto.ServiceGroupRow;
import com.exem.inspector.screen.maxspace.dto.TablespaceRow;

/**
 * MaxSpace 메인 서비스 — 원본 tablespace_server.py 의 핵심 함수 1:1.
 *
 * <p>Step 3-1A 범위:
 * <ul>
 *   <li>build_data — 인스턴스별 ts_data fetch, 캐시 (cache_ttl_min, 기본 24h)</li>
 *   <li>getServiceGroups — service_id 기준 grouping</li>
 *   <li>getHealth — 캐시 상태 + 다음 자동 갱신 예정 시각</li>
 *   <li>refresh — 강제 캐시 invalidate + 재빌드</li>
 *   <li>reset — pool/캐시 폐기 (Inspector 가 Repository SAVE 후 호출)</li>
 * </ul>
 *
 * <p>Step 3-1B 에서 권한 필터 (apm_user_list/apm_users_db_list) + 트렌드 캐시 추가.
 * Step 3-1C 에서 warmup_trends + auto_refresh_loop ({@code @Scheduled}) 추가.
 *
 * <p>DataSource / SqlSessionFactory 는 Inspector BE 가 service_config.json 으로 동적 구성하므로
 * {@link ObjectProvider} 로 lazy 주입. Repository 미구성 상태에서는 health 만 "초기화중"으로 응답.
 */
@Service
public class MaxSpaceService {

    private static final Logger log = LoggerFactory.getLogger(MaxSpaceService.class);
    private static final Pattern SAFE_SCHEMA = Pattern.compile("^[a-zA-Z0-9_]+$");
    private static final DateTimeFormatter F_DATE = DateTimeFormatter.ofPattern("yyyy-MM-dd");
    private static final DateTimeFormatter F_DTM = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final DateTimeFormatter F_DTM_M = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    private final MaxSpaceConfig config;
    private final ObjectProvider<SqlSessionFactory> sqlSessionFactoryProvider;
    private final ObjectProvider<DataSource> dataSourceProvider;

    // ====== 캐시 상태 ======
    private volatile Map<String, Object> cache;        // { today, dbs[], tablespaces{} }
    private volatile long cacheTimeMs;                 // 0 = 미빌드
    private volatile Map<String, int[]> instMap;       // instance_name → [dbId] (Step B 에서 schema 도)
    private final Object buildLock = new Object();

    public MaxSpaceService(MaxSpaceConfig config,
                           ObjectProvider<SqlSessionFactory> sqlSessionFactoryProvider,
                           ObjectProvider<DataSource> dataSourceProvider) {
        this.config = config;
        this.sqlSessionFactoryProvider = sqlSessionFactoryProvider;
        this.dataSourceProvider = dataSourceProvider;
        this.instMap = Collections.emptyMap();
    }

    // ============================================================
    // 공개 API
    // ============================================================

    /** build_data — 캐시된 데이터 반환 (TTL 안이면 그대로, 아니면 재빌드). */
    public Map<String, Object> buildData() {
        long ttlMs = config.getCacheTtlMin() * 60_000L;
        Map<String, Object> snap = this.cache;
        if (snap != null && (System.currentTimeMillis() - cacheTimeMs) < ttlMs) {
            return snap;
        }
        synchronized (buildLock) {
            snap = this.cache;
            if (snap != null && (System.currentTimeMillis() - cacheTimeMs) < ttlMs) {
                return snap;
            }
            Map<String, Object> built = rebuildLocked();
            this.cache = built;
            this.cacheTimeMs = System.currentTimeMillis();
            return built;
        }
    }

    /** 서비스 그룹 — service_id 기준 grouping. 원본 get_service_groups 1:1. */
    public List<Map<String, Object>> getServiceGroups() {
        SqlSessionFactory factory = sqlSessionFactoryProvider.getIfAvailable();
        if (factory == null) {
            return Collections.emptyList();
        }
        try (SqlSession session = factory.openSession()) {
            MaxSpaceMapper mapper = session.getMapper(MaxSpaceMapper.class);
            List<ServiceGroupRow> rows = mapper.findServiceGroupRows();
            Map<Integer, Map<String, Object>> groups = new LinkedHashMap<>();
            for (ServiceGroupRow r : rows) {
                Map<String, Object> g = groups.computeIfAbsent(r.getServiceId(), sid -> {
                    Map<String, Object> m = new LinkedHashMap<>();
                    m.put("service_id", sid);
                    m.put("service_name", r.getServiceName());
                    m.put("instances", new ArrayList<Map<String, Object>>());
                    return m;
                });
                @SuppressWarnings("unchecked")
                List<Map<String, Object>> instances = (List<Map<String, Object>>) g.get("instances");
                Map<String, Object> inst = new LinkedHashMap<>();
                inst.put("db_id", r.getDbId());
                inst.put("instance_name", r.getInstanceName());
                instances.add(inst);
            }
            return new ArrayList<>(groups.values());
        }
    }

    /** /api/health — 원본 api_health 1:1. */
    public Map<String, Object> getHealth() {
        Map<String, Object> snap = this.cache;
        boolean cacheOk = (snap != null);
        Double cacheAgeMin = cacheTimeMs == 0 ? null
                : Math.round((System.currentTimeMillis() - cacheTimeMs) / 60_000.0 * 10.0) / 10.0;
        int dbCount = cacheOk ? ((List<?>) snap.get("dbs")).size() : 0;
        String dbType = currentDbType();

        LocalDateTime now = LocalDateTime.now();
        LocalDateTime target = now.withHour(config.getRefreshHour())
                .withMinute(config.getRefreshMinute()).withSecond(0).withNano(0);
        if (!now.isBefore(target)) {
            target = target.plusDays(1);
        }

        Map<String, Object> cacheNode = new LinkedHashMap<>();
        cacheNode.put("loaded", cacheOk);
        cacheNode.put("age_min", cacheAgeMin);
        cacheNode.put("db_count", dbCount);

        Map<String, Object> trendNode = new LinkedHashMap<>();
        trendNode.put("count", 0);          // Step B 에서 trend 캐시 도입 후 갱신
        trendNode.put("total", dbCount);

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ok", true);
        out.put("status", cacheOk ? "healthy" : "initializing");
        out.put("db_type", dbType == null ? "unknown" : dbType);
        out.put("cache", cacheNode);
        out.put("trend_cache", trendNode);
        out.put("next_refresh", target.format(F_DTM_M));
        out.put("server_time", now.format(F_DTM));
        return out;
    }

    /** /api/refresh — 강제 캐시 invalidate + 즉시 재빌드. token 검증은 Controller. */
    public Map<String, Object> refresh() {
        synchronized (buildLock) {
            this.cache = null;
            this.cacheTimeMs = 0;
            Map<String, Object> built = rebuildLocked();
            this.cache = built;
            this.cacheTimeMs = System.currentTimeMillis();
            return built;
        }
    }

    /** /api/reset — pool/캐시 폐기. token 검증은 Controller. */
    public void reset() {
        // Inspector BE 의 DataSource 는 service_config.json 변경 시 별도 hook 에서 재구성된다.
        // MaxSpace 측은 캐시만 폐기. Step C 에서 trend 캐시도 함께 폐기.
        synchronized (buildLock) {
            this.cache = null;
            this.cacheTimeMs = 0;
            this.instMap = Collections.emptyMap();
            log.info("[maxspace] reset — 캐시 폐기");
        }
    }

    // ============================================================
    // 내부 — buildLock 보유 상태에서 호출
    // ============================================================
    private Map<String, Object> rebuildLocked() {
        SqlSessionFactory factory = sqlSessionFactoryProvider.getIfAvailable();
        if (factory == null) {
            throw new IllegalStateException(
                    "Repository DB not configured. Labs → Configuration 에서 설정하세요.");
        }
        String dbType = currentDbType();
        log.info("[maxspace] 빌드 시작 (db_type={})", dbType);

        try (SqlSession session = factory.openSession()) {
            MaxSpaceMapper mapper = session.getMapper(MaxSpaceMapper.class);
            List<String> schemas = mapper.findTablespaceSchemas();
            List<InstanceRow> instances = mapper.findInstances();

            Map<String, String> schemaMap = new LinkedHashMap<>();
            boolean isPg = "postgresql".equalsIgnoreCase(dbType);
            if (isPg) {
                for (String s : schemas) {
                    schemaMap.put(s.toLowerCase(Locale.ROOT), s);
                }
            }

            Map<String, int[]> newInstMap = new LinkedHashMap<>();
            List<Map<String, Object>> dbList = new ArrayList<>();
            Map<String, List<TablespaceRow>> tsMap = new LinkedHashMap<>();

            for (InstanceRow inst : instances) {
                Integer dbId = inst.getDbId();
                String name = inst.getInstanceName();
                String biz = inst.getBusinessName() == null ? "-" : inst.getBusinessName();

                String schema;
                if (isPg) {
                    schema = schemaMap.get(name == null ? "" : name.toLowerCase(Locale.ROOT));
                    if (schema == null) {
                        continue;     // 매칭 schema 없으면 skip (원본 fetch_inst 와 동일)
                    }
                } else {
                    schema = "";       // Oracle 은 schema 무시
                }

                if (schema.length() > 0 && !SAFE_SCHEMA.matcher(schema).matches()) {
                    log.warn("[maxspace] 비안전 schema 건너뜀: {}", schema);
                    continue;
                }

                newInstMap.put(name, new int[]{dbId == null ? -1 : dbId});

                try {
                    List<TablespaceRow> tsData = mapper.findTablespaceData(schema, dbId == null ? -1 : dbId);
                    if (tsData == null || tsData.isEmpty()) {
                        continue;
                    }
                    double totalGb = 0, usedGb = 0, sumW = 0, sumM = 0;
                    for (TablespaceRow t : tsData) {
                        totalGb += nz(t.getTotalGb());
                        usedGb += nz(t.getUsedGb());
                        sumW += nz(t.getUsedPct1w());
                        sumM += nz(t.getUsedPct1m());
                    }
                    double avgW = sumW / tsData.size();
                    double avgM = sumM / tsData.size();

                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("product", "ORACLE");
                    row.put("biz_name", biz);
                    row.put("db_name", name);
                    row.put("db_id", dbId);
                    row.put("schema", schema == null ? "" : schema);
                    row.put("total_gb", round2(totalGb));
                    row.put("used_gb", round2(usedGb));
                    row.put("used_pct_1w", round1(avgW));
                    row.put("used_pct_1m", round1(avgM));
                    dbList.add(row);
                    tsMap.put(name, tsData);
                } catch (Exception e) {
                    log.error("[maxspace] {} 오류: {}", name, e.toString());
                }
            }

            this.instMap = newInstMap;
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("today", LocalDateTime.now().format(F_DATE));
            out.put("dbs", dbList);
            out.put("tablespaces", tsMap);
            log.info("[maxspace] 완료: {} 개 DB", dbList.size());
            return out;
        }
    }

    /** 현재 DataSource 가 PG / Oracle 중 어느 쪽인지 결정. service_config 가 source. */
    private String currentDbType() {
        DataSource ds = dataSourceProvider.getIfAvailable();
        if (ds == null) {
            return null;
        }
        try {
            String url = ds.unwrap(com.zaxxer.hikari.HikariDataSource.class).getJdbcUrl();
            if (url == null) {
                return null;
            }
            String low = url.toLowerCase(Locale.ROOT);
            if (low.startsWith("jdbc:oracle")) {
                return "oracle";
            }
            if (low.startsWith("jdbc:postgresql")) {
                return "postgresql";
            }
        } catch (Exception ignored) {
            // Hikari 가 아닌 다른 구현 — null 반환
        }
        return null;
    }

    private static double nz(Double d) { return d == null ? 0.0 : d; }

    private static double round1(double v) { return Math.round(v * 10.0) / 10.0; }

    private static double round2(double v) { return Math.round(v * 100.0) / 100.0; }
}
