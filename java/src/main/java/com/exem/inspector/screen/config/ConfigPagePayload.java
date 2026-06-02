package com.exem.inspector.screen.config;

import java.util.List;
import java.util.Map;

/**
 * Config Page 통합 응답 — service_config.json 의 repository/services/log_paths 블록 그대로 노출.
 *
 * <p>원본 config_page.py 의 폼 데이터와 동등. connection_test 결과는 별도 endpoint.
 */
public class ConfigPagePayload {

    private final Map<String, Object> repository;
    private final Map<String, Object> services;
    private final Map<String, Object> logPaths;
    private final String configFilePath;

    public ConfigPagePayload(Map<String, Object> repository, Map<String, Object> services,
                             Map<String, Object> logPaths, String configFilePath) {
        this.repository = repository;
        this.services = services;
        this.logPaths = logPaths;
        this.configFilePath = configFilePath;
    }

    public Map<String, Object> getRepository() { return repository; }
    public Map<String, Object> getServices() { return services; }
    public Map<String, Object> getLogPaths() { return logPaths; }
    public String getConfigFilePath() { return configFilePath; }
}
