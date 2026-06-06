package com.exem.inspector.screen.maxspace;

import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import org.apache.ibatis.session.SqlSession;
import org.apache.ibatis.session.SqlSessionFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;

import com.exem.inspector.screen.maxspace.dto.UserAdminRow;

/**
 * MaxSpace 권한 결정 — 현재 인증된 사용자가 볼 수 있는 instance db_id 집합을 반환.
 *
 * <p>원본 tablespace_server.py::_fetch_user_dbids 1:1. Inspector BE 통합 환경에선 cookie →
 * /labs/api/whoami 호출 대신 Spring Security {@link SecurityContextHolder} 활용.
 *
 * <p>매핑:
 * <ul>
 *   <li>ROLE_ENGINEER (AdminAuthenticationProvider — maxgauge 계정) → allAllowed=true (전체)</li>
 *   <li>ROLE_USER (RepositoryUserAuthenticationProvider — apm_user_list) → username 으로
 *       apm_user_list.admin_role 조회:
 *       <ul>
 *         <li>admin_role &gt;= 2 → allAllowed=true</li>
 *         <li>그 외 → apm_users_db_list 의 db_id NOT IN ('0','9999') + role1~6 중 하나 ≥ 1 인 db_id 만</li>
 *       </ul></li>
 *   <li>미인증 → allAllowed=false, dbids=∅ (안전 측 — 데이터 전부 가려짐)</li>
 * </ul>
 */
@Service
public class MaxSpacePermissionService {

    private static final Logger log = LoggerFactory.getLogger(MaxSpacePermissionService.class);

    private final ObjectProvider<SqlSessionFactory> sqlSessionFactoryProvider;

    public MaxSpacePermissionService(ObjectProvider<SqlSessionFactory> sqlSessionFactoryProvider) {
        this.sqlSessionFactoryProvider = sqlSessionFactoryProvider;
    }

    /**
     * 현재 사용자의 권한 결과. allAllowed=true 이면 dbids 무시.
     */
    public static final class Permission {
        public final boolean allAllowed;
        public final Set<Integer> dbIds;

        public Permission(boolean allAllowed, Set<Integer> dbIds) {
            this.allAllowed = allAllowed;
            this.dbIds = dbIds == null ? Collections.emptySet() : dbIds;
        }

        public static Permission denyAll() {
            return new Permission(false, Collections.emptySet());
        }

        public static Permission allowAll() {
            return new Permission(true, Collections.emptySet());
        }
    }

    public Permission resolveCurrent() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !auth.isAuthenticated()) {
            return Permission.denyAll();
        }
        boolean isEngineer = hasRole(auth, "ROLE_ENGINEER");
        if (isEngineer) {
            return Permission.allowAll();
        }
        boolean isUser = hasRole(auth, "ROLE_USER");
        if (!isUser) {
            return Permission.denyAll();
        }
        String userId = auth.getName();
        if (userId == null || userId.trim().isEmpty()) {
            return Permission.denyAll();
        }
        return resolveByUserId(userId.trim());
    }

    private Permission resolveByUserId(String userId) {
        SqlSessionFactory factory = sqlSessionFactoryProvider.getIfAvailable();
        if (factory == null) {
            log.warn("[maxspace.perm] Repository 미구성 — 권한 결정 불가, 차단");
            return Permission.denyAll();
        }
        try (SqlSession session = factory.openSession()) {
            MaxSpaceMapper mapper = session.getMapper(MaxSpaceMapper.class);
            UserAdminRow row = mapper.findUserSeqAndAdminRole(userId);
            if (row == null || row.getSeq() == null) {
                return Permission.denyAll();
            }
            int adminRole = row.getAdminRole() == null ? 0 : row.getAdminRole();
            if (adminRole >= 2) {
                return Permission.allowAll();
            }
            List<Integer> ids = mapper.findUserAllowedDbIds(row.getSeq());
            if (ids == null || ids.isEmpty()) {
                return new Permission(false, Collections.emptySet());
            }
            return new Permission(false, new HashSet<>(ids));
        } catch (Exception e) {
            log.warn("[maxspace.perm] dbid 조회 실패 ({}), 차단", userId, e);
            return Permission.denyAll();
        }
    }

    private static boolean hasRole(Authentication auth, String role) {
        if (auth.getAuthorities() == null) {
            return false;
        }
        for (GrantedAuthority a : auth.getAuthorities()) {
            if (role.equals(a.getAuthority())) {
                return true;
            }
        }
        return false;
    }
}
