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
 * Config Page 의 read/write/connection-test 서비스 — 원본 config_page.py + config_dump.py 핵심.
 *
 * <p>read = service_config.json 그대로 노출. write = 새 본문 저장 + ServiceConfig.reload().
 * connection-test = Repository DB TCP + DGServer/PJS 포트 listen 점검.
 */
@Service
public class ConfigService {

    private static final Logger log = LoggerFactory.getLogger(ConfigService.class);

    private final ServiceConfig serviceConfig;
    private final String configPath;
    private final ObjectMapper objectMapper = new ObjectMapper()
            .enable(SerializationFeature.INDENT_OUTPUT);

    public ConfigService(ServiceConfig serviceConfig,
                         @Value("${inspector.service-config-path}") String configPath) {
        this.serviceConfig = serviceConfig;
        this.configPath = configPath;
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

        // Repository DB
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

        // DGServer_M / S* / PlatformJS — home 디렉토리 존재 여부 + (있다면) home 표시
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

    @SuppressWarnings("unchecked")
    private static Map<String, Object> asMap(Object o) {
        if (o instanceof Map) return (Map<String, Object>) o;
        return Collections.emptyMap();
    }
}
