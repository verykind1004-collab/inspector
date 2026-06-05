package com.exem.inspector.screen.config;

import java.util.Map;

/**
 * Config Dump 결과 — 원본 config_dump.py 의 api_config_dump 응답 1:1.
 *
 * <p>{stats, dumpInfo, tables(columns/rows/count), sequences,
 *    jsonContent(직렬화 본문), sqlContent(생성된 SQL), filenameBase, dbType}.
 *
 * <p>jsonContent 는 FE 에서 파일 다운로드 시 그대로 사용한다 — 원본 _doDump 의
 * _dl(d.json_content, fname, "application/json") 와 동일 동작.
 */
public class ConfigDumpPayload {

    private final DumpStats stats;
    private final DumpInfo dumpInfo;
    private final Map<String, DumpTable> tables;
    private final Map<String, Object> sequences;
    private final String jsonContent;
    private final String sqlContent;
    private final String filenameBase;
    private final String dbType;

    public ConfigDumpPayload(DumpStats stats, DumpInfo dumpInfo,
                             Map<String, DumpTable> tables,
                             Map<String, Object> sequences,
                             String jsonContent, String sqlContent,
                             String filenameBase, String dbType) {
        this.stats = stats;
        this.dumpInfo = dumpInfo;
        this.tables = tables;
        this.sequences = sequences;
        this.jsonContent = jsonContent;
        this.sqlContent = sqlContent;
        this.filenameBase = filenameBase;
        this.dbType = dbType;
    }

    public DumpStats getStats() { return stats; }
    public DumpInfo getDumpInfo() { return dumpInfo; }
    public Map<String, DumpTable> getTables() { return tables; }
    public Map<String, Object> getSequences() { return sequences; }
    public String getJsonContent() { return jsonContent; }
    public String getSqlContent() { return sqlContent; }
    public String getFilenameBase() { return filenameBase; }
    public String getDbType() { return dbType; }
}
