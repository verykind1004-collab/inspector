package com.exem.inspector.screen.config;

import java.util.List;

/** connection_test 응답 — 컴포넌트별 OK/FAIL/SKIP + 상세. */
public class ConnectionTestResult {
    private final List<Item> results;
    public ConnectionTestResult(List<Item> results) { this.results = results; }
    public List<Item> getResults() { return results; }

    public static final class Item {
        private final String component;
        private final String status;   // OK / FAIL / SKIP
        private final String detail;
        public Item(String component, String status, String detail) {
            this.component = component; this.status = status; this.detail = detail;
        }
        public String getComponent() { return component; }
        public String getStatus() { return status; }
        public String getDetail() { return detail; }
    }
}
