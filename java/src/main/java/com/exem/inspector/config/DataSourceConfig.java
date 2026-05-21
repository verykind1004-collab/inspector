package com.exem.inspector.config;

import javax.sql.DataSource;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Conditional;
import org.springframework.context.annotation.Configuration;

import com.exem.inspector.common.db.DbType;
import com.exem.inspector.common.db.RepositoryConfig;
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;

/**
 * 리포지토리 DataSource 구성.
 *
 * <p>service_config.json 의 접속정보로 HikariCP 풀을 만든다(I절 규약 — 화면이 커넥션을 직접 열지 않음).
 * 미설정이면 DataSource 를 만들지 않아 부팅을 막지 않는다(MyBatis 는 DataSource 부재 시 자동 backoff).
 * DB 가 미가동이어도 부팅은 통과하고 첫 쿼리 시점에 연결한다(initializationFailTimeout=-1).
 *
 * <p>참고: 현재는 단일 풀이다. 수집/조회 풀 분리는 부하 검증 시점에 도입한다(투기적 분리 지양 — 헌법 A.2).
 */
@Configuration
public class DataSourceConfig {

    private static final Logger log = LoggerFactory.getLogger(DataSourceConfig.class);

    @Bean
    @Conditional(RepositoryConfiguredCondition.class)
    public DataSource dataSource(ServiceConfig serviceConfig) {
        // 미설정이면 조건이 false 라 이 메서드가 호출되지 않는다(DataSource 빈 미등록 → MyBatis backoff).
        RepositoryConfig repo = serviceConfig.repository();
        DbType dbType = DbType.fromConfigValue(repo.dbType());
        int port = (repo.port() > 0) ? repo.port() : dbType.defaultPort();

        HikariConfig hc = new HikariConfig();
        hc.setPoolName("inspector-repo");
        hc.setDriverClassName(dbType.driverClassName());
        hc.setJdbcUrl(dbType.jdbcUrl(repo.ip(), port, repo.sid()));
        hc.setUsername(repo.user());
        hc.setPassword(repo.password());
        hc.setMaximumPoolSize(10);
        hc.setConnectionTimeout(30_000);          // 조회 타임아웃 30초(db_utils.py 사양)
        hc.setInitializationFailTimeout(-1);       // DB 미가동이어도 부팅 허용

        log.info("리포지토리 DataSource 구성: {} {}", dbType, dbType.jdbcUrl(repo.ip(), port, repo.sid()));
        return new HikariDataSource(hc);
    }
}
