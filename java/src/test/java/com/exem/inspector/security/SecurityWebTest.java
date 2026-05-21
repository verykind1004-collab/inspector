package com.exem.inspector.security;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

/**
 * 보안 필터 체인 동작 검증 — 공개/보호 경로, 게이트웨이 인증확인.
 */
@SpringBootTest
@AutoConfigureMockMvc
class SecurityWebTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void ping은_인증없이_공개() throws Exception {
        mockMvc.perform(get("/api/ping")).andExpect(status().isOk());
    }

    @Test
    void whoami는_미인증이어도_200() throws Exception {
        mockMvc.perform(get("/labs/api/whoami")).andExpect(status().isOk());
    }

    @Test
    void check_auth는_미인증이면_401() throws Exception {
        mockMvc.perform(get("/labs/api/check-auth")).andExpect(status().isUnauthorized());
    }

    @Test
    void 보호된_경로는_미인증이면_401() throws Exception {
        mockMvc.perform(get("/internal/anything")).andExpect(status().isUnauthorized());
    }
}
