package com.exem.inspector.screen.config;

import java.util.List;
import java.util.Map;

/**
 * Restore 결과 — 원본 api_config_restore 응답 1:1.
 *
 * <p>{totalInserted, tables(처리 결과 목록), sequences(시퀀스 처리 목록), source(dump_info.source_db)}.
 */
public class RestoreResult {

    private final int totalInserted;
    private final List<RestoreTableResult> tables;
    private final List<Map<String, Object>> sequences;
    private final String source;

    public RestoreResult(int totalInserted, List<RestoreTableResult> tables,
                         List<Map<String, Object>> sequences, String source) {
        this.totalInserted = totalInserted;
        this.tables = tables;
        this.sequences = sequences;
        this.source = source;
    }

    public int getTotalInserted() { return totalInserted; }
    public List<RestoreTableResult> getTables() { return tables; }
    public List<Map<String, Object>> getSequences() { return sequences; }
    public String getSource() { return source; }
}
