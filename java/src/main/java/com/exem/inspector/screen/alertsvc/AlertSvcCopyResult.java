package com.exem.inspector.screen.alertsvc;

import java.util.List;

/**
 * Alert Service copy 응답 — 원본 {@code api_alert_svc_copy} 의 {@code {ok, results}} 와 1:1 동등.
 *
 * <p>{@code ok} 는 모든 target 이 status="ok" 일 때만 true(전체 결과 봉투는 표준 ApiResponse).
 */
public class AlertSvcCopyResult {

    private final boolean allOk;
    private final List<Item> results;

    public AlertSvcCopyResult(boolean allOk, List<Item> results) {
        this.allOk = allOk;
        this.results = results;
    }

    public boolean isAllOk() { return allOk; }
    public List<Item> getResults() { return results; }

    /** 단일 target 결과 — 원본 results[i] 항목과 동등. */
    public static final class Item {
        private final String svcDir;
        private final String status; // "ok" / "error"
        private final String file;
        private final String backup;
        private final String message;

        public Item(String svcDir, String status, String file, String backup, String message) {
            this.svcDir = svcDir;
            this.status = status;
            this.file = file;
            this.backup = backup;
            this.message = message;
        }

        public String getSvcDir() { return svcDir; }
        public String getStatus() { return status; }
        public String getFile() { return file; }
        public String getBackup() { return backup; }
        public String getMessage() { return message; }
    }
}
