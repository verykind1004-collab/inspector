package com.exem.inspector.screen.script;

import java.util.List;

/**
 * Script Manager 의 schemas 목록 응답.
 *
 * <p>PG 일 때만 의미가 있다. Oracle 이거나 오류 발생 시 빈 리스트를 반환한다(원본 api_script_schemas 동일).
 */
public class ScriptSchemasResult {

    private final List<String> schemas;

    public ScriptSchemasResult(List<String> schemas) {
        this.schemas = schemas;
    }

    public List<String> getSchemas() {
        return schemas;
    }
}
