package com.exem.inspector.screen.config;

/**
 * SQL Dump 결과 — config_dump.py::_generate_sql 의 응답 1:1.
 *
 * <p>{sql, filenameBase}. filename 은 dump 시점과 동일(yyyyMMdd_HHmmss).
 */
public class SqlDumpResult {

    private final String sql;
    private final String filenameBase;

    public SqlDumpResult(String sql, String filenameBase) {
        this.sql = sql;
        this.filenameBase = filenameBase;
    }

    public String getSql() { return sql; }
    public String getFilenameBase() { return filenameBase; }
}
