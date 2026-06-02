package com.exem.inspector.common.db;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * service_config.json 의 repository 블록 매핑.
 *
 * <p>리포지토리(MaxGauge 저장소) DB 접속정보. sid 는 Oracle 에선 service_name,
 * PG 에선 dbname 으로 쓰인다(db_utils.py 사양).
 * pg_data_dir 은 overview Disk 카드 표시용 — 접속 자체에는 사용하지 않는다.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public class RepositoryConfig {

    @JsonProperty("db_type")
    private String dbType = "";

    @JsonProperty("ip")
    private String ip = "";

    @JsonProperty("port")
    private String port = "";

    @JsonProperty("user")
    private String user = "";

    @JsonProperty("password")
    private String password = "";

    @JsonProperty("sid")
    private String sid = "";

    /** PG 운영 시 데이터 디렉토리 — overview Disk 카드 산정 기준 경로(원본 _disk_for_overview 와 동등). */
    @JsonProperty("pg_data_dir")
    private String pgDataDir = "";

    public String dbType() {
        return dbType;
    }

    public String ip() {
        return ip;
    }

    /** 포트. 빈 값이면 0 을 반환한다(호출측이 DbType 기본 포트로 대체). */
    public int port() {
        if (port == null || port.trim().isEmpty()) {
            return 0;
        }
        return Integer.parseInt(port.trim());
    }

    public String user() {
        return user;
    }

    public String password() {
        return password;
    }

    public String sid() {
        return sid;
    }

    public String pgDataDir() {
        return pgDataDir == null ? "" : pgDataDir.trim();
    }

    /**
     * 접속 가능한 최소 설정이 채워졌는지 여부.
     *
     * <p>db_type/ip/user/sid 가 모두 있어야 한다(password 는 PG 에서 생략 가능 — db_utils.py 사양).
     */
    public boolean isConfigured() {
        return notBlank(dbType) && notBlank(ip) && notBlank(user) && notBlank(sid);
    }

    private static boolean notBlank(String s) {
        return s != null && !s.trim().isEmpty();
    }
}
