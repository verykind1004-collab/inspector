package com.exem.inspector.screen.maxspace.dto;

/**
 * apm_user_list 의 seq + admin_role 한 행.
 * 원본 tablespace_server.py::_fetch_user_dbids 의 첫 조회 1:1.
 */
public class UserAdminRow {

    private Long seq;
    private Integer adminRole;

    public Long getSeq() { return seq; }
    public void setSeq(Long seq) { this.seq = seq; }

    public Integer getAdminRole() { return adminRole; }
    public void setAdminRole(Integer adminRole) { this.adminRole = adminRole; }
}
