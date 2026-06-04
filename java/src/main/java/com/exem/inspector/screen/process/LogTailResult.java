package com.exem.inspector.screen.process;

import java.util.List;

/**
 * Log tail 응답 — 원본 {@code api_log_tail} 와 1:1 동등.
 *
 * <p>{@code offset == 0} 으로 호출하면 마지막 {@code TAIL_LINES} 줄 + 현재 파일 크기 반환.
 * {@code offset > 0} 으로 호출하면 그 위치부터 새로 추가된 라인 + 갱신된 offset 반환.
 * 에러 시 {@code error} 만 채움(lines/offset null).
 */
public class LogTailResult {

    private final List<String> lines;
    private final Long offset;
    private final String error;

    public LogTailResult(List<String> lines, Long offset, String error) {
        this.lines = lines;
        this.offset = offset;
        this.error = error;
    }

    public static LogTailResult ok(List<String> lines, long offset) {
        return new LogTailResult(lines, offset, null);
    }
    public static LogTailResult error(String message) {
        return new LogTailResult(null, null, message);
    }

    public List<String> getLines() { return lines; }
    public Long getOffset() { return offset; }
    public String getError() { return error; }
}
