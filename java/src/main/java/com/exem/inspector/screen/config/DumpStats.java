package com.exem.inspector.screen.config;

import java.util.List;

/**
 * Dump 통계 — 원본 api_config_dump 응답의 stats 1:1.
 *
 * <p>{tables(수집된 테이블 수), rows(총 행수), skipped(누락된 테이블/시퀀스명)}.
 */
public class DumpStats {

    private final int tables;
    private final int rows;
    private final List<String> skipped;

    public DumpStats(int tables, int rows, List<String> skipped) {
        this.tables = tables;
        this.rows = rows;
        this.skipped = skipped;
    }

    public int getTables() { return tables; }
    public int getRows() { return rows; }
    public List<String> getSkipped() { return skipped; }
}
