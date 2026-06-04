package com.exem.inspector.screen.process;

import java.util.List;

/**
 * Process Gather OBSD 탭 응답 — 원본 process.py::_gather_obsd_html 1:1.
 *
 * <p>각 DGServer 프로세스(dgm/dgs1/...) 당 OBSD 로그 파일 목록.
 * 파일 본문은 별도 {@code /labs/api/log-tail} 로 on-demand fetch.
 */
public class ObsdPayload {

    public static class File {
        private final String name;
        private final long size;
        private final long mtime;   // epoch ms
        private final String path;  // 절대경로 — log-tail 호출용

        public File(String name, long size, long mtime, String path) {
            this.name = name;
            this.size = size;
            this.mtime = mtime;
            this.path = path;
        }

        public String getName() { return name; }
        public long getSize() { return size; }
        public long getMtime() { return mtime; }
        public String getPath() { return path; }
    }

    public static class Proc {
        private final String id;       // dgm / dgs1 / ...
        private final String name;     // DGServer_M / DGServer_S1 / ...
        private final String logDir;   // {home}/log/maxgauge
        private final List<File> files; // mtime desc
        private final String error;    // logDir 없음 / 읽기 실패 시

        public Proc(String id, String name, String logDir, List<File> files, String error) {
            this.id = id;
            this.name = name;
            this.logDir = logDir;
            this.files = files;
            this.error = error;
        }

        public String getId() { return id; }
        public String getName() { return name; }
        public String getLogDir() { return logDir; }
        public List<File> getFiles() { return files; }
        public String getError() { return error; }
    }

    private final List<Proc> procs;
    private final String configError;

    public ObsdPayload(List<Proc> procs, String configError) {
        this.procs = procs;
        this.configError = configError;
    }

    public List<Proc> getProcs() { return procs; }
    public String getConfigError() { return configError; }
}
