package com.exem.inspector.screen.script;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

/**
 * Script Manager POST 본문.
 *
 * <p>원본 api_script_run 의 JSON 본문({@code sql}, {@code schema})과 동일 형식.
 * 알 수 없는 필드는 무시(프런트 진화 호환).
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public class ScriptRunRequest {

    private String sql;
    private String schema;

    public String getSql() {
        return sql;
    }

    public void setSql(String sql) {
        this.sql = sql;
    }

    public String getSchema() {
        return schema;
    }

    public void setSchema(String schema) {
        this.schema = schema;
    }
}
