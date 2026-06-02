package com.exem.inspector.screen.script;

import com.exem.inspector.common.web.screen.ScreenResponse;

/**
 * Script Manager 실행 결과 페이로드.
 *
 * <p>표준 표({@link ScreenResponse}) + 부가 정보(행수/잘림/상한). 원본 응답의
 * {@code rows} / {@code truncated} 필드와 동등하며 표 본문은 표준 응답 봉투로 통일했다.
 */
public class ScriptRunResult {

    private final ScreenResponse screen;
    private final int rowCount;
    private final boolean truncated;
    private final int maxRows;

    public ScriptRunResult(ScreenResponse screen, int rowCount, boolean truncated, int maxRows) {
        this.screen = screen;
        this.rowCount = rowCount;
        this.truncated = truncated;
        this.maxRows = maxRows;
    }

    public ScreenResponse getScreen() {
        return screen;
    }

    public int getRowCount() {
        return rowCount;
    }

    public boolean isTruncated() {
        return truncated;
    }

    public int getMaxRows() {
        return maxRows;
    }
}
