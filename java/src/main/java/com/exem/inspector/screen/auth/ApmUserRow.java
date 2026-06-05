package com.exem.inspector.screen.auth;

/**
 * apm_user_list 의 password / is_locked 행 — auth.py {@code _fetch_user_row} 의 row_dict 와 1:1.
 *
 * <p>{@code password} 는 DGServer 로 암호화된 문자열이라 인증 시 복호화 후 평문 비교한다.
 */
public class ApmUserRow {

    private String password;
    private Integer isLocked;

    public String getPassword() { return password; }
    public void setPassword(String password) { this.password = password; }

    public Integer getIsLocked() { return isLocked; }
    public void setIsLocked(Integer isLocked) { this.isLocked = isLocked; }
}
