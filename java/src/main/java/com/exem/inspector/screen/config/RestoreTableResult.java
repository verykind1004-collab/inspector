package com.exem.inspector.screen.config;

import java.util.List;

/**
 * Restore 결과의 테이블별 항목 — 원본 api_config_restore 의 tables[] 원소 1:1.
 *
 * <p>{table, status(ok/skip), inserted, columns(처리 컬럼 수), totalColumns(원본 컬럼 수),
 *     reason(skip 사유), skippedColumns(source-only), newColumns(target-only)}.
 *
 * <p>FE 결과 표 렌더와 1:1.
 */
public class RestoreTableResult {

    private final String table;
    private final String status;
    private final int inserted;
    private final Integer columns;
    private final Integer totalColumns;
    private final String reason;
    private final List<String> skippedColumns;
    private final List<String> newColumns;

    public RestoreTableResult(String table, String status, int inserted,
                              Integer columns, Integer totalColumns,
                              String reason,
                              List<String> skippedColumns, List<String> newColumns) {
        this.table = table;
        this.status = status;
        this.inserted = inserted;
        this.columns = columns;
        this.totalColumns = totalColumns;
        this.reason = reason;
        this.skippedColumns = skippedColumns;
        this.newColumns = newColumns;
    }

    public String getTable() { return table; }
    public String getStatus() { return status; }
    public int getInserted() { return inserted; }
    public Integer getColumns() { return columns; }
    public Integer getTotalColumns() { return totalColumns; }
    public String getReason() { return reason; }
    public List<String> getSkippedColumns() { return skippedColumns; }
    public List<String> getNewColumns() { return newColumns; }
}
