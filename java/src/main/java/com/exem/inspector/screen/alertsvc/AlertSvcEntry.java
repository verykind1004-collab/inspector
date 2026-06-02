package com.exem.inspector.screen.alertsvc;

import java.util.Map;

/**
 * DGServer 인스턴스 한 곳의 Alert Service 설정 한 단위(read API 결과 원소).
 *
 * <p>원본 {@code api_alert_svc_read} 응답의 results[i] 와 1:1 동등.
 */
public class AlertSvcEntry {

    private final String dgserver;
    private final String svcDir;
    private final boolean active;
    private final String xmlPath;
    private final Map<String, Object> config;
    private final Map<String, String> binds;
    private final Map<String, String> headers;
    private final String raw;

    public AlertSvcEntry(String dgserver, String svcDir, boolean active, String xmlPath,
                         Map<String, Object> config, Map<String, String> binds,
                         Map<String, String> headers, String raw) {
        this.dgserver = dgserver;
        this.svcDir = svcDir;
        this.active = active;
        this.xmlPath = xmlPath;
        this.config = config;
        this.binds = binds;
        this.headers = headers;
        this.raw = raw;
    }

    public String getDgserver() { return dgserver; }
    public String getSvcDir() { return svcDir; }
    public boolean isActive() { return active; }
    public String getXmlPath() { return xmlPath; }
    public Map<String, Object> getConfig() { return config; }
    public Map<String, String> getBinds() { return binds; }
    public Map<String, String> getHeaders() { return headers; }
    public String getRaw() { return raw; }
}
