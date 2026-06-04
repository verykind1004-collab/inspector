package com.exem.inspector.screen.dgxml;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.exem.inspector.config.ServiceConfig;

/**
 * DGServer.xml Parameter Modify (process/param) — 원본 pages/dgxml_modify.py 1:1.
 *
 * <ul>
 *   <li>parseAll — DGServer_M/S* home/conf/DGServer.xml 파싱 (param/value/disabled)</li>
 *   <li>search(param_name) — 모든 DGServer 의 param 값 검색</li>
 *   <li>save(changes) — 변경 일괄 저장 + .bak_YYMMDD_seq 백업</li>
 * </ul>
 */
@Service
public class DgxmlService {

    private static final Logger log = LoggerFactory.getLogger(DgxmlService.class);

    /** 원본 RE_PARAM: <(\w+)(?:\s[^>]*)?>([^<]+)</\1>. */
    private static final Pattern RE_PARAM =
            Pattern.compile("<(\\w+)(?:\\s[^>]*)?>([^<]+)</\\1>");

    private static final DateTimeFormatter YYMMDD = DateTimeFormatter.ofPattern("yyMMdd");

    private final ServiceConfig serviceConfig;

    public DgxmlService(ServiceConfig serviceConfig) {
        this.serviceConfig = serviceConfig;
    }

    // ── parseAll — 원본 _parse_all_params 1:1 ─────────────────────────

    public List<DgxmlFile> parseAll() {
        com.exem.inspector.config.ServicesBlock svc = serviceConfig.services();
        List<String[]> homes = new ArrayList<>();
        String dgm = svc.dgserverM();
        if (dgm != null && !dgm.isEmpty()) homes.add(new String[] { "DGServer_M", dgm });
        List<String> dgsList = svc.dgserverS();
        for (int i = 0; i < dgsList.size(); i++) {
            String h = dgsList.get(i);
            if (h != null && !h.isEmpty()) homes.add(new String[] { "DGServer_S" + (i + 1), h });
        }

        List<DgxmlFile> result = new ArrayList<>();
        for (String[] hp : homes) {
            String name = hp[0];
            String home = hp[1];
            Path xmlfile = Paths.get(home, "conf", "DGServer.xml");
            String safeId = name.toLowerCase().replaceAll("[^a-z0-9]", "");
            if (!Files.exists(xmlfile)) {
                result.add(new DgxmlFile(name, xmlfile.toString(), safeId,
                        Collections.emptyList(), "File not found"));
                continue;
            }
            try {
                List<String> lines = Files.readAllLines(xmlfile, StandardCharsets.UTF_8);
                List<DgxmlParam> parsed = new ArrayList<>();
                for (String line : lines) {
                    String stripped = line.trim();
                    if (stripped.isEmpty()) continue;
                    Matcher m = RE_PARAM.matcher(stripped);
                    if (m.find()) {
                        int commentPos = stripped.indexOf("<!--");
                        boolean isDisabled = commentPos >= 0 && commentPos < m.start();
                        parsed.add(new DgxmlParam(isDisabled, m.group(1), m.group(2)));
                    }
                }
                result.add(new DgxmlFile(name, xmlfile.toString(), safeId, parsed, null));
            } catch (IOException e) {
                result.add(new DgxmlFile(name, xmlfile.toString(), safeId,
                        Collections.emptyList(), e.getMessage()));
            }
        }
        return result;
    }

    // ── search — 원본 api_dgxml_param_search 1:1 ──────────────────────

    public SearchResult search(String paramName) {
        if (paramName == null || paramName.trim().isEmpty()) {
            return SearchResult.error("Empty parameter name");
        }
        List<DgxmlFile> all = parseAll();
        if (all.isEmpty()) return SearchResult.error("No DGServer configured");

        List<SearchEntry> results = new ArrayList<>();
        for (DgxmlFile f : all) {
            if (f.error != null) {
                results.add(new SearchEntry(f.dgserver, f.xmlfile, paramName, "-", "Error"));
                continue;
            }
            boolean found = false;
            for (DgxmlParam p : f.params) {
                if (paramName.equals(p.key)) {
                    results.add(new SearchEntry(f.dgserver, f.xmlfile, p.key, p.value,
                            p.isDisabled ? "Disable" : "Enable"));
                    found = true;
                    break;
                }
            }
            if (!found) {
                results.add(new SearchEntry(f.dgserver, f.xmlfile, paramName, "-", "Not Found"));
            }
        }
        return SearchResult.ok(results);
    }

    // ── save — 원본 api_dgxml_param_save 1:1 ──────────────────────────

    public SaveResult save(SaveRequest req) {
        if (req == null || req.changes == null || req.changes.isEmpty()) {
            return SaveResult.error("No changes provided");
        }
        List<SaveEntry> results = new ArrayList<>();
        for (ChangeItem ch : req.changes) {
            String xmlfile = ch.xmlfile == null ? "" : ch.xmlfile;
            String param = ch.param == null ? "" : ch.param;
            String newStatus = ch.status == null ? "" : ch.status.trim();
            String newValue = ch.value;

            boolean hasStatus = "Enable".equals(newStatus) || "Disable".equals(newStatus);
            boolean hasValue = newValue != null && !newValue.isEmpty();

            // Legacy single-action form
            String legacy = ch.action == null ? "" : ch.action.trim().toLowerCase();
            if (!hasStatus && !hasValue && !legacy.isEmpty()) {
                if ("enable".equals(legacy)) { newStatus = "Enable"; hasStatus = true; }
                else if ("disable".equals(legacy)) { newStatus = "Disable"; hasStatus = true; }
                else if ("value".equals(legacy)) { hasValue = newValue != null && !newValue.isEmpty(); }
            }

            Path path = Paths.get(xmlfile);
            if (xmlfile.isEmpty() || param.isEmpty() || !Files.exists(path)) {
                results.add(new SaveEntry(xmlfile, "error", "File not found", null));
                continue;
            }
            if (!hasStatus && !hasValue) {
                results.add(new SaveEntry(xmlfile, "no_change", null, null));
                continue;
            }
            try {
                String today = LocalDate.now().format(YYMMDD);
                int seq = 0;
                Path bak;
                while (true) {
                    bak = Paths.get(xmlfile + ".bak_" + today + "_" + seq);
                    if (!Files.exists(bak)) break;
                    seq++;
                }
                Files.copy(path, bak, StandardCopyOption.COPY_ATTRIBUTES);

                List<String> lines = Files.readAllLines(path, StandardCharsets.UTF_8);
                Pattern tagRe = Pattern.compile(
                        "(<" + Pattern.quote(param) + "(?:\\s[^>]*)?>)(.*?)(</" + Pattern.quote(param) + ">)");

                List<String> newLines = new ArrayList<>(lines.size());
                boolean modified = false;
                for (String line : lines) {
                    int leadLen = line.length() - leftTrim(line).length();
                    String indent = line.substring(0, leadLen);
                    String stripped = stripNewline(line).trim();

                    boolean isCommented = stripped.startsWith("<!--") && stripped.endsWith("-->");
                    String inner = isCommented ? stripped.substring(4, stripped.length() - 3).trim() : stripped;
                    if (!tagRe.matcher(inner).find()) {
                        newLines.add(line);
                        continue;
                    }
                    if (hasValue) {
                        Matcher m = tagRe.matcher(inner);
                        StringBuffer sb = new StringBuffer();
                        while (m.find()) {
                            m.appendReplacement(sb, Matcher.quoteReplacement(m.group(1) + newValue + m.group(3)));
                        }
                        m.appendTail(sb);
                        inner = sb.toString();
                    }
                    boolean wantCommented = hasStatus ? "Disable".equals(newStatus) : isCommented;
                    String rebuilt = wantCommented ? ("<!--" + inner + "-->") : inner;
                    String newLine = indent + rebuilt + "\n";
                    if (!newLine.equals(line.endsWith("\n") ? line : (line + "\n"))) modified = true;
                    newLines.add(newLine);
                }
                if (modified) {
                    StringBuilder sb = new StringBuilder();
                    for (String l : newLines) sb.append(l);
                    Files.write(path, sb.toString().getBytes(StandardCharsets.UTF_8));
                    results.add(new SaveEntry(xmlfile, "ok", null, bak.getFileName().toString()));
                } else {
                    Files.deleteIfExists(bak);
                    results.add(new SaveEntry(xmlfile, "no_change", null, null));
                }
            } catch (IOException | RuntimeException e) {
                String msg = e.getMessage();
                if (msg != null && msg.length() > 200) msg = msg.substring(0, 200);
                results.add(new SaveEntry(xmlfile, "error", msg, null));
            }
        }
        return SaveResult.ok(results);
    }

    private static String leftTrim(String s) {
        int i = 0;
        while (i < s.length() && Character.isWhitespace(s.charAt(i))) i++;
        return s.substring(i);
    }

    private static String stripNewline(String s) {
        if (s.endsWith("\n")) s = s.substring(0, s.length() - 1);
        if (s.endsWith("\r")) s = s.substring(0, s.length() - 1);
        return s;
    }

    // ── DTOs ───────────────────────────────────────────────────────────

    public static final class DgxmlParam {
        public final boolean isDisabled;
        public final String key;
        public final String value;
        public DgxmlParam(boolean isDisabled, String key, String value) {
            this.isDisabled = isDisabled; this.key = key; this.value = value;
        }
        public boolean getIsDisabled() { return isDisabled; }
        public String getKey() { return key; }
        public String getValue() { return value; }
    }

    public static final class DgxmlFile {
        public final String dgserver;
        public final String xmlfile;
        public final String safeId;
        public final List<DgxmlParam> params;
        public final String error;
        public DgxmlFile(String dgserver, String xmlfile, String safeId,
                         List<DgxmlParam> params, String error) {
            this.dgserver = dgserver; this.xmlfile = xmlfile; this.safeId = safeId;
            this.params = params; this.error = error;
        }
        public String getDgserver() { return dgserver; }
        public String getXmlfile() { return xmlfile; }
        public String getSafeId() { return safeId; }
        public List<DgxmlParam> getParams() { return params; }
        public String getError() { return error; }
    }

    public static final class SearchEntry {
        public final String dgserver;
        public final String xmlfile;
        public final String param;
        public final String value;
        public final String status;  // Enable / Disable / Not Found / Error
        public SearchEntry(String dgserver, String xmlfile, String param, String value, String status) {
            this.dgserver = dgserver; this.xmlfile = xmlfile;
            this.param = param; this.value = value; this.status = status;
        }
        public String getDgserver() { return dgserver; }
        public String getXmlfile() { return xmlfile; }
        public String getParam() { return param; }
        public String getValue() { return value; }
        public String getStatus() { return status; }
    }

    public static final class SearchResult {
        public final boolean ok;
        public final String error;
        public final List<SearchEntry> results;
        private SearchResult(boolean ok, String error, List<SearchEntry> results) {
            this.ok = ok; this.error = error; this.results = results;
        }
        public static SearchResult ok(List<SearchEntry> r) { return new SearchResult(true, null, r); }
        public static SearchResult error(String e) { return new SearchResult(false, e, Collections.emptyList()); }
        public boolean isOk() { return ok; }
        public String getError() { return error; }
        public List<SearchEntry> getResults() { return results; }
    }

    public static final class ChangeItem {
        public String xmlfile;
        public String param;
        public String status;
        public String value;
        public String action;  // legacy
        public ChangeItem() {}
        public String getXmlfile() { return xmlfile; }
        public void setXmlfile(String v) { xmlfile = v; }
        public String getParam() { return param; }
        public void setParam(String v) { param = v; }
        public String getStatus() { return status; }
        public void setStatus(String v) { status = v; }
        public String getValue() { return value; }
        public void setValue(String v) { value = v; }
        public String getAction() { return action; }
        public void setAction(String v) { action = v; }
    }

    public static final class SaveRequest {
        public List<ChangeItem> changes;
        public List<ChangeItem> getChanges() { return changes; }
        public void setChanges(List<ChangeItem> v) { changes = v; }
    }

    public static final class SaveEntry {
        public final String xmlfile;
        public final String status;   // ok / no_change / error
        public final String message;
        public final String backup;
        public SaveEntry(String xmlfile, String status, String message, String backup) {
            this.xmlfile = xmlfile; this.status = status; this.message = message; this.backup = backup;
        }
        public String getXmlfile() { return xmlfile; }
        public String getStatus() { return status; }
        public String getMessage() { return message; }
        public String getBackup() { return backup; }
    }

    public static final class SaveResult {
        public final boolean ok;
        public final String error;
        public final List<SaveEntry> results;
        private SaveResult(boolean ok, String error, List<SaveEntry> results) {
            this.ok = ok; this.error = error; this.results = results;
        }
        public static SaveResult ok(List<SaveEntry> r) { return new SaveResult(true, null, r); }
        public static SaveResult error(String e) { return new SaveResult(false, e, Collections.emptyList()); }
        public boolean isOk() { return ok; }
        public String getError() { return error; }
        public List<SaveEntry> getResults() { return results; }
    }

    // Suppress unused (Map import 잠재)
    @SuppressWarnings("unused")
    private static <K, V> Map<K, V> _emptyMap() { return new LinkedHashMap<>(); }
}
