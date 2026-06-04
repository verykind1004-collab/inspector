package com.exem.inspector.screen.config;

/**
 * Inspector History 설정(원본 history.py 의 _load_insp_config 1:1).
 *
 * <p>{enabled, tables_initialized, retention_days, log_retention_days}.
 * 누락 키는 default 로 채움(원본 default 와 동일).
 */
public class InspHistoryConfig {

    private final boolean enabled;
    private final boolean tablesInitialized;
    private final int retentionDays;
    private final int logRetentionDays;

    public InspHistoryConfig(boolean enabled, boolean tablesInitialized,
                              int retentionDays, int logRetentionDays) {
        this.enabled = enabled;
        this.tablesInitialized = tablesInitialized;
        this.retentionDays = retentionDays;
        this.logRetentionDays = logRetentionDays;
    }

    /** 원본 default — enabled=false, tables_initialized=false, retention=31, log_retention=10. */
    public static InspHistoryConfig defaults() {
        return new InspHistoryConfig(false, false, 31, 10);
    }

    public boolean isEnabled() { return enabled; }
    public boolean isTablesInitialized() { return tablesInitialized; }
    public int getRetentionDays() { return retentionDays; }
    public int getLogRetentionDays() { return logRetentionDays; }
}
