package com.exem.inspector.screen.alertsvc;

/**
 * Alert Service 종류 — 원본 alert_svc_config.py 의 {@code kind ∈ {sms, api, mail}} 와 1:1 동등.
 *
 * <p>이름(소문자)이 그대로 파일명 prefix 가 된다(예: sms → {@code sms.xml} / {@code sample_sms.xml}).
 */
public enum AlertSvcKind {
    SMS, API, MAIL;

    /** 소문자(파일명 prefix). 원본 path join 호환. */
    public String lower() {
        return name().toLowerCase();
    }

    /** 라우트/요청 본문의 kind 문자열 → enum. 미지원 값은 null. */
    public static AlertSvcKind fromString(String s) {
        if (s == null) return null;
        switch (s.trim().toLowerCase()) {
            case "sms":  return SMS;
            case "api":  return API;
            case "mail": return MAIL;
            default:     return null;
        }
    }
}
