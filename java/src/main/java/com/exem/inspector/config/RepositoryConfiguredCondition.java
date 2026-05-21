package com.exem.inspector.config;

import java.io.File;

import org.springframework.context.annotation.Condition;
import org.springframework.context.annotation.ConditionContext;
import org.springframework.core.type.AnnotatedTypeMetadata;

import com.exem.inspector.common.db.RepositoryConfig;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * 리포지토리가 설정되어 있을 때만 DataSource 빈을 등록하기 위한 조건.
 *
 * <p>빈 생성 전(조건 평가) 단계라 {@link ServiceConfig} 빈을 쓸 수 없어 파일을 직접 읽는다.
 * 미설정이면 DataSource 빈을 아예 등록하지 않아 MyBatis 자동설정이 backoff 하고 부팅이 통과한다.
 */
public class RepositoryConfiguredCondition implements Condition {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Override
    public boolean matches(ConditionContext context, AnnotatedTypeMetadata metadata) {
        String path = context.getEnvironment().getProperty("inspector.service-config-path");
        if (path == null) {
            return false;
        }
        File file = new File(path);
        if (!file.isFile()) {
            return false;
        }
        try {
            JsonNode repo = MAPPER.readTree(file).get("repository");
            if (repo == null) {
                return false;
            }
            return MAPPER.treeToValue(repo, RepositoryConfig.class).isConfigured();
        } catch (Exception e) {
            return false;
        }
    }
}
