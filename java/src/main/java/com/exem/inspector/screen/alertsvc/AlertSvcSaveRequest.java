package com.exem.inspector.screen.alertsvc;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

/**
 * Alert Service save 요청 본문 — 원본 {@code api_alert_svc_save} 입력과 동등.
 *
 * <p>{@code activate} 는 3-state: true/false/null(미지정 — 현재 활성/비활성 상태 유지).
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public class AlertSvcSaveRequest {

    private String kind;
    private String svcDir;
    private Boolean activate;
    private String rawXml;

    public String getKind() { return kind; }
    public void setKind(String kind) { this.kind = kind; }

    /** JSON 키 호환: {@code svc_dir}. */
    @com.fasterxml.jackson.annotation.JsonProperty("svc_dir")
    public String getSvcDir() { return svcDir; }
    @com.fasterxml.jackson.annotation.JsonProperty("svc_dir")
    public void setSvcDir(String svcDir) { this.svcDir = svcDir; }

    public Boolean getActivate() { return activate; }
    public void setActivate(Boolean activate) { this.activate = activate; }

    /** JSON 키 호환: {@code raw_xml}. */
    @com.fasterxml.jackson.annotation.JsonProperty("raw_xml")
    public String getRawXml() { return rawXml; }
    @com.fasterxml.jackson.annotation.JsonProperty("raw_xml")
    public void setRawXml(String rawXml) { this.rawXml = rawXml; }
}
