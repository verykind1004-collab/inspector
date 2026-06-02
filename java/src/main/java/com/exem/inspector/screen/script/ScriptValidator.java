package com.exem.inspector.screen.script;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Script Manager 의 SELECT-only 사전검증.
 *
 * <p>원본 {@code _validate_select_only} / {@code _strip_sql_comments} 와 1:1 동등.
 * 주석을 제거하고 {@code ';'} 로 분리한 모든 statement 가 허용 prefix 로 시작해야 한다.
 * 실 실행 시점에 DB 의 {@code SET TRANSACTION READ ONLY} 가 2차 방어선이다(I절 — 화면이 보안을 직접 떠안지 않음).
 */
public final class ScriptValidator {

    /** 원본 _ALLOWED_PREFIXES 와 동일. */
    private static final Set<String> ALLOWED_PREFIXES = new HashSet<>(Arrays.asList(
            "SELECT", "WITH", "EXPLAIN", "SHOW", "VALUES", "DESC", "DESCRIBE"));

    private static final Pattern BLOCK_COMMENT = Pattern.compile("/\\*.*?\\*/", Pattern.DOTALL);
    private static final Pattern LINE_COMMENT = Pattern.compile("--[^\n]*");
    /** 원본의 {@code re.search(r'[^a-zA-Z0-9_]', schema)} 와 동등(전부 영숫자+언더스코어). */
    private static final Pattern SCHEMA_PATTERN = Pattern.compile("^[A-Za-z0-9_]+$");

    private ScriptValidator() {}

    /** 입력 SQL 의 블록/라인 주석을 공백으로 치환한다(prefix 검사 우회 차단). */
    public static String stripComments(String sql) {
        if (sql == null) return "";
        String s = BLOCK_COMMENT.matcher(sql).replaceAll(" ");
        s = LINE_COMMENT.matcher(s).replaceAll(" ");
        return s;
    }

    /**
     * OK 면 null, 차단이면 사용자 노출 메시지를 반환한다(문구는 원본과 동일).
     * 빈 SQL 도 차단 — "No SQL provided".
     */
    public static String validateSelectOnly(String sql) {
        String cleaned = stripComments(sql).trim();
        if (cleaned.isEmpty()) return "No SQL provided";
        for (String stmt : cleaned.split(";")) {
            String s = stmt.trim();
            if (s.isEmpty()) continue;
            int idx = 0;
            while (idx < s.length() && !Character.isWhitespace(s.charAt(idx))) idx++;
            String first = s.substring(0, idx).toUpperCase();
            if (!ALLOWED_PREFIXES.contains(first)) {
                return "Only SELECT is allowed. Blocked statement starts with: " + first;
            }
        }
        return null;
    }

    /**
     * schema 이름 sanitize. {@code [A-Za-z0-9_]+} 만 통과시키고 그 외(빈 값/특수문자)는 null.
     * 원본 코드와 동일하게 trim 후 검사하며, 부적합 입력은 조용히 null 로 떨어져 SET search_path 를 건너뛴다.
     */
    public static String sanitizeSchema(String schema) {
        if (schema == null) return null;
        String s = schema.trim();
        if (s.isEmpty()) return null;
        if (!SCHEMA_PATTERN.matcher(s).matches()) return null;
        return s;
    }
}
