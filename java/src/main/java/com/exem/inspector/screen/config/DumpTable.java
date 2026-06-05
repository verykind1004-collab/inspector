package com.exem.inspector.screen.config;

import java.util.List;

/**
 * 단일 테이블 dump 결과 — 원본 _dump_table 반환 1:1.
 *
 * <p>{columns(컬럼명 목록, 원본 순서 유지), rows(행별 값 배열의 배열), count}.
 * Restore 측에서 source columns + rows 를 그대로 재현하기 위한 array-of-array 포맷.
 */
public class DumpTable {

    private final List<String> columns;
    private final List<List<Object>> rows;
    private final int count;

    public DumpTable(List<String> columns, List<List<Object>> rows, int count) {
        this.columns = columns;
        this.rows = rows;
        this.count = count;
    }

    public List<String> getColumns() { return columns; }
    public List<List<Object>> getRows() { return rows; }
    public int getCount() { return count; }
}
