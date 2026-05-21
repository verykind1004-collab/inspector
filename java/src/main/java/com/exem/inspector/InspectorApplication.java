package com.exem.inspector;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration;

/**
 * MaxGauge Inspector 애플리케이션 진입점.
 *
 * <p>리포지토리 접속 정보는 service_config.json 에서 런타임에 동적으로 읽으므로
 * Spring Boot 기본 DataSource 자동설정을 제외한다(부팅 시 DB 미연결 허용).
 * 동적 DataSource 구성은 공통 인프라 단계에서 추가한다.
 */
@SpringBootApplication(exclude = DataSourceAutoConfiguration.class)
public class InspectorApplication {

    public static void main(String[] args) {
        SpringApplication.run(InspectorApplication.class, args);
    }
}
