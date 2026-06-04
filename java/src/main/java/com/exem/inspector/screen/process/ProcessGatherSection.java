package com.exem.inspector.screen.process;

import java.util.List;

/**
 * Process Gather Overview 탭 — 한 DGServer 섹션.
 *
 * <p>원본 process.py page_process_gather() Overview 의 각 카드와 1:1.
 * 로그 파일 1개에 대해: 경로 / 전체 ERROR&WARN 카운트 / 마지막 500 라인 / 오류.
 */
public class ProcessGatherSection {

    private final String id;            // dgm / dgs1 / dgs2 ...
    private final String name;          // "DGServer_M" / "DGServer_S1" 등 표시명
    private final String logfile;       // 로그 파일 절대경로 또는 null
    private final long totalErrors;     // 전체 ERROR/WARN 카운트
    private final List<String> recentLines; // 마지막 500 ERROR/WARN
    private final String error;         // 로그 미존재/읽기 실패 시 사유

    public ProcessGatherSection(String id, String name, String logfile,
                                long totalErrors, List<String> recentLines, String error) {
        this.id = id;
        this.name = name;
        this.logfile = logfile;
        this.totalErrors = totalErrors;
        this.recentLines = recentLines;
        this.error = error;
    }

    public static ProcessGatherSection error(String id, String name, String logfile, String message) {
        return new ProcessGatherSection(id, name, logfile, 0, java.util.Collections.<String>emptyList(), message);
    }

    public String getId() { return id; }
    public String getName() { return name; }
    public String getLogfile() { return logfile; }
    public long getTotalErrors() { return totalErrors; }
    public List<String> getRecentLines() { return recentLines; }
    public String getError() { return error; }
}
