package com.exem.inspector.screen.auth;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * apm_user_list 조회 — auth.py {@code _fetch_user_row} 1:1.
 *
 * <p>존재하지 않으면 {@code null} 반환. 호출자가 BadCredentials 로 변환.
 */
@Mapper
public interface ApmUserListMapper {

    ApmUserRow findByUserId(@Param("userId") String userId);
}
