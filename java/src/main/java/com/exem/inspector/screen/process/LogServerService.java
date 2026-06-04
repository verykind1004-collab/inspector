package com.exem.inspector.screen.process;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Deque;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.exem.inspector.config.LogPathsBlock;
import com.exem.inspector.config.ServiceConfig;

/**
 * DGM/DGS_n 로그 뷰어 서비스 — 원본 process.py::_gather_log_server_html 1:1.
 *
 * <p>{@code log_paths} 의 dgserver_m + dgserver_s[i] 경로 기반으로 탭/파일 목록을 만들고,
 * 파일 선택 시 다음 규칙으로 본문을 반환:
 * <ul>
 *   <li>필터 없음: 마지막 1,000 라인</li>
 *   <li>검색어만: grep -ic + grep -i -m 500</li>
 *   <li>시간 필터 포함: 전체 읽어 라인별 매칭(타임스탬프 무 = 직전 ts 범위 상속)</li>
 *   <li>.log.zip: 내부 entry 첫번째 읽어 동일 필터</li>
 * </ul>
 */
@Service
public class LogServerService {

    private static final Logger log = LoggerFactory.getLogger(LogServerService.class);
    /** 원본 SEARCH_LIMIT = 500. */
    static final int SEARCH_LIMIT = 500;
    /** 원본 마지막 N 라인 기본값. */
    static final int TAIL_LINES = 1000;

    /** 행 첫 머리의 {@code [HH:MM:SS(.mmm)} 타임스탬프 추출용. */
    private static final Pattern TIME_RE = Pattern.compile("^\\[(\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?)");

    private final ServiceConfig serviceConfig;

    public LogServerService(ServiceConfig serviceConfig) {
        this.serviceConfig = serviceConfig;
    }

    /**
     * 탭/파일/본문을 한 번에 빌드. 모든 파라미터 nullable.
     */
    public LogServerPayload build(String tabId, String file, String search, String timeFrom, String timeTo) {
        LogPathsBlock lp;
        try {
            lp = serviceConfig.logPaths();
        } catch (RuntimeException e) {
            return new LogServerPayload(Collections.<LogServerPayload.Tab>emptyList(),
                    null, null, "service_config 로드 실패: " + e.getMessage());
        }

        List<LogServerPayload.Tab> tabs = new ArrayList<>();
        String dgm = nz(lp.dgserverM());
        if (!dgm.isEmpty()) tabs.add(new LogServerPayload.Tab("dgm", "DGServer_M", dgm));
        List<String> dgsList = lp.dgserverS();
        if (dgsList != null) {
            for (int i = 0; i < dgsList.size(); i++) {
                String dgs = nz(dgsList.get(i));
                if (dgs.isEmpty()) continue;
                tabs.add(new LogServerPayload.Tab("dgs" + (i + 1), "DGServer_S" + (i + 1), dgs));
            }
        }
        if (tabs.isEmpty()) {
            return new LogServerPayload(tabs, null, null, "DGServer log_paths 가 설정되지 않았습니다.");
        }

        // tabId 검증
        LogServerPayload.Tab cur = null;
        for (LogServerPayload.Tab t : tabs) {
            if (t.getId().equals(tabId)) { cur = t; break; }
        }
        if (cur == null) cur = tabs.get(0);

        // 파일 목록 스캔(원본 _scan_log_dir + maxgauge 하위)
        List<LogServerPayload.File> files = scanLogFiles(Paths.get(cur.getLogDir()));
        LogServerPayload.CurrentTab current = new LogServerPayload.CurrentTab(
                cur.getId(), cur.getLogDir(), files);

        LogServerPayload.Content content = null;
        if (file != null && !file.isEmpty()) {
            content = readContent(cur.getLogDir(), file, nz(search), nz(timeFrom), nz(timeTo));
        }

        return new LogServerPayload(tabs, current, content, null);
    }

    /** 원본 _scan_log_dir + maxgauge 하위 통합 스캔 → mtime DESC. */
    private List<LogServerPayload.File> scanLogFiles(Path logDir) {
        List<LogServerPayload.File> files = new ArrayList<>();
        if (logDir == null || !Files.isDirectory(logDir)) return files;
        scanLogDir(logDir, "", files);
        scanLogDir(logDir.resolve("maxgauge"), "maxgauge", files);
        files.sort(new Comparator<LogServerPayload.File>() {
            @Override public int compare(LogServerPayload.File a, LogServerPayload.File b) {
                return Long.compare(b.getMtime(), a.getMtime());
            }
        });
        return files;
    }

    private static void scanLogDir(Path dir, String prefix, List<LogServerPayload.File> out) {
        if (dir == null || !Files.isDirectory(dir)) return;
        try (DirectoryStream<Path> ds = Files.newDirectoryStream(dir)) {
            for (Path p : ds) {
                String fname = p.getFileName().toString();
                if (!(fname.endsWith(".log") || fname.endsWith(".log.zip"))) continue;
                String rel = prefix.isEmpty() ? fname : prefix + "/" + fname;
                long mtime;
                try { mtime = Files.getLastModifiedTime(p).toMillis(); }
                catch (IOException e) { mtime = 0L; }
                out.add(new LogServerPayload.File(rel, groupOf(rel), mtime));
            }
        } catch (IOException ignored) { /* skip */ }
    }

    /** 원본 그룹 분류: DGM_/DGS_ prefix → "DG", maxgauge/ → "OBSD", 나머지 → "Other". */
    static String groupOf(String rel) {
        String base = rel.contains("/") ? rel.substring(rel.lastIndexOf('/') + 1) : rel;
        String low = base.toLowerCase();
        if (rel.startsWith("maxgauge/")) return "OBSD";
        if (low.startsWith("dgm_") || low.startsWith("dgs_")) return "DG";
        return "Other";
    }

    private LogServerPayload.Content readContent(String logDir, String file,
                                                  String search, String timeFrom, String timeTo) {
        Path logPath = Paths.get(logDir, file).normalize();
        if (!Files.exists(logPath)) {
            return LogServerPayload.Content.err(logPath.toString(), "File not found");
        }
        boolean isZip = file.endsWith(".log.zip");
        boolean hasTime = !timeFrom.isEmpty() || !timeTo.isEmpty();
        boolean hasFilter = !search.isEmpty() || hasTime;

        try {
            List<String> allLines;
            if (isZip) {
                allLines = readZipFirstEntry(logPath);
                if (allLines == null) {
                    return LogServerPayload.Content.err(logPath.toString(), "Empty zip file");
                }
            } else if (!hasFilter) {
                List<String> tail = tailLines(logPath, TAIL_LINES);
                return new LogServerPayload.Content(logPath.toString(),
                        "Latest 1,000 lines", null, tail.size(), false, tail, false, null);
            } else {
                allLines = readAllLines(logPath);
            }

            if (!hasFilter) {
                // zip: 필터 없으면 last 1,000
                int from = Math.max(0, allLines.size() - TAIL_LINES);
                List<String> tail = new ArrayList<>(allLines.subList(from, allLines.size()));
                return new LogServerPayload.Content(logPath.toString(),
                        "Latest 1,000 lines", null, tail.size(), false, tail, true, null);
            }

            // 필터 적용
            List<String> matched = filterLines(allLines, search, timeFrom, timeTo);
            int totalMatch = matched.size();
            boolean truncated = totalMatch > SEARCH_LIMIT;
            List<String> shown = truncated ? new ArrayList<>(matched.subList(0, SEARCH_LIMIT)) : matched;
            return new LogServerPayload.Content(logPath.toString(),
                    "Search Results", (long) totalMatch, shown.size(), truncated, shown, isZip, null);
        } catch (IOException e) {
            return LogServerPayload.Content.err(logPath.toString(), "Error: " + e.getMessage());
        }
    }

    private static List<String> readZipFirstEntry(Path zip) throws IOException {
        try (ZipFile zf = new ZipFile(zip.toFile())) {
            java.util.Enumeration<? extends ZipEntry> en = zf.entries();
            if (!en.hasMoreElements()) return null;
            ZipEntry e = en.nextElement();
            List<String> lines = new ArrayList<>();
            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(zf.getInputStream(e), StandardCharsets.UTF_8))) {
                String s;
                while ((s = br.readLine()) != null) lines.add(s);
            }
            return lines;
        }
    }

    private static List<String> readAllLines(Path path) throws IOException {
        try {
            return Files.readAllLines(path, StandardCharsets.UTF_8);
        } catch (java.nio.charset.MalformedInputException e) {
            return Files.readAllLines(path, StandardCharsets.ISO_8859_1);
        }
    }

    /** 마지막 N 줄. tail -n N 등가. */
    static List<String> tailLines(Path path, int n) throws IOException {
        Deque<String> dq = new ArrayDeque<>(n);
        try (BufferedReader br = newReader(path)) {
            String s;
            while ((s = br.readLine()) != null) {
                if (dq.size() == n) dq.pollFirst();
                dq.addLast(s);
            }
        }
        return new ArrayList<>(dq);
    }

    private static BufferedReader newReader(Path path) throws IOException {
        try {
            return Files.newBufferedReader(path, StandardCharsets.UTF_8);
        } catch (java.nio.charset.MalformedInputException e) {
            return Files.newBufferedReader(path, StandardCharsets.ISO_8859_1);
        }
    }

    /**
     * 원본 _time_match + search 필터.
     * - search: case-insensitive substring(원본 grep -i).
     * - time_from / time_to: HH:MM:SS(.mmm). 12자리 zero-padding 후 사전식 비교.
     * - 타임스탬프 없는 행: 직전 행이 범위 내였으면 포함(stack trace 보존).
     */
    static List<String> filterLines(List<String> lines, String search, String timeFrom, String timeTo) {
        boolean hasTime = !timeFrom.isEmpty() || !timeTo.isEmpty();
        String tf = padTime(timeFrom.isEmpty() ? "00:00:00.000" : timeFrom, '0');
        String tt = padTime(timeTo.isEmpty()   ? "23:59:59.999" : timeTo,   '9');
        String searchLow = search.toLowerCase();
        boolean hasSearch = !search.isEmpty();
        boolean lastInRange = false;

        List<String> out = new ArrayList<>();
        for (String line : lines) {
            if (hasSearch && !line.toLowerCase().contains(searchLow)) continue;
            boolean keepByTime;
            if (!hasTime) {
                keepByTime = true;
            } else {
                Matcher m = TIME_RE.matcher(line);
                if (m.find()) {
                    String ts = padTime(m.group(1), '0');
                    lastInRange = (tf.compareTo(ts) <= 0) && (ts.compareTo(tt) <= 0);
                    keepByTime = lastInRange;
                } else {
                    keepByTime = lastInRange;
                }
            }
            if (keepByTime) out.add(line);
        }
        return out;
    }

    /** 12자리(HH:MM:SS.mmm)로 우측 패딩. */
    static String padTime(String s, char pad) {
        if (s == null) s = "";
        if (s.length() >= 12) return s.substring(0, 12);
        StringBuilder b = new StringBuilder(12).append(s);
        while (b.length() < 12) b.append(pad);
        return b.toString();
    }

    private static String nz(String s) { return s == null ? "" : s.trim(); }
}
