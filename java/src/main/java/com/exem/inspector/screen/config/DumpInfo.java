package com.exem.inspector.screen.config;

import java.util.List;

/**
 * Dump 파일 메타 — 원본 config_dump.py 의 dump_data["dump_info"] 1:1.
 *
 * <p>{createdAt, sourceDb, dbType, menus, menuLabels, version}.
 * Restore 시 source 표시 + version 검증에 사용된다.
 */
public class DumpInfo {

    private final String createdAt;
    private final String sourceDb;
    private final String dbType;
    private final List<String> menus;
    private final List<String> menuLabels;
    private final String version;

    public DumpInfo(String createdAt, String sourceDb, String dbType,
                    List<String> menus, List<String> menuLabels, String version) {
        this.createdAt = createdAt;
        this.sourceDb = sourceDb;
        this.dbType = dbType;
        this.menus = menus;
        this.menuLabels = menuLabels;
        this.version = version;
    }

    public String getCreatedAt() { return createdAt; }
    public String getSourceDb() { return sourceDb; }
    public String getDbType() { return dbType; }
    public List<String> getMenus() { return menus; }
    public List<String> getMenuLabels() { return menuLabels; }
    public String getVersion() { return version; }
}
