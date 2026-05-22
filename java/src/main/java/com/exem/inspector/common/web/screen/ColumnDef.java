package com.exem.inspector.common.web.screen;

/**
 * 표준 표 응답의 컬럼 메타데이터. 렌더러는 이 정의만 보고 컬럼을 그린다.
 *
 * <p>{@code key} 는 행(row) 맵에서 값을 꺼내는 키이며, {@code hidden} 컬럼은 표에 그리지 않고
 * 렌더러가 부가정보(예: DELAY → STATUS 툴팁)로만 사용한다.
 */
public class ColumnDef {

    private final String key;
    private final String label;
    private final ColumnType type;
    private final ColumnRole role;
    private final boolean hidden;

    private ColumnDef(String key, String label, ColumnType type, ColumnRole role, boolean hidden) {
        this.key = key;
        this.label = label;
        this.type = type;
        this.role = role;
        this.hidden = hidden;
    }

    /** 표시 컬럼. */
    public static ColumnDef of(String key, String label, ColumnType type, ColumnRole role) {
        return new ColumnDef(key, label, type, role, false);
    }

    /** 숨김 컬럼(표 미표시 — 렌더러가 부가정보로만 사용). */
    public static ColumnDef hidden(String key, String label, ColumnType type, ColumnRole role) {
        return new ColumnDef(key, label, type, role, true);
    }

    public String getKey() {
        return key;
    }

    public String getLabel() {
        return label;
    }

    public ColumnType getType() {
        return type;
    }

    public ColumnRole getRole() {
        return role;
    }

    public boolean isHidden() {
        return hidden;
    }
}
