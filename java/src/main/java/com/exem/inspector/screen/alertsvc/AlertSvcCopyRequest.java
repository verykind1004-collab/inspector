package com.exem.inspector.screen.alertsvc;

import java.util.ArrayList;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Alert Service copy 요청 — 원본 {@code api_alert_svc_copy} 입력과 동등.
 *
 * <p>여러 target DGServer 에 동일 XML 을 일괄 복사(백업 후). {@code activate} 3-state.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public class AlertSvcCopyRequest {

    private String kind;

    @JsonProperty("raw_xml")
    private String rawXml;

    @JsonProperty("target_svc_dirs")
    private List<String> targetSvcDirs = new ArrayList<>();

    private Boolean activate;

    public String getKind() { return kind; }
    public void setKind(String kind) { this.kind = kind; }

    public String getRawXml() { return rawXml; }
    public void setRawXml(String rawXml) { this.rawXml = rawXml; }

    public List<String> getTargetSvcDirs() {
        return targetSvcDirs == null ? new ArrayList<>() : targetSvcDirs;
    }
    public void setTargetSvcDirs(List<String> dirs) { this.targetSvcDirs = dirs; }

    public Boolean getActivate() { return activate; }
    public void setActivate(Boolean activate) { this.activate = activate; }
}
