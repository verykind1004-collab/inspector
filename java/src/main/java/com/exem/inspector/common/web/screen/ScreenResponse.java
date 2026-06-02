package com.exem.inspector.common.web.screen;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * DB 성능분석 화면의 표준 표 응답.
 *
 * <p>{@code columns}(메타) + {@code rows}(키-값 행) 구조로, 2층 공통 테이블 렌더러가 일관 소비한다(I절).
 * 행은 컬럼 key 로 접근하는 맵이며, 컬럼 정의에 없는 키는 렌더러가 무시한다.
 * 새 화면은 이 스키마만 지키면 별도 렌더링 코드 없이 동일 렌더러에 실린다(공통화 강제).
 */
public class ScreenResponse {

    private final ScreenMeta meta;
    private final List<ColumnDef> columns;
    private final List<Map<String, Object>> rows;

    private ScreenResponse(ScreenMeta meta, List<ColumnDef> columns, List<Map<String, Object>> rows) {
        this.meta = meta;
        this.columns = columns;
        this.rows = rows;
    }

    public static Builder builder(String screen, String title, String dbType) {
        return new Builder(screen, title, dbType);
    }

    public ScreenMeta getMeta() {
        return meta;
    }

    public List<ColumnDef> getColumns() {
        return columns;
    }

    public List<Map<String, Object>> getRows() {
        return rows;
    }

    /** 컬럼 정의 → 행 추가 → build 순으로 표준 응답을 조립한다. */
    public static class Builder {

        private static final DateTimeFormatter ISO = DateTimeFormatter.ISO_LOCAL_DATE_TIME;

        private final String screen;
        private final String title;
        private final String dbType;
        private final List<ColumnDef> columns = new ArrayList<>();
        private final List<Map<String, Object>> rows = new ArrayList<>();

        private Builder(String screen, String title, String dbType) {
            this.screen = screen;
            this.title = title;
            this.dbType = dbType;
        }

        public Builder column(ColumnDef col) {
            columns.add(col);
            return this;
        }

        /**
         * 매퍼가 반환한 LinkedHashMap(컬럼 라벨 키) 한 행을 컬럼 메타 키 순서대로 추가한다.
         * 원본 _parse_db_table 의 헤더->값 매핑과 동등(컬럼 메타에 정의된 키만 노출).
         */
        public Builder rowFromMap(Map<String, ?> source) {
            if (source == null) {
                throw new IllegalArgumentException("rowFromMap source 가 null");
            }
            Object[] values = new Object[columns.size()];
            for (int i = 0; i < columns.size(); i++) {
                values[i] = source.get(columns.get(i).getKey());
            }
            return row(values);
        }

        /** 컬럼 정의 순서대로 값을 받아 행을 추가한다(values 길이 = 컬럼 수). */
        public Builder row(Object... values) {
            if (values.length != columns.size()) {
                throw new IllegalArgumentException(
                        "행 값 개수(" + values.length + ")가 컬럼 수(" + columns.size() + ")와 다릅니다");
            }
            Map<String, Object> row = new LinkedHashMap<>();
            for (int i = 0; i < columns.size(); i++) {
                row.put(columns.get(i).getKey(), values[i]);
            }
            rows.add(row);
            return this;
        }

        public ScreenResponse build() {
            ScreenMeta builtMeta =
                    new ScreenMeta(screen, title, dbType, LocalDateTime.now().format(ISO), rows.size());
            return new ScreenResponse(builtMeta, columns, rows);
        }
    }
}
