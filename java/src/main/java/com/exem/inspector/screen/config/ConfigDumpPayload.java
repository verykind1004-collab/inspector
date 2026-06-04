package com.exem.inspector.screen.config;

import java.util.List;
import java.util.Map;

/**
 * Config Dump 결과 — 원본 config_dump.py 의 api_config_dump 응답 1:1 동등.
 *
 * <p>{filename_base, db_type, selected_menus, tables, sequences, skipped}.
 */
public class ConfigDumpPayload {

    private final String filenameBase;
    private final String dbType;
    private final List<String> selectedMenus;
    private final Map<String, List<Map<String, Object>>> tables;   // 테이블별 행 목록
    private final Map<String, Object> sequences;                   // 시퀀스 마지막 값
    private final List<String> skipped;                            // 누락 테이블/시퀀스

    public ConfigDumpPayload(String filenameBase, String dbType, List<String> selectedMenus,
                             Map<String, List<Map<String, Object>>> tables,
                             Map<String, Object> sequences,
                             List<String> skipped) {
        this.filenameBase = filenameBase;
        this.dbType = dbType;
        this.selectedMenus = selectedMenus;
        this.tables = tables;
        this.sequences = sequences;
        this.skipped = skipped;
    }

    public String getFilenameBase() { return filenameBase; }
    public String getDbType() { return dbType; }
    public List<String> getSelectedMenus() { return selectedMenus; }
    public Map<String, List<Map<String, Object>>> getTables() { return tables; }
    public Map<String, Object> getSequences() { return sequences; }
    public List<String> getSkipped() { return skipped; }
}
