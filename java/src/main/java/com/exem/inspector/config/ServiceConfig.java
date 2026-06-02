package com.exem.inspector.config;

import java.io.File;
import java.io.IOException;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import com.exem.inspector.common.db.RepositoryConfig;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * service_config.json 로더.
 *
 * <p>리포지토리/서비스 정보를 런타임에 읽는다(기존 Python service_config.py 대응).
 * 파일이 없거나 비어 있으면 미설정 상태로 둔다 — 설정 UI 도입 전까지 부팅을 막지 않는다.
 * 설정 변경 시 재로딩(reload)으로 반영한다.
 */
@Component
public class ServiceConfig {

    private static final Logger log = LoggerFactory.getLogger(ServiceConfig.class);

    private final File configFile;
    private final ObjectMapper objectMapper = new ObjectMapper();

    private volatile RepositoryConfig repository = new RepositoryConfig();
    private volatile ServicesBlock services = new ServicesBlock();

    public ServiceConfig(@Value("${inspector.service-config-path}") String path) {
        this.configFile = new File(path);
        reload();
    }

    /** service_config.json 을 다시 읽어 repository / services 설정을 갱신한다. */
    public synchronized void reload() {
        if (!configFile.isFile()) {
            log.warn("service_config.json 없음({}) — 리포지토리 미설정 상태로 기동", configFile.getPath());
            this.repository = new RepositoryConfig();
            this.services = new ServicesBlock();
            return;
        }
        try {
            JsonNode root = objectMapper.readTree(configFile);
            JsonNode repoNode = root.get("repository");
            this.repository = (repoNode == null)
                    ? new RepositoryConfig()
                    : objectMapper.treeToValue(repoNode, RepositoryConfig.class);
            JsonNode svcNode = root.get("services");
            this.services = (svcNode == null)
                    ? new ServicesBlock()
                    : objectMapper.treeToValue(svcNode, ServicesBlock.class);
        } catch (IOException e) {
            log.error("service_config.json 파싱 실패({}) — 미설정 상태로 폴백", configFile.getPath(), e);
            this.repository = new RepositoryConfig();
            this.services = new ServicesBlock();
        }
    }

    public RepositoryConfig repository() {
        return repository;
    }

    public ServicesBlock services() {
        return services;
    }

    public boolean isRepositoryConfigured() {
        return repository.isConfigured();
    }
}
