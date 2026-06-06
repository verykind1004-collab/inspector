package com.exem.inspector.screen.maxspace;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * MaxSpace 전용 설정 — 원본 {@code tablespace_config.json} 1:1.
 *
 * <p>키: cache_ttl_min (분, 기본 1440=24h) / refresh_hour / refresh_minute /
 * refresh_token. service_config_path 와 port 는 Inspector BE 가 통합 관리하므로 사용 안 함.
 *
 * <p>파일 누락/파싱 실패 시 안전 기본값 사용 + WARN 로그. 운영자가 점검 가능.
 */
@Component
public class MaxSpaceConfig {

    private static final Logger log = LoggerFactory.getLogger(MaxSpaceConfig.class);

    private final Path configPath;
    private final ObjectMapper mapper = new ObjectMapper();

    private volatile long cacheTtlMin = 1440L;
    private volatile int refreshHour = 1;
    private volatile int refreshMinute = 5;
    private volatile String refreshToken = "";

    public MaxSpaceConfig(@Value("${inspector.maxspace.config-path:config/tablespace_config.json}")
                          String configPathProperty) {
        this.configPath = Paths.get(configPathProperty);
        reload();
    }

    /**
     * 디스크에서 현재 설정을 다시 읽는다. 누락 항목은 기본값 유지.
     */
    public synchronized void reload() {
        if (!Files.isRegularFile(configPath)) {
            log.warn("MaxSpace 설정 없음 — 기본값 사용 (path={})", configPath);
            return;
        }
        try {
            byte[] bytes = Files.readAllBytes(configPath);
            @SuppressWarnings("unchecked")
            Map<String, Object> cfg = mapper.readValue(bytes, Map.class);

            Object ttl = cfg.get("cache_ttl_min");
            if (ttl instanceof Number) {
                this.cacheTtlMin = ((Number) ttl).longValue();
            }
            Object hh = cfg.get("refresh_hour");
            if (hh instanceof Number) {
                this.refreshHour = ((Number) hh).intValue();
            }
            Object mm = cfg.get("refresh_minute");
            if (mm instanceof Number) {
                this.refreshMinute = ((Number) mm).intValue();
            }
            Object tk = cfg.get("refresh_token");
            if (tk instanceof String) {
                this.refreshToken = (String) tk;
            }
            log.info("MaxSpace 설정 로드: ttl={}min refresh={}:{} token={}자",
                    cacheTtlMin, refreshHour, refreshMinute,
                    refreshToken == null ? 0 : refreshToken.length());
        } catch (IOException e) {
            log.warn("MaxSpace 설정 파싱 실패 — 기본값 유지", e);
        }
    }

    public long getCacheTtlMin() { return cacheTtlMin; }

    public int getRefreshHour() { return refreshHour; }

    public int getRefreshMinute() { return refreshMinute; }

    public String getRefreshToken() { return refreshToken; }
}
