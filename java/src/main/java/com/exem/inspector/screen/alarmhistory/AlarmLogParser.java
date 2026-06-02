package com.exem.inspector.screen.alarmhistory;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Collections;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import com.exem.inspector.config.ServiceConfig;

/**
 * Alarm send 로그 파서 — 원본 _find_alert_logs + _parse_send_logs 1:1 동등.
 *
 * <ul>
 *   <li>각 DGServer_S 의 svc/log 디렉토리에서 {@code sms.log}/{@code api.log}/{@code mail.log} (라이브) +
 *       {@code <kind>_yyyymmdd_<seq>.log.zip} (selDate 일치) 수집.</li>
 *   <li>{@code <kind>.jar} 존재 여부로 jarActive 판정.</li>
 *   <li>로그 라인 정규식: thread ID → epoch_ms 매핑 → ERROR / Finish / Failed 로 status 결정.
 *       "Connection success" 면 prior failed 도 success 로 갱신. finish 는 prior failed 를 덮어쓰지 않음.</li>
 * </ul>
 */
@Component
public class AlarmLogParser {

    private static final Logger log = LoggerFactory.getLogger(AlarmLogParser.class);

    private static final Pattern EPOCH_RE = Pattern.compile("@1\\s*:\\[.*?,\\s*.*?,\\s*.*?,\\s*\\d+,\\s*(\\d{13}),");
    private static final Pattern THREAD_RE = Pattern.compile("#(\\d+)\\s+@1");
    private static final Pattern EPOCH_RE_API = Pattern.compile("\\[ALARM PARAM\\].*time=(\\d{13})");
    private static final Pattern THREAD_RE_API = Pattern.compile("#(\\d+)\\s+\\[ALARM PARAM\\]");
    private static final Pattern FINISH_RE = Pattern.compile("#(\\d+)\\s+Finish");
    private static final Pattern FAILED_RE = Pattern.compile("#(\\d+)\\s+.*(?:Failed|Exception|\\bError\\b)");
    private static final Pattern ERROR_LEVEL_RE = Pattern.compile("\\[ERROR\\s*\\]\\s*#(\\d+)\\b");
    private static final Pattern ERROR_MSG_RE = Pattern.compile(
            "(java\\.\\S+Exception:\\s*.+|ORA-\\d+.+|연결이 거부됨.*|The Network Adapter.+|Listener refused.+)");
    private static final Pattern THREAD_GENERIC = Pattern.compile("#(\\d+)\\s");

    private static final String[] KINDS = { "sms", "api", "mail" };

    private final ServiceConfig serviceConfig;

    public AlarmLogParser(ServiceConfig serviceConfig) {
        this.serviceConfig = serviceConfig;
    }

    /** 로그 경로 + jarActive 수집. selDate 가 null/빈값이면 모든 zip 포함. */
    public Result findLogs(String selDate) {
        Result r = new Result();
        for (String k : KINDS) r.paths.put(k, new java.util.ArrayList<>());
        for (String k : KINDS) r.jarActive.put(k, false);

        List<String> dgsList = serviceConfig.services().dgserverS();
        String dateTag = selDate == null ? null : selDate.replace("-", "");

        for (String home : dgsList) {
            if (home == null || home.isEmpty()) continue;
            Path svcDir = Paths.get(home, "svc");
            Path logDir = Paths.get(home, "log");
            for (String kind : KINDS) {
                Path jar = svcDir.resolve(kind + ".jar");
                if (Files.isDirectory(svcDir) && Files.exists(jar)) {
                    r.jarActive.put(kind, true);
                }
                for (Path dir : new Path[] { svcDir, logDir }) {
                    if (!Files.isDirectory(dir)) continue;
                    Path live = dir.resolve(kind + ".log");
                    if (Files.exists(live) && !r.paths.get(kind).contains(live)) {
                        r.paths.get(kind).add(live);
                    }
                    Pattern zipP = Pattern.compile("^" + kind + "_(\\d{8})_\\d+\\.log\\.zip$");
                    try (DirectoryStream<Path> ds = Files.newDirectoryStream(dir)) {
                        for (Path p : ds) {
                            String name = p.getFileName().toString();
                            Matcher m = zipP.matcher(name);
                            if (!m.matches()) continue;
                            if (dateTag != null && !m.group(1).equals(dateTag)) continue;
                            if (!r.paths.get(kind).contains(p)) r.paths.get(kind).add(p);
                        }
                    } catch (IOException ignore) { /* best-effort */ }
                }
            }
        }
        return r;
    }

    /** 로그들 파싱 → epoch_ms_str → {status, error}. 원본 _parse_send_logs 와 동등. */
    public Map<String, Status> parseSendLogs(List<Path> paths) {
        Map<String, Status> statusMap = new HashMap<>();
        for (Path p : paths) {
            for (Source s : readSources(p)) {
                parseOne(s.content, statusMap);
            }
        }
        return statusMap;
    }

    private void parseOne(String content, Map<String, Status> statusMap) {
        Map<String, String> threadEpoch = new HashMap<>();
        Map<String, String> threadError = new HashMap<>();
        String[] lines = content.split("\n", -1);

        for (String line : lines) {
            Matcher tm = THREAD_RE.matcher(line);
            Matcher em = EPOCH_RE.matcher(line);
            boolean matchedSms = false;
            if (tm.find() && em.find()) {
                threadEpoch.put(tm.group(1), em.group(1));
                threadError.put(tm.group(1), "");
                matchedSms = true;
            }
            if (!matchedSms) {
                Matcher tm2 = THREAD_RE_API.matcher(line);
                Matcher em2 = EPOCH_RE_API.matcher(line);
                if (tm2.find() && em2.find()) {
                    threadEpoch.put(tm2.group(1), em2.group(1));
                    threadError.put(tm2.group(1), "");
                }
            }

            Matcher errMsg = ERROR_MSG_RE.matcher(line);
            if (errMsg.find()) {
                Matcher gt = THREAD_GENERIC.matcher(line);
                if (gt.find() && threadEpoch.containsKey(gt.group(1))) {
                    String s = errMsg.group(1).trim();
                    if (s.length() > 200) s = s.substring(0, 200);
                    threadError.put(gt.group(1), s);
                }
            }
            Matcher elm = ERROR_LEVEL_RE.matcher(line);
            if (elm.find()) {
                String tid = elm.group(1);
                if (threadEpoch.containsKey(tid)) {
                    String ems = threadEpoch.get(tid);
                    String errStr = threadError.getOrDefault(tid, "");
                    if (errStr.isEmpty()) {
                        errStr = line.trim();
                        if (errStr.length() > 200) errStr = errStr.substring(0, 200);
                    }
                    statusMap.put(ems, new Status("failed", errStr));
                }
            }
            if (line.contains("Connection success")) {
                Matcher gt = THREAD_GENERIC.matcher(line);
                if (gt.find() && threadEpoch.containsKey(gt.group(1))) {
                    statusMap.put(threadEpoch.get(gt.group(1)), new Status("success", ""));
                }
            }
            Matcher fm = FINISH_RE.matcher(line);
            if (fm.find()) {
                String tid = fm.group(1);
                if (threadEpoch.containsKey(tid)) {
                    String ems = threadEpoch.get(tid);
                    Status existing = statusMap.get(ems);
                    if (existing == null || !"failed".equals(existing.status)) {
                        statusMap.put(ems, new Status("success", ""));
                    }
                }
            }
            Matcher flm = FAILED_RE.matcher(line);
            if (flm.find()) {
                String tid = flm.group(1);
                if (threadEpoch.containsKey(tid)) {
                    String ems = threadEpoch.get(tid);
                    String errMsgStr = threadError.getOrDefault(tid, "Connection failed");
                    statusMap.put(ems, new Status("failed", errMsgStr));
                }
            }
        }

        // 2nd pass: Failed 라인 이후 detail 캡처
        for (int i = 0; i < lines.length; i++) {
            Matcher flm = FAILED_RE.matcher(lines[i]);
            if (flm.find()) {
                String tid = flm.group(1);
                if (threadEpoch.containsKey(tid)) {
                    String ems = threadEpoch.get(tid);
                    String errDetail = "";
                    int upper = Math.min(i + 15, lines.length);
                    for (int j = i; j < upper; j++) {
                        Matcher em2 = ERROR_MSG_RE.matcher(lines[j]);
                        if (em2.find()) {
                            errDetail = em2.group(1).trim();
                            break;
                        }
                        if (lines[j].contains("Caused by:")) {
                            errDetail = lines[j].trim();
                            break;
                        }
                    }
                    if (!errDetail.isEmpty() && errDetail.length() > 200) {
                        errDetail = errDetail.substring(0, 200);
                    }
                    Status existing = statusMap.get(ems);
                    if (!errDetail.isEmpty() && existing != null) {
                        statusMap.put(ems, new Status(existing.status, errDetail));
                    }
                }
            }
        }
    }

    private List<Source> readSources(Path p) {
        String name = p.getFileName().toString().toLowerCase();
        if (name.endsWith(".zip")) {
            return readZip(p);
        }
        try {
            return Collections.singletonList(
                    new Source(p.toString(),
                               new String(Files.readAllBytes(p), StandardCharsets.UTF_8)));
        } catch (IOException e) {
            log.debug("로그 읽기 실패: {} ({})", p, e.getMessage());
            return Collections.emptyList();
        }
    }

    private List<Source> readZip(Path p) {
        List<Source> out = new java.util.ArrayList<>();
        try (ZipFile zf = new ZipFile(p.toFile())) {
            Enumeration<? extends ZipEntry> entries = zf.entries();
            while (entries.hasMoreElements()) {
                ZipEntry e = entries.nextElement();
                if (e.isDirectory()) continue;
                try (BufferedReader br = new BufferedReader(
                        new InputStreamReader(zf.getInputStream(e), StandardCharsets.UTF_8))) {
                    StringBuilder sb = new StringBuilder();
                    String l;
                    while ((l = br.readLine()) != null) {
                        sb.append(l).append('\n');
                    }
                    out.add(new Source(e.getName(), sb.toString()));
                }
            }
        } catch (IOException e) {
            log.debug("zip 읽기 실패: {} ({})", p, e.getMessage());
        }
        return out;
    }

    /** _find_alert_logs 반환과 동등. */
    public static final class Result {
        public final Map<String, List<Path>> paths = new LinkedHashMap<>();
        public final Map<String, Boolean> jarActive = new LinkedHashMap<>();
    }

    /** epoch_ms_str → 상태. */
    public static final class Status {
        public final String status; // "success" / "failed"
        public final String error;
        public Status(String status, String error) {
            this.status = status;
            this.error = error;
        }
    }

    /** zip 내부 엔트리 또는 plain 파일. */
    private static final class Source {
        final String name;
        final String content;
        Source(String name, String content) { this.name = name; this.content = content; }
    }
}
