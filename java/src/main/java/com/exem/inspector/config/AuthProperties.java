package com.exem.inspector.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 인증 설정(기존 auth.py 상수 외부화).
 *
 * <p>관리자 계정은 고정 자격증명: id=admin-user, SHA-256(salt + 비밀번호) == admin-hash.
 * 기본값은 auth.py 와 동일하며 application.yml 로 재정의할 수 있다.
 *
 * <p>보안개선 TODO: 고정 SHA-256(salt) → BCrypt 등 적응형 해시로 전환 검토(auth.py 대비 강화).
 */
@ConfigurationProperties(prefix = "inspector.auth")
public class AuthProperties {

    private String adminUser = "maxgauge";
    private String salt = "mxg_inspector_salt_v1";
    private String adminHash = "ffb3ac5ee5445547dc04b542cf7d329efeb0178de4148c2ec8a9a877fb3ed316";

    public String getAdminUser() {
        return adminUser;
    }

    public void setAdminUser(String adminUser) {
        this.adminUser = adminUser;
    }

    public String getSalt() {
        return salt;
    }

    public void setSalt(String salt) {
        this.salt = salt;
    }

    public String getAdminHash() {
        return adminHash;
    }

    public void setAdminHash(String adminHash) {
        this.adminHash = adminHash;
    }
}
