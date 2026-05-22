package com.exem.inspector.common.web.screen;

/**
 * 표준 표 응답의 메타 정보(화면 식별·생성시각·행수).
 */
public class ScreenMeta {

    private final String screen;       // 화면 키(예: summary_10min)
    private final String title;        // 화면 제목
    private final String dbType;       // ORACLE / POSTGRESQL
    private final String generatedAt;  // 응답 생성 시각(ISO-8601 LOCAL)
    private final int rowCount;

    public ScreenMeta(String screen, String title, String dbType, String generatedAt, int rowCount) {
        this.screen = screen;
        this.title = title;
        this.dbType = dbType;
        this.generatedAt = generatedAt;
        this.rowCount = rowCount;
    }

    public String getScreen() {
        return screen;
    }

    public String getTitle() {
        return title;
    }

    public String getDbType() {
        return dbType;
    }

    public String getGeneratedAt() {
        return generatedAt;
    }

    public int getRowCount() {
        return rowCount;
    }
}
