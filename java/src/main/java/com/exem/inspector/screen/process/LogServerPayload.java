package com.exem.inspector.screen.process;

import java.util.List;

/**
 * Process Gather DGM/DGS_n 탭 응답 — 원본 process.py::_gather_log_server_html 1:1.
 *
 * <p>한 호출로 다음을 모두 반환:
 * <ul>
 *   <li>{@code tabs}: 사용 가능한 DGM/DGS_n 탭 목록</li>
 *   <li>{@code currentTab}: 현재 탭의 logDir + 파일 목록(그룹별)</li>
 *   <li>{@code content}: 파일 선택 시 본문(검색/시간필터 적용) + 표시 메타</li>
 * </ul>
 */
public class LogServerPayload {

    public static class Tab {
        private final String id;       // dgm / dgs1 / ...
        private final String name;     // DGServer_M / DGServer_S1 / ...
        private final String logDir;   // log_paths.dgserver_m / log_paths.dgserver_s[i]
        public Tab(String id, String name, String logDir) {
            this.id = id; this.name = name; this.logDir = logDir;
        }
        public String getId() { return id; }
        public String getName() { return name; }
        public String getLogDir() { return logDir; }
    }

    /** 파일 목록 1개(셀렉터 옵션). {@code group} 은 DG/OBSD/Other 중 하나. */
    public static class File {
        private final String name;     // 상대경로 (예: DGM_18800.log, maxgauge/obsd1.log)
        private final String group;    // DG / OBSD / Other
        private final long mtime;
        public File(String name, String group, long mtime) {
            this.name = name; this.group = group; this.mtime = mtime;
        }
        public String getName() { return name; }
        public String getGroup() { return group; }
        public long getMtime() { return mtime; }
    }

    public static class CurrentTab {
        private final String tabId;
        private final String logDir;
        private final List<File> files;  // mtime DESC
        public CurrentTab(String tabId, String logDir, List<File> files) {
            this.tabId = tabId; this.logDir = logDir; this.files = files;
        }
        public String getTabId() { return tabId; }
        public String getLogDir() { return logDir; }
        public List<File> getFiles() { return files; }
    }

    /** 본문 + 표시 메타. 파일 선택+읽기 성공 시에만 채워진다. */
    public static class Content {
        private final String logPath;      // 절대경로
        private final String filterLabel;  // "Search Results" / "Latest 1,000 lines"
        private final Long totalMatch;     // 검색 시 총 매칭(있으면), 평상시 null
        private final int totalCount;      // 반환된 lines 수
        private final boolean truncated;   // SEARCH_LIMIT 초과 여부(총 매칭 > 반환)
        private final List<String> lines;
        private final boolean isZip;
        private final String error;        // 읽기 실패 시 메시지

        public Content(String logPath, String filterLabel, Long totalMatch,
                       int totalCount, boolean truncated, List<String> lines,
                       boolean isZip, String error) {
            this.logPath = logPath;
            this.filterLabel = filterLabel;
            this.totalMatch = totalMatch;
            this.totalCount = totalCount;
            this.truncated = truncated;
            this.lines = lines;
            this.isZip = isZip;
            this.error = error;
        }

        public static Content err(String logPath, String message) {
            return new Content(logPath, null, null, 0, false,
                    java.util.Collections.<String>emptyList(), false, message);
        }

        public String getLogPath() { return logPath; }
        public String getFilterLabel() { return filterLabel; }
        public Long getTotalMatch() { return totalMatch; }
        public int getTotalCount() { return totalCount; }
        public boolean isTruncated() { return truncated; }
        public List<String> getLines() { return lines; }
        public boolean getIsZip() { return isZip; }
        public String getError() { return error; }
    }

    private final List<Tab> tabs;
    private final CurrentTab currentTab;    // null 가능
    private final Content content;          // null 가능
    private final String configError;       // log_paths 미설정 시

    public LogServerPayload(List<Tab> tabs, CurrentTab currentTab, Content content, String configError) {
        this.tabs = tabs;
        this.currentTab = currentTab;
        this.content = content;
        this.configError = configError;
    }

    public List<Tab> getTabs() { return tabs; }
    public CurrentTab getCurrentTab() { return currentTab; }
    public Content getContent() { return content; }
    public String getConfigError() { return configError; }
}
