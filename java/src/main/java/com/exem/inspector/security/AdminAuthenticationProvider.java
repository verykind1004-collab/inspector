package com.exem.inspector.security;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Collections;

import org.springframework.security.authentication.AuthenticationProvider;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.stereotype.Component;

import com.exem.inspector.config.AuthProperties;

/**
 * 관리자 인증 경로 — auth.py 경로 A.
 *
 * <p>id == 관리자 계정 AND SHA-256(salt + 비밀번호) == 고정 해시 → ROLE_ENGINEER.
 * 관리자 계정이 아니면 {@code null} 을 반환해 다음 provider(추후 DB 사용자 경로)에 위임한다.
 *
 * <p>미구현 TODO — auth.py 경로 B(DB 사용자):
 * apm_user_list(user_id/password/is_locked) 조회 + DGServer.jar 복호화 비교 → ROLE_USER.
 * 복호화는 jar 서브프로세스 의존이라, 보안개선(복호화 in-process 이식)을 위해 알고리즘 분석이 선행되어야 한다.
 * DataSource 가 필요하므로 리포지토리 설정 이후 별도 provider 로 추가한다.
 */
@Component
public class AdminAuthenticationProvider implements AuthenticationProvider {

    private final AuthProperties props;

    public AdminAuthenticationProvider(AuthProperties props) {
        this.props = props;
    }

    @Override
    public Authentication authenticate(Authentication authentication) throws AuthenticationException {
        String id = authentication.getName();
        if (!props.getAdminUser().equals(id)) {
            return null; // 관리자 계정 아님 → 위임(현재는 후속 provider 없음 = 미지원)
        }
        String password = String.valueOf(authentication.getCredentials());
        if (!sha256(props.getSalt() + password).equals(props.getAdminHash())) {
            throw new BadCredentialsException("자격 증명이 일치하지 않습니다");
        }
        return new UsernamePasswordAuthenticationToken(
                id, null,
                Collections.singletonList(new SimpleGrantedAuthority("ROLE_ENGINEER")));
    }

    @Override
    public boolean supports(Class<?> authentication) {
        return UsernamePasswordAuthenticationToken.class.isAssignableFrom(authentication);
    }

    /** SHA-256 16진 소문자 해시(auth.py 와 동일 알고리즘). */
    static String sha256(String text) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(text.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(digest.length * 2);
            for (byte b : digest) {
                sb.append(Character.forDigit((b >> 4) & 0xF, 16));
                sb.append(Character.forDigit(b & 0xF, 16));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 미지원 환경", e);
        }
    }
}
