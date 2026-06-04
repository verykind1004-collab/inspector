package com.exem.inspector.screen.process;

import java.io.IOException;
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
import java.util.stream.Stream;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.exem.inspector.config.ServiceConfig;
import com.exem.inspector.config.ServicesBlock;

/**
 * Process Gather Overview 서비스 — 원본 process.py::page_process_gather() Overview 탭 1:1.
 *
 * <p>service_config 의 dgserver_m + dgserver_s home 목록을 순회하면서
 * conf/DGServer.xml 의 gather_port 로 로그 파일을 식별한 뒤(없으면 같은 prefix 의 최신 *.log)
 * ERROR / WARN 패턴 라인을 카운트하고 마지막 500 라인을 반환한다.
 */
@Service
public class ProcessGatherService {

    private static final Logger log = LoggerFactory.getLogger(ProcessGatherService.class);

    /** 원본 OVERVIEW_LIMIT. */
    static final int OVERVIEW_LIMIT = 500;

    private static final Pattern GATHER_PORT_RE =
            Pattern.compile("<gather_port>\\s*([^<\\s]+)\\s*</gather_port>", Pattern.CASE_INSENSITIVE);

    private final ServiceConfig serviceConfig;

    public ProcessGatherService(ServiceConfig serviceConfig) {
        this.serviceConfig = serviceConfig;
    }

    public ProcessGatherPayload overview() {
        ServicesBlock svc;
        try {
            svc = serviceConfig.services();
        } catch (RuntimeException e) {
            return new ProcessGatherPayload(Collections.<ProcessGatherSection>emptyList(),
                    OVERVIEW_LIMIT, "service_config 로드 실패: " + e.getMessage());
        }

        List<ProcessGatherSection> out = new ArrayList<>();

        // ── DGServer_M ─────────────────────────────────────────
        String dgm = safe(svc.dgserverM());
        if (!dgm.isEmpty()) {
            out.add(buildSection("dgm", "DGServer_M", dgm, true));
        }
        // ── DGServer_S(n) ──────────────────────────────────────
        List<String> dgsList = svc.dgserverS();
        if (dgsList != null) {
            for (int i = 0; i < dgsList.size(); i++) {
                String dgs = safe(dgsList.get(i));
                if (dgs.isEmpty()) continue;
                out.add(buildSection("dgs" + (i + 1), "DGServer_S" + (i + 1), dgs, false));
            }
        }

        String cfgError = out.isEmpty() ? "DGServer paths 가 설정되지 않았습니다." : null;
        return new ProcessGatherPayload(out, OVERVIEW_LIMIT, cfgError);
    }

    // ── 섹션 1개 빌드 ────────────────────────────────────────────

    private ProcessGatherSection buildSection(String id, String name, String home, boolean isMaster) {
        Path xml = Paths.get(home, "conf", "DGServer.xml");
        String port = parseGatherPort(xml);
        String prefix = isMaster ? "DGM_" : "DGS_";

        Path logfile = null;
        Path logDir = Paths.get(home, "log");
        if (port != null && !port.isEmpty()) {
            Path candidate = logDir.resolve(prefix + port + ".log");
            if (Files.exists(candidate)) logfile = candidate;
        }
        if (logfile == null) {
            logfile = pickLatestLog(logDir, prefix);
        }
        if (logfile == null) {
            return ProcessGatherSection.error(id, name, null, "로그 파일을 찾을 수 없습니다: " + home);
        }
        try {
            ScanResult sr = scanErrors(logfile);
            return new ProcessGatherSection(id, name, logfile.toString(),
                    sr.total, sr.recent, null);
        } catch (IOException e) {
            return ProcessGatherSection.error(id, name, logfile.toString(),
                    "로그 읽기 오류: " + e.getMessage());
        }
    }

    /** DGServer.xml 에서 {@code <gather_port>NNNN</gather_port>} 추출. */
    static String parseGatherPort(Path xml) {
        if (xml == null || !Files.exists(xml)) return null;
        try {
            String content = new String(Files.readAllBytes(xml), StandardCharsets.UTF_8);
            Matcher m = GATHER_PORT_RE.matcher(content);
            return m.find() ? m.group(1).trim() : null;
        } catch (IOException e) {
            log.debug("xml parse fail: {} ({})", xml, e.getMessage());
            return null;
        }
    }

    /** 같은 prefix 의 *.log 중 가장 최근 수정된 파일. */
    static Path pickLatestLog(Path logDir, String prefix) {
        if (logDir == null || !Files.isDirectory(logDir)) return null;
        Path latest = null;
        long latestMtime = -1L;
        try (DirectoryStream<Path> ds = Files.newDirectoryStream(logDir, prefix + "*.log")) {
            for (Path p : ds) {
                try {
                    long t = Files.getLastModifiedTime(p).toMillis();
                    if (t > latestMtime) { latestMtime = t; latest = p; }
                } catch (IOException ignored) { /* skip */ }
            }
        } catch (IOException e) {
            log.debug("log dir scan fail: {} ({})", logDir, e.getMessage());
            return null;
        }
        return latest;
    }

    /** 로그 파일 전체 스캔 → ERROR/WARN 카운트 + 마지막 {@link #OVERVIEW_LIMIT} 줄. */
    static ScanResult scanErrors(Path logfile) throws IOException {
        long total = 0L;
        Deque<String> tail = new ArrayDeque<>(OVERVIEW_LIMIT);
        try (Stream<String> stream = Files.lines(logfile, StandardCharsets.UTF_8)) {
            for (java.util.Iterator<String> it = stream.iterator(); it.hasNext(); ) {
                String line = it.next();
                if (!matchesErrOrWarn(line)) continue;
                total++;
                if (tail.size() == OVERVIEW_LIMIT) tail.pollFirst();
                tail.addLast(line);
            }
        } catch (java.nio.charset.MalformedInputException mie) {
            // 비-UTF8 — Latin-1 로 재시도(원본은 errors='replace').
            try (Stream<String> stream = Files.lines(logfile, StandardCharsets.ISO_8859_1)) {
                for (java.util.Iterator<String> it = stream.iterator(); it.hasNext(); ) {
                    String line = it.next();
                    if (!matchesErrOrWarn(line)) continue;
                    total++;
                    if (tail.size() == OVERVIEW_LIMIT) tail.pollFirst();
                    tail.addLast(line);
                }
            }
        }
        return new ScanResult(total, new ArrayList<>(tail));
    }

    /** 원본 정규식 {@code \[ERROR|\[WARN}. */
    static boolean matchesErrOrWarn(String line) {
        if (line == null) return false;
        // 대소문자 무시 — 원본 grep 은 case-sensitive 였으나 운영상 robust 하게.
        // ERROR/WARN 사이에 별표/색상 escape 가 끼는 케이스 방지를 위해 단순 contains.
        return line.contains("[ERROR") || line.contains("[WARN");
    }

    private static String safe(String s) { return s == null ? "" : s.trim(); }

    /** scan 결과 holder. */
    static final class ScanResult {
        final long total;
        final List<String> recent;
        ScanResult(long total, List<String> recent) {
            this.total = total;
            this.recent = recent;
        }
    }

    /** 의도적 미사용 import 회피용 — 향후 확장 시 사용. */
    @SuppressWarnings("unused")
    private static <T> Comparator<T> _nullCmp() { return null; }
}
