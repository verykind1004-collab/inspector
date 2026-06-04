package com.exem.inspector.screen.simple;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import com.exem.inspector.config.ServiceConfig;

/**
 * DGS PORT map resolver — 원본 license.py::_get_dgs_port_map 1:1 동등 (B-1).
 *
 * <p>각 DGServer_S 의 <code>conf/DGServer.xml</code> 에서 gather_port 추출 + log 디렉토리의
 * <code>DGS_&lt;port&gt;.log</code> (또는 가장 최근 DGS_*.log) 를 스캔하여
 * <code>[DB 10MIN SUMMARY] server_id=N</code> 라인의 db_id 별 마지막 시각 + 그 시점 port 매핑.
 *
 * <p>여러 DGS_S 에서 같은 db_id 가 나오면 라인 시각이 가장 늦은 DGS_S 의 gather_port 채택
 * (현재 어디 붙어있는지 반영).
 */
@Component
public class DgsPortResolver {

    private static final Logger log = LoggerFactory.getLogger(DgsPortResolver.class);

    /** 원본 _DGS_SUMMARY_LINE_RE 1:1. */
    private static final Pattern SUMMARY_LINE_RE = Pattern.compile(
            "^\\[(\\d{2}:\\d{2}:\\d{2}\\.\\d+)\\].*?\\[DB 10MIN SUMMARY\\] server_id=(\\d+)");

    /** DGServer.xml gather_port 패턴 — `<gather_port>3000</gather_port>`. */
    private static final Pattern GATHER_PORT_RE = Pattern.compile(
            "<gather_port>\\s*(\\d+)\\s*</gather_port>");

    private final ServiceConfig serviceConfig;

    public DgsPortResolver(ServiceConfig serviceConfig) {
        this.serviceConfig = serviceConfig;
    }

    /** 원본 _get_dgs_port_map 와 동등 — {db_id_str: gather_port_str}. */
    public Map<String, String> resolve() {
        List<String> sHomes = serviceConfig.services().dgserverS();
        Map<String, String> logPaths = collectLogPaths();
        if (sHomes == null || sHomes.isEmpty()) return Collections.emptyMap();

        // per_sid_latest[sid] = (last_seen_HHMMSS, port)
        Map<String, String[]> perSidLatest = new HashMap<>();

        for (int i = 0; i < sHomes.size(); i++) {
            String home = sHomes.get(i);
            if (home == null || home.isEmpty()) continue;
            String logDir = logPaths.get("dgserver_s_" + i);
            if (logDir == null || logDir.isEmpty()) continue;
            try {
                Path xmlfile = Paths.get(home, "conf", "DGServer.xml");
                String port = parseXmlGatherPort(xmlfile);
                if (port == null) continue;

                Path logfile = pickLogFile(Paths.get(logDir), port);
                if (logfile == null) continue;

                Map<String, String> lastBySid = scanLastBySid(logfile);
                for (Map.Entry<String, String> e : lastBySid.entrySet()) {
                    String sid = e.getKey();
                    String t = e.getValue();
                    String[] prev = perSidLatest.get(sid);
                    if (prev == null || t.compareTo(prev[0]) > 0) {
                        perSidLatest.put(sid, new String[] { t, port });
                    }
                }
            } catch (RuntimeException e) {
                log.debug("DGS port resolve 실패: {} ({})", home, e.getMessage());
            }
        }

        Map<String, String> out = new LinkedHashMap<>();
        for (Map.Entry<String, String[]> e : perSidLatest.entrySet()) {
            out.put(e.getKey(), e.getValue()[1]);
        }
        return out;
    }

    /** Reflection 으로 log_paths.dgserver_s 추출 — ServicesBlock 에 직접 노출 없을 수 있어 대비. */
    @SuppressWarnings("unchecked")
    private Map<String, String> collectLogPaths() {
        Map<String, String> out = new HashMap<>();
        try {
            Object svc = serviceConfig.services();
            java.lang.reflect.Method m = svc.getClass().getMethod("logPathsDgserverS");
            Object res = m.invoke(svc);
            if (res instanceof List) {
                List<String> list = (List<String>) res;
                for (int i = 0; i < list.size(); i++) {
                    if (list.get(i) != null && !list.get(i).isEmpty()) {
                        out.put("dgserver_s_" + i, list.get(i));
                    }
                }
            }
        } catch (ReflectiveOperationException e) {
            // ServicesBlock 에 logPathsDgserverS 메서드 없는 경우 — service_config.json 직접 읽기는
            // 다음 보강으로. 현재는 빈 map 반환 → resolver 빈 결과.
            log.debug("ServicesBlock 에 logPathsDgserverS 없음 — log_paths 미적용");
        }
        return out;
    }

    /** XML 파일에서 gather_port 추출 — 단순 regex (XML 파서 대체). */
    static String parseXmlGatherPort(Path xmlfile) {
        if (!Files.exists(xmlfile)) return null;
        try {
            String content = new String(Files.readAllBytes(xmlfile), StandardCharsets.UTF_8);
            Matcher m = GATHER_PORT_RE.matcher(content);
            if (m.find()) return m.group(1);
        } catch (IOException e) {
            return null;
        }
        return null;
    }

    /** DGS_&lt;port&gt;.log 우선, 없으면 디렉토리에서 mtime 최신 DGS_*.log. */
    static Path pickLogFile(Path logDir, String port) {
        Path direct = logDir.resolve("DGS_" + port + ".log");
        if (Files.exists(direct)) return direct;
        if (!Files.isDirectory(logDir)) return null;
        List<Path> candidates = new ArrayList<>();
        try (DirectoryStream<Path> ds = Files.newDirectoryStream(logDir)) {
            for (Path p : ds) {
                String name = p.getFileName().toString();
                if (name.startsWith("DGS_") && name.endsWith(".log")) candidates.add(p);
            }
        } catch (IOException e) {
            return null;
        }
        if (candidates.isEmpty()) return null;
        // mtime DESC — 가장 최근
        candidates.sort((a, b) -> Long.compare(modified(b), modified(a)));
        return candidates.get(0);
    }

    private static long modified(Path p) {
        try { return Files.getLastModifiedTime(p).toMillis(); }
        catch (IOException e) { return 0; }
    }

    /** 로그 파일을 스캔하여 sid → 마지막 시각 매핑 — 파일 끝쪽 = 늦은 시각이라 last-write-wins. */
    static Map<String, String> scanLastBySid(Path logfile) {
        Map<String, String> lastBySid = new HashMap<>();
        try {
            for (String line : Files.readAllLines(logfile, StandardCharsets.UTF_8)) {
                Matcher m = SUMMARY_LINE_RE.matcher(line);
                if (m.find()) lastBySid.put(m.group(2), m.group(1));
            }
        } catch (IOException e) {
            // best-effort
        }
        return lastBySid;
    }
}
