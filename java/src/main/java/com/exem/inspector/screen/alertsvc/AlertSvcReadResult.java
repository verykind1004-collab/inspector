package com.exem.inspector.screen.alertsvc;

import java.util.List;

/**
 * Alert Service read 응답 페이로드 — kind + 모든 DGServer_S 의 설정 리스트.
 *
 * <p>원본 {@code api_alert_svc_read} 의 {@code {ok, kind, results}} 와 1:1 동등(ok 봉투는 표준 ApiResponse).
 */
public class AlertSvcReadResult {

    private final String kind;
    private final List<AlertSvcEntry> results;

    public AlertSvcReadResult(String kind, List<AlertSvcEntry> results) {
        this.kind = kind;
        this.results = results;
    }

    public String getKind() { return kind; }
    public List<AlertSvcEntry> getResults() { return results; }
}
