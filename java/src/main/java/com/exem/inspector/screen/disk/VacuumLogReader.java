package com.exem.inspector.screen.disk;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
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
import com.exem.inspector.screen.overview.DgServerXmlReader;

/**
 * Vacuum Log 파서 — DGServer_M 의 DGM 로그에서 'POSTGRESQL VACUUM' 라인을 모아
 * (schema, start, end, duration) 행 목록을 만든다.
 *
 * <p>원본 disk.py::_vacuum_log_html (line 29~104) 1:1 동등.
 *
 * <p>데이터 소스 우선순위 (원본과 동일):
 * <ol>
 *   <li>오늘 날짜 zip: {@code <log_dir>/DGM_<port>_<YYYYMMDD>_0.log.zip} — 압축 풀어 첫 entry 파싱</li>
 *   <li>fallback: 현 logfile {@code <log_dir>/DGM_<port>.log}</li>
 * </ol>
 *
 * <p>파싱 규칙 (원본 _parse_vacuum_lines):
 * <ul>
 *   <li>라인에 'POSTGRESQL VACUUM' 포함</li>
 *   <li>{@code [HH:MM:SS.mmm]} 시각 추출</li>
 *   <li>{@code schema_name=XXX} 스키마명 추출</li>
 *   <li>'start' 라인 → {@code starts[sch] = t}</li>
 *   <li>'end' 라인 → {@code el=Xms} 경과 ms → 초.소수3자리 / starts 의 시작 시각 → row</li>
 * </ul>
 */
@Component
public class VacuumLogReader {

    private static final Logger log = LoggerFactory.getLogger(VacuumLogReader.class);

    private static final Pattern TIME_RE = Pattern.compile("\\[(\\d{2}:\\d{2}:\\d{2}\\.\\d{3})\\]");
    private static final Pattern SCHEMA_RE = Pattern.compile("schema_name=([^, \\n]+)");
    private static final Pattern EL_RE = Pattern.compile("el=(\\d+)ms");
    private static final DateTimeFormatter TODAY_FMT = DateTimeFormatter.ofPattern("yyyyMMdd");

    /** 원본 _parse_vacuum_lines 의 한 행 — (schema, startTime, endTime, duration). */
    public static final class VacuumLogRow {
        private final String schema;
        private final String startTime;
        private final String endTime;
        private final String duration;

        public VacuumLogRow(String schema, String startTime, String endTime, String duration) {
            this.schema = schema; this.startTime = startTime;
            this.endTime = endTime; this.duration = duration;
        }
        public String getSchema() { return schema; }
        public String getStartTime() { return startTime; }
        public String getEndTime() { return endTime; }
        public String getDuration() { return duration; }
    }

    /** 결과 봉투 — rows + source(파일명) + error. */
    public static final class VacuumLogResult {
        private final List<VacuumLogRow> rows;
        private final String source;
        private final String error;

        private VacuumLogResult(List<VacuumLogRow> rows, String source, String error) {
            this.rows = rows; this.source = source; this.error = error;
        }
        public static VacuumLogResult ok(List<VacuumLogRow> rows, String source) {
            return new VacuumLogResult(rows, source, null);
        }
        public static VacuumLogResult error(String message) {
            return new VacuumLogResult(Collections.emptyList(), null, message);
        }
        public List<VacuumLogRow> getRows() { return rows; }
        public String getSource() { return source; }
        public String getError() { return error; }
    }

    private final ServiceConfig serviceConfig;
    private final DgServerXmlReader xmlReader;

    public VacuumLogReader(ServiceConfig serviceConfig, DgServerXmlReader xmlReader) {
        this.serviceConfig = serviceConfig;
        this.xmlReader = xmlReader;
    }

    /** 메인 진입점 — 원본 _vacuum_log_html 의 본문 로직(파싱까지) 동등. */
    public VacuumLogResult read() {
        String dgmHome = serviceConfig.services().dgserverM();
        if (dgmHome == null || dgmHome.trim().isEmpty()) {
            return VacuumLogResult.error("DGServer_M 경로가 설정되지 않았습니다. Go to Configuration.");
        }
        Path xmlFile = Paths.get(dgmHome, "conf", "DGServer.xml");
        String portStr = xmlReader.readTagValue(xmlFile, "gather_port");
        Path logDir = Paths.get(dgmHome, "log");
        Path logFile = logDir.resolve("DGM_" + portStr + ".log");

        List<VacuumLogRow> rows = Collections.emptyList();
        String source = "";

        try {
            // 1. 오늘 날짜 zip 우선
            Path todayZip = findTodayZip(logDir, portStr);
            if (todayZip != null) {
                List<String> zipLines = readZipFirstEntry(todayZip);
                rows = parseVacuumLines(zipLines);
                source = todayZip.getFileName().toString();
            }
            // 2. zip 없거나 결과 없으면 logfile fallback
            if (rows.isEmpty()) {
                if (Files.isRegularFile(logFile)) {
                    List<String> lines = Files.readAllLines(logFile, StandardCharsets.UTF_8);
                    rows = parseVacuumLines(lines);
                    source = logFile.getFileName().toString();
                } else if (todayZip == null) {
                    return VacuumLogResult.error("로그 파일을 찾을 수 없습니다: " + logFile);
                }
            }
        } catch (IOException e) {
            log.warn("Vacuum log 읽기 실패 dgmHome={}", dgmHome, e);
            return VacuumLogResult.error("로그 읽기 오류: " + e.getMessage());
        }
        return VacuumLogResult.ok(rows, source);
    }

    /** ScreenView 호환 응답 변환 — 컬럼 메타 + rows. UI 가 단일 표 카드로 렌더. */
    public Map<String, Object> toScreenPayload() {
        VacuumLogResult res = read();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("source", res.source == null ? "" : res.source);
        payload.put("error", res.error);
        List<Map<String, Object>> rowMaps = new ArrayList<>();
        // 원본은 최근 100건만 출력. rows[-100:] 동등.
        int from = Math.max(0, res.rows.size() - 100);
        for (int i = from; i < res.rows.size(); i++) {
            VacuumLogRow r = res.rows.get(i);
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("schema", r.schema);
            m.put("start_time", r.startTime);
            m.put("end_time", r.endTime);
            m.put("duration", r.duration);
            rowMaps.add(m);
        }
        payload.put("rows", rowMaps);
        return payload;
    }

    private Path findTodayZip(Path logDir, String portStr) {
        String today = LocalDate.now().format(TODAY_FMT);
        Path candidate = logDir.resolve("DGM_" + portStr + "_" + today + "_0.log.zip");
        return Files.isRegularFile(candidate) ? candidate : null;
    }

    private List<String> readZipFirstEntry(Path zipPath) throws IOException {
        try (ZipFile zip = new ZipFile(zipPath.toFile())) {
            ZipEntry entry = zip.entries().hasMoreElements() ? zip.entries().nextElement() : null;
            if (entry == null) return Collections.emptyList();
            try (InputStream is = zip.getInputStream(entry);
                 BufferedReader br = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
                List<String> lines = new ArrayList<>();
                String line;
                while ((line = br.readLine()) != null) lines.add(line);
                return lines;
            }
        }
    }

    /**
     * 원본 _parse_vacuum_lines 1:1.
     * 'POSTGRESQL VACUUM' 라인만 추리고 start/end 매칭으로 (schema, start, end, durationSeconds) 생성.
     * el=Xms → "X.XXXs" 형식 (3자리 소수).
     */
    List<VacuumLogRow> parseVacuumLines(List<String> lines) {
        List<VacuumLogRow> rows = new ArrayList<>();
        Map<String, String> starts = new LinkedHashMap<>();
        for (String line : lines) {
            if (!line.contains("POSTGRESQL VACUUM")) continue;
            Matcher tm = TIME_RE.matcher(line);
            String t = tm.find() ? tm.group(1) : "-";
            Matcher sm = SCHEMA_RE.matcher(line);
            String sch = sm.find() ? sm.group(1) : "-";
            if (line.contains("start")) {
                starts.put(sch, t);
            } else if (line.contains("end")) {
                Matcher elm = EL_RE.matcher(line);
                String duration = "-";
                if (elm.find()) {
                    int ms = Integer.parseInt(elm.group(1));
                    duration = String.format("%.3fs", ms / 1000.0);
                }
                String st = starts.getOrDefault(sch, "-");
                rows.add(new VacuumLogRow(sch, st, t, duration));
            }
        }
        return rows;
    }
}
