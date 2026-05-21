package com.exem.inspector.config;

import java.util.Properties;

import org.apache.ibatis.mapping.DatabaseIdProvider;
import org.apache.ibatis.mapping.VendorDatabaseIdProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import com.exem.inspector.common.db.DbType;

/**
 * DB 벤더 분기 공통 설정.
 *
 * <p>매퍼 XML 은 databaseId 로 Oracle/PG 를 분기한다(I절 규약 — 화면 코드에 분기를 흩뿌리지 않음).
 * JDBC DatabaseMetaData 의 제품명을 {@link DbType} 의 databaseId 키로 매핑한다.
 */
@Configuration
public class DatabaseConfig {

    @Bean
    public DatabaseIdProvider databaseIdProvider() {
        VendorDatabaseIdProvider provider = new VendorDatabaseIdProvider();
        Properties props = new Properties();
        props.setProperty("Oracle", DbType.ORACLE.databaseId());
        props.setProperty("PostgreSQL", DbType.POSTGRESQL.databaseId());
        provider.setProperties(props);
        return provider;
    }
}
