package com.exem.inspector.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;

import com.exem.inspector.config.AuthProperties;

/**
 * 관리자 인증 경로(auth.py 경로 A) 검증.
 */
class AdminAuthenticationProviderTest {

    private static final String SALT = "mxg_inspector_salt_v1";
    private static final String PASSWORD = "secret123";

    private AdminAuthenticationProvider provider;

    @BeforeEach
    void setUp() {
        AuthProperties props = new AuthProperties();
        props.setAdminUser("maxgauge");
        props.setSalt(SALT);
        props.setAdminHash(AdminAuthenticationProvider.sha256(SALT + PASSWORD));
        provider = new AdminAuthenticationProvider(props);
    }

    @Test
    void 올바른_관리자_자격증명이면_ENGINEER_권한() {
        Authentication result = provider.authenticate(
                new UsernamePasswordAuthenticationToken("maxgauge", PASSWORD));
        assertThat(result.getAuthorities())
                .extracting("authority")
                .containsExactly("ROLE_ENGINEER");
    }

    @Test
    void 비밀번호가_틀리면_BadCredentials() {
        assertThatThrownBy(() -> provider.authenticate(
                new UsernamePasswordAuthenticationToken("maxgauge", "wrong")))
                .isInstanceOf(BadCredentialsException.class);
    }

    @Test
    void 관리자가_아닌_id는_위임을_위해_null_반환() {
        Authentication result = provider.authenticate(
                new UsernamePasswordAuthenticationToken("alice", PASSWORD));
        assertThat(result).isNull();
    }
}
