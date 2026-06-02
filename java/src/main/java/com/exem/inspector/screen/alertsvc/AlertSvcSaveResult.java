package com.exem.inspector.screen.alertsvc;

import java.util.List;

/**
 * Alert Service save 응답 — 원본 {@code api_alert_svc_save} 의 {@code {ok, results: [string]}} 와 1:1 동등.
 */
public class AlertSvcSaveResult {

    private final List<String> results;

    public AlertSvcSaveResult(List<String> results) {
        this.results = results;
    }

    public List<String> getResults() { return results; }
}
