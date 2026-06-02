package com.exem.inspector.screen.script;

import java.util.Collections;
import java.util.List;
import java.util.Map;

import com.exem.inspector.common.db.DbType;

/**
 * Script Manager 의 SELECT 실행 추상화.
 *
 * <p>JDBC 의존을 인터페이스로 분리해 서비스 단위 테스트가 가능하게 한다(I절 — 외부 의존을 화면 코드에 박지 않음).
 * 구현체는 {@link JdbcScriptExecutor}.
 */
public interface ScriptExecutor {

    /**
     * READ ONLY 트랜잭션으로 SELECT 를 실행한다.
     *
     * @param sql           검증을 통과한 SQL 본문(주석 포함 그대로 전달).
     * @param searchPath    PG 한정 search_path 값(미사용 시 null).
     * @param maxRows       응답 행 상한(0 또는 음수면 무제한). 상한 초과 시 {@link Result#truncated}=true.
     * @return 컬럼/행/잘림 플래그.
     */
    Result run(String sql, String searchPath, int maxRows) throws Exception;

    /** PG schema 목록(Oracle 은 빈 리스트). */
    default List<String> listPgSchemas() throws Exception {
        return Collections.emptyList();
    }

    /** 현재 리포지토리 DB 타입(서비스 측 응답 메타 채우기용). */
    DbType currentDbType();

    /** 실행 결과 — 컬럼 메타 순서대로 LinkedHashMap 행을 담는다. */
    final class Result {

        public final List<ColumnInfo> columns;
        public final List<Map<String, Object>> rows;
        public final boolean truncated;

        public Result(List<ColumnInfo> columns, List<Map<String, Object>> rows, boolean truncated) {
            this.columns = columns;
            this.rows = rows;
            this.truncated = truncated;
        }
    }

    /** ResultSet 컬럼 메타(라벨 + java.sql.Types). 라벨 키는 행 맵의 key 와 일치한다. */
    final class ColumnInfo {

        public final String label;
        public final int sqlType;

        public ColumnInfo(String label, int sqlType) {
            this.label = label;
            this.sqlType = sqlType;
        }
    }
}
