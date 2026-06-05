package com.exem.inspector.security;

import java.util.Collections;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.security.authentication.AuthenticationProvider;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.LockedException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.stereotype.Component;

import com.exem.inspector.screen.auth.ApmUserListMapper;
import com.exem.inspector.screen.auth.ApmUserRow;

/**
 * 일반 사용자 인증 — auth.py {@code verify_credential} 경로 B (1:1).
 *
 * <p>흐름:
 * <ol>
 *   <li>repository DB.apm_user_list 에서 user_id 조회 (없으면 BadCredentials)</li>
 *   <li>is_locked != 0 이면 LockedException</li>
 *   <li>{@link DgsDecryptService} 로 password 복호화 후 평문 비교</li>
 *   <li>성공 시 ROLE_USER</li>
 * </ol>
 */
@Component
public class RepositoryUserAuthenticationProvider implements AuthenticationProvider {

    private static final Logger log = LoggerFactory.getLogger(RepositoryUserAuthenticationProvider.class);

    private final ObjectProvider<ApmUserListMapper> mapperProvider;
    private final DgsDecryptService dgsDecryptService;

    public RepositoryUserAuthenticationProvider(ObjectProvider<ApmUserListMapper> mapperProvider,
                                                DgsDecryptService dgsDecryptService) {
        this.mapperProvider = mapperProvider;
        this.dgsDecryptService = dgsDecryptService;
    }

    @Override
    public Authentication authenticate(Authentication authentication) throws AuthenticationException {
        String userId = (authentication.getName() == null ? "" : authentication.getName()).trim();
        String password = String.valueOf(authentication.getCredentials());

        ApmUserListMapper mapper = mapperProvider.getIfAvailable();
        if (mapper == null) {
            log.warn("apm_user_list mapper unavailable — repository may be unconfigured");
            throw new BadCredentialsException("자격 증명이 일치하지 않습니다");
        }

        ApmUserRow row;
        try {
            row = mapper.findByUserId(userId);
        } catch (RuntimeException e) {
            log.warn("apm_user_list 조회 실패: userId={}", userId, e);
            throw new BadCredentialsException("자격 증명이 일치하지 않습니다");
        }
        if (row == null) {
            throw new BadCredentialsException("자격 증명이 일치하지 않습니다");
        }
        if (row.getIsLocked() != null && row.getIsLocked() != 0) {
            throw new LockedException("계정이 잠겼습니다");
        }

        String plain = dgsDecryptService.decrypt(row.getPassword());
        if (plain == null) {
            log.warn("password 복호화 실패: userId={}", userId);
            throw new BadCredentialsException("자격 증명이 일치하지 않습니다");
        }
        if (!plain.equals(password)) {
            throw new BadCredentialsException("자격 증명이 일치하지 않습니다");
        }

        return new UsernamePasswordAuthenticationToken(
                userId, null,
                Collections.singletonList(new SimpleGrantedAuthority("ROLE_USER")));
    }

    @Override
    public boolean supports(Class<?> authentication) {
        return UsernamePasswordAuthenticationToken.class.isAssignableFrom(authentication);
    }
}
