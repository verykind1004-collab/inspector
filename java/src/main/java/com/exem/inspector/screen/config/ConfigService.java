package com.exem.inspector.screen.config;

import java.io.File;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.exem.inspector.config.ServiceConfig;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

/**
 * Config Page 의 read/write/connection-test + Inspector History config CRUD.
 *
 * <p>read = service_config.json 그대로 노출. write = 새 본문 저장 + ServiceConfig.reload().
 * connection-test = Repository DB TCP + 각 서비스 home 디렉토리 존재 여부.
 * insp-history = insp_config.json (Inspector History 설정) read/save.
 */
@Service
public class ConfigService {

    private static final Logger log = LoggerFactory.getLogger(ConfigService.class);

    private final ServiceConfig serviceConfig;
    private final String configPath;
    private final String inspConfigPath;
    private final ObjectMapper objectMapper = new ObjectMapper()
            .enable(SerializationFeature.INDENT_OUTPUT);

    public ConfigService(ServiceConfig serviceConfig,
                         @Value("${inspector.service-config-path}") String configPath,
                         @Value("${inspector.insp-config-path:config/insp_config.json}") String inspConfigPath) {
        this.serviceConfig = serviceConfig;
        this.configPath = configPath;
        this.inspConfigPath = inspConfigPath;
    }

    /** 현재 service_config.json 내용을 그대로 읽어 노출. */
    @SuppressWarnings("unchecked")
    public ConfigPagePayload read() {
        Path path = Paths.get(configPath);
        Map<String, Object> root = new LinkedHashMap<>();
        if (Files.exists(path)) {
            try {
                root = objectMapper.readValue(path.toFile(), Map.class);
            } catch (IOException e) {
                log.warn("service_config.json read 실패", e);
            }
        }
        Map<String, Object> repository = asMap(root.get("repository"));
        Map<String, Object> services = asMap(root.get("services"));
        Map<String, Object> logPaths = asMap(root.get("log_paths"));
        return new ConfigPagePayload(repository, services, logPaths, path.toString());
    }

    /** 새 본문 저장 — root 객체 그대로 받음. 저장 후 ServiceConfig.reload(). */
    public void write(Map<String, Object> body) throws IOException {
        if (body == null) throw new IllegalArgumentException("Body is required");
        Path path = Paths.get(configPath);
        Files.createDirectories(path.getParent());
        String json = objectMapper.writeValueAsString(body);
        Files.write(path, json.getBytes(StandardCharsets.UTF_8));
        serviceConfig.reload();
    }

    /** 원본 api_connection_test 와 동등(단순화 — TCP listen 만). */
    public ConnectionTestResult connectionTest() {
        List<ConnectionTestResult.Item> out = new ArrayList<>();

        com.exem.inspector.common.db.RepositoryConfig repo = serviceConfig.repository();
        if (repo.isConfigured()) {
            int port = repo.port() > 0 ? repo.port() : 1521;
            String dbType = repo.dbType();
            String label = "Repository DB (" + dbType + ")";
            String detail = repo.ip() + ":" + port;
            try (Socket s = new Socket()) {
                s.connect(new InetSocketAddress(repo.ip(), port), 3000);
                out.add(new ConnectionTestResult.Item(label, "OK", detail));
            } catch (IOException e) {
                out.add(new ConnectionTestResult.Item(label, "FAIL", e.getMessage()));
            }
        } else {
            out.add(new ConnectionTestResult.Item("Repository DB", "SKIP", "Not configured"));
        }

        com.exem.inspector.config.ServicesBlock svc = serviceConfig.services();
        addPathProbe(out, "DGServer_M", svc.dgserverM());
        List<String> sList = svc.dgserverS();
        for (int i = 0; i < sList.size(); i++) {
            addPathProbe(out, "DGServer_S" + (i + 1), sList.get(i));
        }
        addPathProbe(out, "PlatformJS", svc.platformjs());

        return new ConnectionTestResult(out);
    }

    private void addPathProbe(List<ConnectionTestResult.Item> out, String name, String home) {
        if (home == null || home.isEmpty()) {
            out.add(new ConnectionTestResult.Item(name, "SKIP", "Not configured"));
            return;
        }
        File f = new File(home);
        if (f.isDirectory()) {
            out.add(new ConnectionTestResult.Item(name, "OK", home));
        } else {
            out.add(new ConnectionTestResult.Item(name, "FAIL", "Path not found: " + home));
        }
    }

    // ── Inspector History config (insp_config.json) ─────────────────────────

    /** 원본 history.py::_load_insp_config 1:1 — 누락 키는 default 로 채움. */
    @SuppressWarnings("unchecked")
    public InspHistoryConfig readInspHistory() {
        Path path = Paths.get(inspConfigPath);
        if (!Files.exists(path)) return InspHistoryConfig.defaults();
        try {
            Map<String, Object> raw = objectMapper.readValue(path.toFile(), Map.class);
            return new InspHistoryConfig(
                    bool(raw.get("enabled"), false),
                    bool(raw.get("tables_initialized"), false),
                    intVal(raw.get("retention_days"), 31),
                    intVal(raw.get("log_retention_days"), 10));
        } catch (IOException e) {
            log.warn("insp_config.json read 실패 — default 사용", e);
            return InspHistoryConfig.defaults();
        }
    }

    /** insp_config.json 저장 — 원본 키 순서 보존(enabled / tables_initialized / retention_days / log_retention_days). */
    public InspHistoryConfig saveInspHistory(InspHistoryConfig body) throws IOException {
        if (body == null) throw new IllegalArgumentException("Body is required");
        Path path = Paths.get(inspConfigPath);
        if (path.getParent() != null) Files.createDirectories(path.getParent());
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("enabled", body.isEnabled());
        out.put("tables_initialized", body.isTablesInitialized());
        out.put("retention_days", body.getRetentionDays());
        out.put("log_retention_days", body.getLogRetentionDays());
        String json = objectMapper.writeValueAsString(out);
        Files.write(path, json.getBytes(StandardCharsets.UTF_8));
        return body;
    }

    public String getInspConfigPath() { return inspConfigPath; }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> asMap(Object o) {
        if (o instanceof Map) return (Map<String, Object>) o;
        return Collections.emptyMap();
    }

    private static boolean bool(Object o, boolean defv) {
        if (o instanceof Boolean) return (Boolean) o;
        if (o == null) return defv;
        String s = String.valueOf(o).trim().toLowerCase();
        if (s.equals("true") || s.equals("1") || s.equals("yes")) return true;
        if (s.equals("false") || s.equals("0") || s.equals("no")) return false;
        return defv;
    }

    private static int intVal(Object o, int defv) {
        if (o instanceof Number) return ((Number) o).intValue();
        if (o == null) return defv;
        try { return Integer.parseInt(String.valueOf(o).trim()); }
        catch (NumberFormatException e) { return defv; }
    }
}
