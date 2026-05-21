package com.exem.inspector.security;

import java.util.HashMap;
import java.util.Map;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.http.HttpSession;

import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.AnonymousAuthenticationToken;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/**
 * 인증 엔드포인트(auth.py 대응).
 *
 * <p>로그인은 폼 리다이렉트가 아닌 JSON API(기존 동작 유지). 인증 성공 시 세션에 컨텍스트를 저장한다.
 * check-auth/whoami 는 nginx auth_request 연동용이다.
 */
@RestController
public class AuthController {

    private final AuthenticationManager authenticationManager;
    private final SecurityContextRepository contextRepository = new HttpSessionSecurityContextRepository();

    public AuthController(AuthenticationManager authenticationManager) {
        this.authenticationManager = authenticationManager;
    }

    @PostMapping("/labs/api/login")
    public ResponseEntity<Map<String, Object>> login(@RequestBody LoginRequest req,
                                                      HttpServletRequest request,
                                                      HttpServletResponse response) {
        try {
            Authentication auth = authenticationManager.authenticate(
                    new UsernamePasswordAuthenticationToken(req.getId(), req.getPassword()));

            SecurityContext context = SecurityContextHolder.createEmptyContext();
            context.setAuthentication(auth);
            SecurityContextHolder.setContext(context);
            contextRepository.saveContext(context, request, response); // 세션에 저장

            Map<String, Object> body = new HashMap<>();
            body.put("ok", true);
            body.put("id", auth.getName());
            body.put("role", roleOf(auth));
            return ResponseEntity.ok(body);
        } catch (AuthenticationException e) {
            Map<String, Object> body = new HashMap<>();
            body.put("ok", false);
            body.put("error", "인증 실패");
            return ResponseEntity.status(HttpServletResponse.SC_UNAUTHORIZED).body(body);
        }
    }

    @PostMapping("/labs/api/logout")
    public ResponseEntity<Void> logout(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        if (session != null) {
            session.invalidate();
        }
        SecurityContextHolder.clearContext();
        return ResponseEntity.noContent().build();
    }

    /** 게이트웨이(nginx auth_request)용: 인증되면 204, 아니면 401. */
    @GetMapping("/labs/api/check-auth")
    public ResponseEntity<Void> checkAuth() {
        return ResponseEntity.status(isAuthenticated()
                ? HttpServletResponse.SC_NO_CONTENT
                : HttpServletResponse.SC_UNAUTHORIZED).build();
    }

    /** 항상 200. 인증 여부와 사용자 정보를 반환한다. */
    @GetMapping("/labs/api/whoami")
    public Map<String, Object> whoami() {
        Map<String, Object> body = new HashMap<>();
        boolean authenticated = isAuthenticated();
        body.put("authenticated", authenticated);
        if (authenticated) {
            Authentication auth = SecurityContextHolder.getContext().getAuthentication();
            body.put("id", auth.getName());
            body.put("role", roleOf(auth));
        }
        return body;
    }

    private static boolean isAuthenticated() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        return auth != null && auth.isAuthenticated() && !(auth instanceof AnonymousAuthenticationToken);
    }

    private static String roleOf(Authentication auth) {
        return auth.getAuthorities().iterator().next().getAuthority()
                .replaceFirst("^ROLE_", "").toLowerCase();
    }
}
