package com.exem.inspector.common.db;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

/**
 * DbType 판별/URL 빌더 검증(DB 불요 순수 로직).
 */
class DbTypeTest {

    @Test
    void db_type_문자열을_부분일치로_판별한다() {
        assertThat(DbType.fromConfigValue("Oracle")).isEqualTo(DbType.ORACLE);
        assertThat(DbType.fromConfigValue("PostgreSQL")).isEqualTo(DbType.POSTGRESQL);
        assertThat(DbType.fromConfigValue("oracle 19c")).isEqualTo(DbType.ORACLE);
    }

    @Test
    void 미지원_db_type_은_예외() {
        assertThatThrownBy(() -> DbType.fromConfigValue("mysql"))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> DbType.fromConfigValue(null))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void Oracle_은_service_name_방식_URL() {
        assertThat(DbType.ORACLE.jdbcUrl("10.10.45.68", 1521, "ORA19"))
                .isEqualTo("jdbc:oracle:thin:@//10.10.45.68:1521/ORA19");
    }

    @Test
    void PG_는_dbname_방식_URL() {
        assertThat(DbType.POSTGRESQL.jdbcUrl("127.0.0.1", 5432, "postgres"))
                .isEqualTo("jdbc:postgresql://127.0.0.1:5432/postgres");
    }

    @Test
    void 기본_포트가_벤더별로_다르다() {
        assertThat(DbType.ORACLE.defaultPort()).isEqualTo(1521);
        assertThat(DbType.POSTGRESQL.defaultPort()).isEqualTo(5432);
    }
}
