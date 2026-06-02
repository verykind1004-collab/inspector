package com.exem.inspector.screen.script;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.junit.jupiter.api.Test;

class ScriptValidatorTest {

    @Test
    void SELECT_허용_prefix는_통과() {
        assertThat(ScriptValidator.validateSelectOnly("SELECT 1 FROM dual")).isNull();
        assertThat(ScriptValidator.validateSelectOnly("WITH t AS (SELECT 1) SELECT * FROM t")).isNull();
        assertThat(ScriptValidator.validateSelectOnly("EXPLAIN SELECT 1")).isNull();
        assertThat(ScriptValidator.validateSelectOnly("SHOW timezone")).isNull();
        assertThat(ScriptValidator.validateSelectOnly("VALUES (1)")).isNull();
        assertThat(ScriptValidator.validateSelectOnly("DESC users")).isNull();
        assertThat(ScriptValidator.validateSelectOnly("DESCRIBE users")).isNull();
    }

    @Test
    void 소문자_또는_혼합대소_도_허용() {
        assertThat(ScriptValidator.validateSelectOnly("select 1")).isNull();
        assertThat(ScriptValidator.validateSelectOnly("Select 1")).isNull();
        assertThat(ScriptValidator.validateSelectOnly("  \n SELECT 1 ")).isNull();
    }

    @Test
    void 빈_입력은_차단() {
        assertThat(ScriptValidator.validateSelectOnly("")).isEqualTo("No SQL provided");
        assertThat(ScriptValidator.validateSelectOnly("   ")).isEqualTo("No SQL provided");
        assertThat(ScriptValidator.validateSelectOnly(null)).isEqualTo("No SQL provided");
        assertThat(ScriptValidator.validateSelectOnly("/* only comment */")).isEqualTo("No SQL provided");
        assertThat(ScriptValidator.validateSelectOnly("-- only line\n--more")).isEqualTo("No SQL provided");
    }

    @Test
    void DML_DDL은_차단() {
        assertThat(ScriptValidator.validateSelectOnly("DELETE FROM users"))
                .contains("Only SELECT").contains("DELETE");
        assertThat(ScriptValidator.validateSelectOnly("UPDATE t SET a=1"))
                .contains("UPDATE");
        assertThat(ScriptValidator.validateSelectOnly("INSERT INTO t VALUES(1)"))
                .contains("INSERT");
        assertThat(ScriptValidator.validateSelectOnly("DROP TABLE t"))
                .contains("DROP");
        assertThat(ScriptValidator.validateSelectOnly("TRUNCATE TABLE t"))
                .contains("TRUNCATE");
        assertThat(ScriptValidator.validateSelectOnly("ALTER TABLE t ADD c1 INT"))
                .contains("ALTER");
    }

    @Test
    void 주석으로_위장한_금지문장도_차단() {
        assertThat(ScriptValidator.validateSelectOnly("-- pretend OK\nDROP TABLE t"))
                .contains("DROP");
        assertThat(ScriptValidator.validateSelectOnly("/* SELECT */ TRUNCATE TABLE t"))
                .contains("TRUNCATE");
    }

    @Test
    void 다중_stmt_중_하나라도_금지면_차단() {
        assertThat(ScriptValidator.validateSelectOnly("SELECT 1; DROP TABLE t"))
                .contains("DROP");
        assertThat(ScriptValidator.validateSelectOnly("SELECT 1; SELECT 2; UPDATE t SET a=1"))
                .contains("UPDATE");
    }

    @Test
    void schema_sanitize_허용_케이스() {
        assertThat(ScriptValidator.sanitizeSchema("public")).isEqualTo("public");
        assertThat(ScriptValidator.sanitizeSchema("my_schema_01")).isEqualTo("my_schema_01");
        assertThat(ScriptValidator.sanitizeSchema(" trim_me ")).isEqualTo("trim_me");
        assertThat(ScriptValidator.sanitizeSchema("A_BC")).isEqualTo("A_BC");
    }

    @Test
    void schema_sanitize_거부_케이스() {
        assertThat(ScriptValidator.sanitizeSchema(null)).isNull();
        assertThat(ScriptValidator.sanitizeSchema("")).isNull();
        assertThat(ScriptValidator.sanitizeSchema("   ")).isNull();
        assertThat(ScriptValidator.sanitizeSchema("a; DROP TABLE x")).isNull();
        assertThat(ScriptValidator.sanitizeSchema("a-b")).isNull();
        assertThat(ScriptValidator.sanitizeSchema("a.b")).isNull();
        assertThat(ScriptValidator.sanitizeSchema("a b")).isNull();
        assertThat(ScriptValidator.sanitizeSchema("public; --")).isNull();
    }

    @Test
    void oracle_directive_strip_정상_라인_보존() {
        String s = "SET PAGESIZE 0\nSELECT 1 FROM dual\nCOLUMN x FORMAT a10\nPROMPT done\n";
        String stripped = JdbcScriptExecutor.stripOracleDirectives(s);
        assertThat(stripped).contains("SELECT 1 FROM dual");
        assertThat(stripped).doesNotContain("SET PAGESIZE");
        assertThat(stripped).doesNotContain("COLUMN x");
        assertThat(stripped).doesNotContain("PROMPT");
    }

    @Test
    void trailing_semicolons_제거() {
        assertThat(JdbcScriptExecutor.trimTrailingSemicolons("SELECT 1;")).isEqualTo("SELECT 1");
        assertThat(JdbcScriptExecutor.trimTrailingSemicolons("SELECT 1;;;")).isEqualTo("SELECT 1");
        assertThat(JdbcScriptExecutor.trimTrailingSemicolons("SELECT 1")).isEqualTo("SELECT 1");
    }

    @Test
    void pg_strip_directives_백슬래시_라인만_제거() {
        String stripped = JdbcScriptExecutor.stripPgDirectives("\\set X 1\nSELECT 1\n\\timing on\n");
        assertThat(stripped).contains("SELECT 1");
        assertThat(stripped).doesNotContain("\\set");
        assertThat(stripped).doesNotContain("\\timing");
    }

    @Test
    void pg_split_단일_select() {
        List<String> stmts = JdbcScriptExecutor.splitPgStatements("SELECT 1");
        assertThat(stmts).hasSize(1);
        assertThat(stmts.get(0).trim()).isEqualTo("SELECT 1");
    }

    @Test
    void pg_split_plpgsql_함수와_후행_select_분리() {
        String s = "CREATE FUNCTION f() RETURNS void AS $$\nBEGIN\nNULL;\nEND;\n$$ LANGUAGE plpgsql;\nSELECT 1";
        List<String> stmts = JdbcScriptExecutor.splitPgStatements(s);
        assertThat(stmts).hasSize(2);
        assertThat(stmts.get(0)).contains("LANGUAGE plpgsql");
        assertThat(stmts.get(1).trim()).isEqualTo("SELECT 1");
    }
}
