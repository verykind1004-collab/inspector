package com.exem.inspector.screen.script;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.nullable;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

import org.junit.jupiter.api.Test;

import com.exem.inspector.common.db.DbType;

class ScriptServiceTest {

    private ScriptExecutor mockExec(DbType dbType) {
        ScriptExecutor e = mock(ScriptExecutor.class);
        when(e.currentDbType()).thenReturn(dbType);
        return e;
    }

    private static Map<String, Object> row(Object... kv) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) m.put((String) kv[i], kv[i + 1]);
        return m;
    }

    @Test
    void SELECT_실행이_표준_응답으로_조립된다() throws Exception {
        ScriptExecutor exec = mockExec(DbType.ORACLE);
        when(exec.run(eq("SELECT 1 FROM dual"), eq((String) null), anyInt()))
                .thenReturn(new ScriptExecutor.Result(
                        Arrays.asList(new ScriptExecutor.ColumnInfo("X", java.sql.Types.NUMERIC)),
                        Arrays.asList(row("X", 1)),
                        false));

        ScriptRunRequest req = new ScriptRunRequest();
        req.setSql("SELECT 1 FROM dual");
        ScriptRunResult res = new ScriptService(exec).run(req);

        assertThat(res.getRowCount()).isEqualTo(1);
        assertThat(res.isTruncated()).isFalse();
        assertThat(res.getMaxRows()).isEqualTo(ScriptService.MAX_SCRIPT_ROWS);
        assertThat(res.getScreen().getColumns()).hasSize(1);
        assertThat(res.getScreen().getColumns().get(0).getKey()).isEqualTo("X");
        assertThat(res.getScreen().getRows().get(0)).containsEntry("X", 1);
        assertThat(res.getScreen().getMeta().getScreen()).isEqualTo("script_manager");
        assertThat(res.getScreen().getMeta().getDbType()).isEqualTo("ORACLE");
    }

    @Test
    void DML_은_executor_도달하지_못한다() throws Exception {
        ScriptExecutor exec = mockExec(DbType.ORACLE);
        ScriptRunRequest req = new ScriptRunRequest();
        req.setSql("DELETE FROM t");

        assertThatThrownBy(() -> new ScriptService(exec).run(req))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Only SELECT");
        verify(exec, never()).run(anyString(), anyString(), anyInt());
    }

    @Test
    void 빈_SQL_차단() {
        ScriptExecutor exec = mockExec(DbType.ORACLE);
        ScriptRunRequest req = new ScriptRunRequest();
        req.setSql("");
        assertThatThrownBy(() -> new ScriptService(exec).run(req))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("No SQL provided");
    }

    @Test
    void null_본문_차단() {
        ScriptExecutor exec = mockExec(DbType.ORACLE);
        assertThatThrownBy(() -> new ScriptService(exec).run(null))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void schema_sanitize_후_executor_에_전달() throws Exception {
        ScriptExecutor exec = mockExec(DbType.POSTGRESQL);
        when(exec.run(anyString(), eq("public"), anyInt()))
                .thenReturn(new ScriptExecutor.Result(
                        Collections.emptyList(), Collections.emptyList(), false));

        ScriptRunRequest req = new ScriptRunRequest();
        req.setSql("SELECT 1");
        req.setSchema("public");
        new ScriptService(exec).run(req);

        verify(exec).run("SELECT 1", "public", ScriptService.MAX_SCRIPT_ROWS);
    }

    @Test
    void 부적합_schema는_null_로_전달() throws Exception {
        ScriptExecutor exec = mockExec(DbType.POSTGRESQL);
        when(exec.run(anyString(), eq((String) null), anyInt()))
                .thenReturn(new ScriptExecutor.Result(
                        Collections.emptyList(), Collections.emptyList(), false));

        ScriptRunRequest req = new ScriptRunRequest();
        req.setSql("SELECT 1");
        req.setSchema("a; DROP TABLE x");
        new ScriptService(exec).run(req);

        verify(exec).run("SELECT 1", null, ScriptService.MAX_SCRIPT_ROWS);
    }

    @Test
    void truncated_플래그_전달() throws Exception {
        ScriptExecutor exec = mockExec(DbType.ORACLE);
        when(exec.run(anyString(), eq((String) null), anyInt()))
                .thenReturn(new ScriptExecutor.Result(
                        Arrays.asList(new ScriptExecutor.ColumnInfo("c", java.sql.Types.VARCHAR)),
                        Collections.emptyList(),
                        true));

        ScriptRunRequest req = new ScriptRunRequest();
        req.setSql("SELECT * FROM big");
        ScriptRunResult res = new ScriptService(exec).run(req);

        assertThat(res.isTruncated()).isTrue();
        assertThat(res.getMaxRows()).isEqualTo(ScriptService.MAX_SCRIPT_ROWS);
    }

    @Test
    void DataSource_미설정_시_IllegalStateException_전파() throws Exception {
        ScriptExecutor exec = mockExec(DbType.ORACLE);
        // sanitizeSchema 결과 null 이 executor.run 두 번째 인자로 들어가므로 nullable matcher 사용.
        when(exec.run(anyString(), nullable(String.class), anyInt()))
                .thenThrow(new IllegalStateException("리포지토리가 설정되지 않았습니다"));

        ScriptRunRequest req = new ScriptRunRequest();
        req.setSql("SELECT 1 FROM dual");

        assertThatThrownBy(() -> new ScriptService(exec).run(req))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("리포지토리가 설정되지 않았습니다");
    }

    @Test
    void schemas_PG_목록_반환() throws Exception {
        ScriptExecutor exec = mockExec(DbType.POSTGRESQL);
        when(exec.listPgSchemas()).thenReturn(Arrays.asList("public", "app"));
        ScriptSchemasResult res = new ScriptService(exec).schemas();
        assertThat(res.getSchemas()).containsExactly("public", "app");
    }

    @Test
    void schemas_오류_시_빈_리스트_폴백() throws Exception {
        ScriptExecutor exec = mockExec(DbType.POSTGRESQL);
        when(exec.listPgSchemas()).thenThrow(new RuntimeException("driver missing"));
        ScriptSchemasResult res = new ScriptService(exec).schemas();
        assertThat(res.getSchemas()).isEmpty();
    }
}
