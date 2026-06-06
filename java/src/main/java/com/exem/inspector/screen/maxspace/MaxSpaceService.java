package com.exem.inspector.screen.maxspace;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
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
import com.exem.inspector.screen.maxspace.dto.TrendPoint;

/**
 * MaxSpace 메인 서비스 — 원본 tablespace_server.py 의 핵심 함수 1:1.
 *
 * <p>Step 3-1A: build_data / getServiceGroups / getHealth / refresh / reset.
 * Step 3-1B (현재): getTrend + 트렌드 캐시 + instMap (인스턴스 → (schema, dbId)).
 * Step 3-1C: warmup_trends + auto_refresh_loop ({@code @Scheduled}).
 *
 * <p>권한 필터는 Controller 가 {@link MaxSpacePermissionService} 결과로 직접 처리 (원본도
 * api_data / api_trend 안에서 분기). Service 는 raw 캐시 데이터만 반환.
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
    private volatile Map<String, Object> cache;            // { today, dbs[], tablespaces{} }
    private volatile long cacheTimeMs;                     // 0 = 미빌드
    private volatile Map<String, InstanceInfo> instMap;    // instance_name → (schema, dbId)
    private final Object buildLock = new Object();

    private final Map<String, Map<String, List<Map<String, Object>>>> trendCache = new ConcurrentHashMap<>();
    private final Map<String, Long> trendCacheTimeMs = new ConcurrentHashMap<>();

    public MaxSpaceService(MaxSpaceConfig config,
                           ObjectProvider<SqlSessionFactory> sqlSessionFactoryProvider,
                           ObjectProvider<DataSource> dataSourceProvider) {
        this.config = config;
        this.sqlSessionFactoryProvider = sqlSessionFactoryProvider;
        this.dataSourceProvider = dataSourceProvider;
        this.instMap = Collections.emptyMap();
    }

    /** 인스턴스 → (schema, dbId) — Service 내부 lookup 전용. */
    public static final class InstanceInfo {
        public final String schema;     // PG: 스키마명, Oracle: ""
        public final int dbId;

        InstanceInfo(String schema, int dbId) {
            this.schema = schema == null ? "" : schema;
            this.dbId = dbId;
        }
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

    /**
     * 인스턴스 1개의 트렌드 — 캐시 우선. 캐시 미스 시 instMap 에서 (schema, dbId) 찾고
     * mapper 호출. instMap 도 비어있으면 build_data 한 번 강제.
     *
     * @return ts_name 기준 grouping 된 { ts_name: [{date, pct, used, total}] } 형태 — 원본
     *         get_trend 반환 1:1.
     */
    public Map<String, List<Map<String, Object>>> getTrend(String dbName) {
        long ttlMs = config.getCacheTtlMin() * 60_000L;
        Map<String, List<Map<String, Object>>> cached = trendCache.get(dbName);
        Long t = trendCacheTimeMs.get(dbName);
        if (cached != null && t != null && (System.currentTimeMillis() - t) < ttlMs) {
            return cached;
        }

        InstanceInfo info = instMap.get(dbName);
        if (info == null) {
            // 캐시에 없으면 build_data 한 번 강제로 부르고 재시도 (원본 api_trend 동일).
            buildData();
            info = instMap.get(dbName);
            if (info == null) {
                throw new NoSuchInstanceException(dbName);
            }
        }
        return fetchAndCacheTrend(dbName, info.schema, info.dbId);
    }

    /** instMap 에서 db_name 의 (schema, dbId) 조회 — Controller 의 권한 검증용. */
    public InstanceInfo lookupInstance(String dbName) {
        InstanceInfo info = instMap.get(dbName);
        if (info == null) {
            buildData();
            info = instMap.get(dbName);
        }
        return info;
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
        trendNode.put("count", trendCache.size());
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
            trendCache.clear();
            trendCacheTimeMs.clear();
            Map<String, Object> built = rebuildLocked();
            this.cache = built;
            this.cacheTimeMs = System.currentTimeMillis();
            return built;
        }
    }

    /** /api/reset — pool/캐시 폐기. token 검증은 Controller. */
    public void reset() {
        synchronized (buildLock) {
            this.cache = null;
            this.cacheTimeMs = 0;
            this.instMap = Collections.emptyMap();
            trendCache.clear();
            trendCacheTimeMs.clear();
            log.info("[maxspace] reset — 캐시/instMap/trend 폐기");
        }
    }

    // ============================================================
    // 내부 — buildLock 보유 상태에서 호출 (rebuildLocked)
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

            Map<String, InstanceInfo> newInstMap = new LinkedHashMap<>();
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
                        continue;
                    }
                } else {
                    schema = "";
                }
                if (!schema.isEmpty() && !SAFE_SCHEMA.matcher(schema).matches()) {
                    log.warn("[maxspace] 비안전 schema 건너뜀: {}", schema);
                    continue;
                }

                newInstMap.put(name, new InstanceInfo(schema, dbId == null ? -1 : dbId));

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
                    row.put("schema", schema);
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

    /**
     * 트렌드 1 회 빌드 + 캐시 적재. row 들을 ts_name 기준 grouping → 원본 get_trend 반환 1:1.
     */
    private Map<String, List<Map<String, Object>>> fetchAndCacheTrend(String dbName, String schema, int dbId) {
        if (!schema.isEmpty() && !SAFE_SCHEMA.matcher(schema).matches()) {
            throw new IllegalArgumentException("허용되지 않은 스키마명: " + schema);
        }
        SqlSessionFactory factory = sqlSessionFactoryProvider.getIfAvailable();
        if (factory == null) {
            throw new IllegalStateException(
                    "Repository DB not configured. Labs → Configuration 에서 설정하세요.");
        }
        try (SqlSession session = factory.openSession()) {
            MaxSpaceMapper mapper = session.getMapper(MaxSpaceMapper.class);
            List<TrendPoint> rows = mapper.findTrend(schema, dbId);
            Map<String, List<Map<String, Object>>> trend = new LinkedHashMap<>();
            for (TrendPoint r : rows) {
                String ts = r.getTsName();
                double total = nz(r.getTotalGb());
                double used = nz(r.getUsedGb());
                List<Map<String, Object>> series = trend.computeIfAbsent(ts, k -> new ArrayList<>());
                Map<String, Object> point = new LinkedHashMap<>();
                point.put("date", r.getSnapDay());
                point.put("pct", total > 0 ? round2(used / total * 100.0) : 0.0);
                point.put("used", used);
                point.put("total", total);
                series.add(point);
            }
            // ConcurrentHashMap 에 적재 — 캐시는 thread-safe.
            // map immutability 위해 HashMap 으로 한 번 더 감싸지 않고 그대로 둠 (원본도 동일).
            trendCache.put(dbName, trend);
            trendCacheTimeMs.put(dbName, System.currentTimeMillis());
            return trend;
        }
    }

    /** 현재 DataSource 가 PG / Oracle 중 어느 쪽인지 결정. */
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
            // Hikari 외 다른 구현 — null 반환
        }
        return null;
    }

    private static double nz(Double d) { return d == null ? 0.0 : d; }

    private static double round1(double v) { return Math.round(v * 10.0) / 10.0; }

    private static double round2(double v) { return Math.round(v * 100.0) / 100.0; }

    /** Controller 가 404 로 변환. */
    public static class NoSuchInstanceException extends RuntimeException {
        public NoSuchInstanceException(String name) { super("인스턴스 없음: " + name); }
    }

    /** 미사용 import 경고 회피용 (HashMap 미사용 시 ConcurrentHashMap 으로만 충분). */
    @SuppressWarnings("unused")
    private static final Map<String, Object> _UNUSED_HASHMAP_TYPE = new HashMap<>();
}
