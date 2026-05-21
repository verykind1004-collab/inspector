package com.exem.inspector.config;

import javax.servlet.http.HttpServletResponse;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.ProviderManager;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;

import com.exem.inspector.security.AdminAuthenticationProvider;

/**
 * 보안 일괄 설정(I절 규약 — 화면별 수동 인증 체크 금지).
 *
 * <p>공개 경로(헬스/게이트웨이 인증확인/로그인)를 제외한 모든 요청은 인증을 요구한다.
 * nginx auth_request 연동을 위해 미인증은 리다이렉트가 아닌 401 로 응답한다.
 *
 * <p>세션 만료 주의: Spring 세션 타임아웃은 idle 기준이다. auth.py 는 절대 만료(3600초, 슬라이딩 없음)이므로
 * 절대 만료를 보장하려면 세션 생성시각 기반 커스텀 검증 필터가 필요하다 — TODO.
 */
@Configuration
@EnableWebSecurity
@EnableConfigurationProperties(AuthProperties.class)
public class SecurityConfig {

    /** 인증 없이 접근 가능한 경로(auth.py public + 로그인 엔드포인트). */
    private static final String[] PUBLIC_PATHS = {
            "/api/ping",
            "/labs/api/whoami",
            "/labs/api/check-auth",
            "/labs/api/login",
            "/labs/api/logout"
    };

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            .csrf().disable() // JSON API + nginx 게이트 구조. CSRF 정책은 프론트 확정 후 재검토 — TODO
            .authorizeHttpRequests(registry -> registry
                    .antMatchers(PUBLIC_PATHS).permitAll()
                    .anyRequest().authenticated())
            .exceptionHandling(handling -> handling
                    .authenticationEntryPoint((request, response, ex) ->
                            response.sendError(HttpServletResponse.SC_UNAUTHORIZED)))
            .sessionManagement(session -> session
                    .sessionCreationPolicy(SessionCreationPolicy.IF_REQUIRED))
            .formLogin().disable()
            .httpBasic().disable()
            .logout().disable();
        return http.build();
    }

    @Bean
    public AuthenticationManager authenticationManager(AdminAuthenticationProvider adminProvider) {
        // 현재는 관리자 경로만. DB 사용자 경로 provider 는 리포지토리 설정 이후 추가한다.
        return new ProviderManager(adminProvider);
    }
}
