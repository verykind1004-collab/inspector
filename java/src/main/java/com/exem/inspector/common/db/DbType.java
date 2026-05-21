package com.exem.inspector.common.db;

/**
 * 지원 DB 벤더.
 *
 * <p>값(databaseId)은 MyBatis databaseId 와 일치시킨다 — 매퍼 XML 의 Oracle/PG 분기 키.
 */
public enum DbType {

    ORACLE("oracle", 1521, "oracle.jdbc.OracleDriver"),
    POSTGRESQL("postgresql", 5432, "org.postgresql.Driver");

    private final String databaseId;
    private final int defaultPort;
    private final String driverClassName;

    DbType(String databaseId, int defaultPort, String driverClassName) {
        this.databaseId = databaseId;
        this.defaultPort = defaultPort;
        this.driverClassName = driverClassName;
    }

    /** MyBatis databaseId (매퍼 XML 분기 키). */
    public String databaseId() {
        return databaseId;
    }

    /** 미지정 시 사용할 기본 포트. */
    public int defaultPort() {
        return defaultPort;
    }

    /** JDBC 드라이버 클래스명. */
    public String driverClassName() {
        return driverClassName;
    }

    /**
     * service_config.json 의 db_type 값을 판별한다.
     *
     * <p>기존 db_utils.py 사양과 동일하게 부분일치(소문자 포함)로 판단한다.
     */
    public static DbType fromConfigValue(String dbTypeRaw) {
        String v = (dbTypeRaw == null) ? "" : dbTypeRaw.toLowerCase();
        if (v.contains("oracle")) {
            return ORACLE;
        }
        if (v.contains("postgres")) {
            return POSTGRESQL;
        }
        throw new IllegalArgumentException("지원하지 않는 db_type: " + dbTypeRaw);
    }

    /**
     * JDBC 접속 URL 을 만든다.
     *
     * <p>Oracle 은 service_name(=sid 필드), PG 는 dbname(=sid 필드)으로 매핑한다(db_utils.py 사양).
     */
    public String jdbcUrl(String host, int port, String database) {
        switch (this) {
            case ORACLE:
                return "jdbc:oracle:thin:@//" + host + ":" + port + "/" + database;
            case POSTGRESQL:
                return "jdbc:postgresql://" + host + ":" + port + "/" + database;
            default:
                throw new IllegalStateException("URL 미정의: " + this);
        }
    }
}
