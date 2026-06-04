package com.exem.inspector.screen.partition;

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
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

import com.exem.inspector.common.db.DbType;
import com.exem.inspector.config.ServiceConfig;
import com.exem.inspector.screen.overview.DgServerXmlReader;

/**
 * Partition Time Check — 원본 page_partition_time (partition.py:1426) 1:1.
 *
 * <p>DGServer_M 의 DGM_&lt;port&gt;.log (또는 오늘 zip) 에서 [PARTITION MANAGE] 라인을
 * 파싱하여 CREATE/DROP/COMPRESS 의 START/FINISH 시각을 매칭한다.
 *
 * <ul>
 *   <li>Oracle (_partition_time_html): 단일 표 — CREATE/DROP/COMPRESS 3 행</li>
 *   <li>PostgreSQL (_partition_time_pg_cards): 스키마별 2 카드 — Create / Drop</li>
 * </ul>
 *
 * <p>응답 구조 TimeCheckResult — dbType + source + actions(Oracle) / createBySchema + dropBySchema(PG).
 */
@Service
public class PartitionTimeService {

    private static final Logger log = LoggerFactory.getLogger(PartitionTimeService.class);
    private static final DateTimeFormatter TODAY_FMT = DateTimeFormatter.ofPattern("yyyyMMdd");

    private static final Pattern TIME_RE = Pattern.compile("\\[(\\d{2}:\\d{2}:\\d{2}\\.\\d{3})\\]");
    private static final Pattern ELAPSED_RE = Pattern.compile("elapsed=(\\d+)ms", Pattern.CASE_INSENSITIVE);

    // Oracle 패턴 (원본 _partition_time_html PATTERNS 1:1)
    private static final Pattern ORA_CREATE_START =
            Pattern.compile("\\[PARTITION MANAGE\\]\\s+Create\\s+partition\\s+start", Pattern.CASE_INSENSITIVE);
    private static final Pattern ORA_CREATE_FINISH =
            Pattern.compile("\\[PARTITION MANAGE\\]\\s+Create\\s+partition\\s+finish", Pattern.CASE_INSENSITIVE);
    private static final Pattern ORA_DROP_START =
            Pattern.compile("\\[PARTITION MANAGE\\]\\s+DROP\\s+PARTITION\\s+start\\b", Pattern.CASE_INSENSITIVE);
    private static final Pattern ORA_DROP_FINISH =
            Pattern.compile("\\[PARTITION MANAGE\\]\\s+DROP\\s+PARTITION\\s+finished", Pattern.CASE_INSENSITIVE);
    private static final Pattern ORA_COMPRESS_START =
            Pattern.compile("\\[PARTITION MANAGE\\]\\s+COMPRESS\\s+PARTITION\\s+start\\b(?!\\s*Thread)", Pattern.CASE_INSENSITIVE);
    private static final Pattern ORA_COMPRESS_FINISH =
            Pattern.compile("\\[PARTITION MANAGE\\]\\s+COMPRESS\\s+PARTITION\\s+finished", Pattern.CASE_INSENSITIVE);

    // PG 패턴 (원본 _partition_time_pg_cards 1:1)
    private static final Pattern PG_CREATE_RE = Pattern.compile(
            "\\[PARTITION MANAGE\\]\\s+Created partition\\s+(?<state>start|finish)[,\\s]+Schema:\\s*(?<schema>\\S+)",
            Pattern.CASE_INSENSITIVE);
    private static final Pattern PG_DROP_RE = Pattern.compile(
            "\\[PARTITION MANAGE\\]\\s+Drop Partition\\s+Schema:\\s*(?<schema>\\S+?)\\s+(?<state>strat|start|finished|finish)",
            Pattern.CASE_INSENSITIVE);

    private final ServiceConfig serviceConfig;
    private final DgServerXmlReader xmlReader;
    private final ObjectProvider<PartitionMapper> mapperProvider;

    public PartitionTimeService(ServiceConfig serviceConfig,
                                DgServerXmlReader xmlReader,
                                ObjectProvider<PartitionMapper> mapperProvider) {
        this.serviceConfig = serviceConfig;
        this.xmlReader = xmlReader;
        this.mapperProvider = mapperProvider;
    }

    /** 메인 진입점 — dbType 에 따라 Oracle / PG 분기. */
    public TimeCheckResult check() {
        DbType dbType = DbType.fromConfigValue(serviceConfig.repository().dbType());
        TimeCheckResult result = new TimeCheckResult();
        result.dbType = dbType.name();

        String dgmHome = serviceConfig.services().dgserverM();
        if (dgmHome == null || dgmHome.trim().isEmpty()) {
            result.error = "DGServer_M 경로가 설정되지 않았습니다.";
            return result;
        }
        Path xmlFile = Paths.get(dgmHome, "conf", "DGServer.xml");
        String portStr = xmlReader.readTagValue(xmlFile, "gather_port");
        Path logDir = Paths.get(dgmHome, "log");
        Path logFile = logDir.resolve("DGM_" + portStr + ".log");

        // 1. 오늘 zip 우선 → fallback logfile
        List<String> lines;
        try {
            Path todayZip = findTodayZip(logDir, portStr);
            if (todayZip != null) {
                lines = readZipFirstEntry(todayZip);
                result.source = todayZip.getFileName().toString();
            } else if (Files.isRegularFile(logFile)) {
                lines = Files.readAllLines(logFile, StandardCharsets.UTF_8);
                result.source = logFile.getFileName().toString();
            } else {
                result.error = "로그 파일을 찾을 수 없습니다: " + logFile;
                return result;
            }
        } catch (IOException e) {
            log.warn("DGM 로그 읽기 실패 dgmHome={}", dgmHome, e);
            result.error = "로그 읽기 오류: " + e.getMessage();
            return result;
        }

        if (dbType == DbType.POSTGRESQL) {
            parsePg(lines, result);
        } else {
            parseOracle(lines, result);
        }
        return result;
    }

    // ────────────────────────── Oracle parse ────────────────────────────

    private void parseOracle(List<String> lines, TimeCheckResult result) {
        Map<String, ActionPair> pairs = new LinkedHashMap<>();
        for (String line : lines) {
            if (!line.contains("[PARTITION MANAGE]")) continue;
            String t = extractTime(line);
            String elapsed = extractElapsed(line);
            ActionMatch m = matchOracle(line);
            if (m == null) continue;
            ActionPair p = pairs.computeIfAbsent(m.action, k -> new ActionPair());
            if (m.state == State.START) {
                p.start = trimSeconds(t);
            } else {
                p.finish = trimSeconds(t);
                if (!"-".equals(elapsed)) p.elapsed = elapsed;
            }
        }
        if (pairs.isEmpty()) {
            result.error = "일치하는 패턴이 없습니다.";
            return;
        }
        // 출력 순서: CREATE → DROP → COMPRESS
        for (String action : new String[]{"CREATE", "DROP", "COMPRESS"}) {
            ActionPair p = pairs.get(action);
            if (p == null) continue;
            String start = p.start == null ? "-" : p.start;
            String finish = p.finish == null ? "-" : p.finish;
            String timeStr;
            String status;
            if (!"-".equals(start) && !"-".equals(finish)) {
                timeStr = start + " ~ " + finish;
                status = "OK";
            } else if (!"-".equals(start) || !"-".equals(finish)) {
                timeStr = start + " ~ " + finish;
                status = "CHECK";
            } else {
                timeStr = "-";
                status = "CHECK";
            }
            result.actions.add(new ActionRow(action, timeStr, p.elapsed, status));
        }
    }

    private ActionMatch matchOracle(String line) {
        if (ORA_CREATE_START.matcher(line).find())     return new ActionMatch("CREATE",   State.START);
        if (ORA_CREATE_FINISH.matcher(line).find())    return new ActionMatch("CREATE",   State.FINISH);
        if (ORA_DROP_START.matcher(line).find())       return new ActionMatch("DROP",     State.START);
        if (ORA_DROP_FINISH.matcher(line).find())      return new ActionMatch("DROP",     State.FINISH);
        if (ORA_COMPRESS_START.matcher(line).find())   return new ActionMatch("COMPRESS", State.START);
        if (ORA_COMPRESS_FINISH.matcher(line).find())  return new ActionMatch("COMPRESS", State.FINISH);
        return null;
    }

    // ────────────────────────── PG parse ────────────────────────────────

    private void parsePg(List<String> lines, TimeCheckResult result) {
        Map<String, ActionPair> createPairs = new TreeMap<>();
        Map<String, ActionPair> dropPairs = new TreeMap<>();
        for (String line : lines) {
            if (!line.contains("[PARTITION MANAGE]")) continue;
            String t = extractTime(line);

            Matcher mc = PG_CREATE_RE.matcher(line);
            if (mc.find()) {
                String schema = mc.group("schema").replaceAll(",$", "");
                String state = mc.group("state").toLowerCase();
                ActionPair p = createPairs.computeIfAbsent(schema, k -> new ActionPair());
                if ("finish".equals(state) || "finished".equals(state)) {
                    p.finish = trimSeconds(t);
                    p.elapsed = calcElapsed(p.start, p.finish);
                } else {
                    p.start = trimSeconds(t);
                }
                continue;
            }
            Matcher md = PG_DROP_RE.matcher(line);
            if (md.find()) {
                String schema = md.group("schema").replaceAll(",$", "");
                String state = md.group("state").toLowerCase();
                ActionPair p = dropPairs.computeIfAbsent(schema, k -> new ActionPair());
                if ("finish".equals(state) || "finished".equals(state)) {
                    p.finish = trimSeconds(t);
                    p.elapsed = calcElapsed(p.start, p.finish);
                } else {
                    p.start = trimSeconds(t);
                }
            }
        }

        // apm_db_info 의 instance 풀 — 누락 schema 도 CHECK 로 노출.
        TreeSet<String> allInstances = new TreeSet<>();
        PartitionMapper mapper = mapperProvider.getIfAvailable();
        if (mapper != null) {
            try {
                List<LinkedHashMap<String, Object>> rows = mapper.findInstances();
                for (LinkedHashMap<String, Object> r : rows) {
                    Object v = r.get("instance_name");
                    if (v == null) v = r.get("INSTANCE_NAME");
                    if (v != null) {
                        String s = String.valueOf(v).trim().toLowerCase();
                        if (!s.isEmpty()) allInstances.add(s);
                    }
                }
            } catch (RuntimeException ignored) { /* best-effort */ }
        }

        result.createBySchema.addAll(buildSchemaRows(createPairs, allInstances));
        result.dropBySchema.addAll(buildSchemaRows(dropPairs, allInstances));
    }

    private List<SchemaRow> buildSchemaRows(Map<String, ActionPair> pairs, TreeSet<String> allInstances) {
        List<SchemaRow> out = new ArrayList<>();
        TreeSet<String> shown = new TreeSet<>();
        for (Map.Entry<String, ActionPair> e : pairs.entrySet()) {
            String schema = e.getKey();
            shown.add(schema.toLowerCase());
            ActionPair p = e.getValue();
            String start = p.start == null ? "-" : p.start;
            String finish = p.finish == null ? "-" : p.finish;
            boolean ok = !"-".equals(start) && !"-".equals(finish);
            out.add(new SchemaRow(schema, start + " ~ " + finish, p.elapsed, ok ? "OK" : "CHECK"));
        }
        for (String inst : allInstances) {
            if (!shown.contains(inst)) {
                out.add(new SchemaRow(inst, "-", "-", "CHECK"));
            }
        }
        return out;
    }

    // ────────────────────────── 공통 ────────────────────────────────────

    private static String extractTime(String line) {
        Matcher m = TIME_RE.matcher(line);
        return m.find() ? m.group(1) : "-";
    }

    private static String extractElapsed(String line) {
        Matcher m = ELAPSED_RE.matcher(line);
        if (!m.find()) return "-";
        int ms = Integer.parseInt(m.group(1));
        return String.format("%.3fs", ms / 1000.0);
    }

    /** HH:MM:SS.mmm → HH:MM:SS (원본 t[:8] 1:1). */
    private static String trimSeconds(String t) {
        if (t == null || t.length() < 8) return t;
        return t.substring(0, 8);
    }

    private static String calcElapsed(String start, String finish) {
        if (start == null || finish == null || "-".equals(start) || "-".equals(finish)) return "-";
        Double s = parseTime(start);
        Double e = parseTime(finish);
        if (s == null || e == null) return "-";
        double diff = e - s;
        if (diff < 0) diff += 86400.0;
        return String.format("%.3fs", diff);
    }

    private static Double parseTime(String t) {
        try {
            String[] parts = t.split(":");
            if (parts.length < 3) return null;
            int h = Integer.parseInt(parts[0]);
            int min = Integer.parseInt(parts[1]);
            String sec = parts[2];
            int s;
            int msPart = 0;
            if (sec.contains(".")) {
                String[] sp = sec.split("\\.");
                s = Integer.parseInt(sp[0]);
                msPart = Integer.parseInt(sp[1]);
            } else {
                s = Integer.parseInt(sec);
            }
            return h * 3600.0 + min * 60.0 + s + msPart / 1000.0;
        } catch (NumberFormatException e) {
            return null;
        }
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
                List<String> out = new ArrayList<>();
                String line;
                while ((line = br.readLine()) != null) out.add(line);
                return out;
            }
        }
    }

    // ────────────────────────── 내부 ────────────────────────────────────

    private enum State { START, FINISH }

    private static final class ActionMatch {
        final String action;
        final State state;
        ActionMatch(String action, State state) { this.action = action; this.state = state; }
    }

    private static final class ActionPair {
        String start;
        String finish;
        String elapsed = "-";
    }

    // ────────────────────────── 응답 DTO ────────────────────────────────

    public static final class TimeCheckResult {
        public String dbType;
        public String source = "";
        public String error;
        public final List<ActionRow> actions = new ArrayList<>();        // Oracle 만
        public final List<SchemaRow> createBySchema = new ArrayList<>(); // PG 만
        public final List<SchemaRow> dropBySchema = new ArrayList<>();   // PG 만

        public String getDbType() { return dbType; }
        public String getSource() { return source; }
        public String getError() { return error; }
        public List<ActionRow> getActions() { return actions; }
        public List<SchemaRow> getCreateBySchema() { return createBySchema; }
        public List<SchemaRow> getDropBySchema() { return dropBySchema; }
    }

    public static final class ActionRow {
        public final String action;
        public final String time;
        public final String elapsed;
        public final String status;
        public ActionRow(String action, String time, String elapsed, String status) {
            this.action = action; this.time = time; this.elapsed = elapsed; this.status = status;
        }
        public String getAction() { return action; }
        public String getTime() { return time; }
        public String getElapsed() { return elapsed; }
        public String getStatus() { return status; }
    }

    public static final class SchemaRow {
        public final String schema;
        public final String time;
        public final String elapsed;
        public final String status;
        public SchemaRow(String schema, String time, String elapsed, String status) {
            this.schema = schema; this.time = time; this.elapsed = elapsed; this.status = status;
        }
        public String getSchema() { return schema; }
        public String getTime() { return time; }
        public String getElapsed() { return elapsed; }
        public String getStatus() { return status; }
    }
}
