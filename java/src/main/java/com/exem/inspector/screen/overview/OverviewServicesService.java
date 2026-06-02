package com.exem.inspector.screen.overview;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Service;

import com.exem.inspector.common.db.DbType;
import com.exem.inspector.common.db.RepositoryConfig;
import com.exem.inspector.config.ServiceConfig;
import com.exem.inspector.config.ServicesBlock;

/**
 * Overview Services 카드 — DGServer_M / DGServer_S* / PlatformJS / Repo DB.
 *
 * <p>원본 overview.py::_services_table_html / page_services / api_services 의
 * 데이터 부분을 그대로 JSON 으로 반환한다(HTML 렌더링은 프런트가 담당).
 *
 * <p>본 단계 단순화:
 * <ul>
 *   <li>process 식별 = TCP 포트 listen 여부 (원본 ss/netstat + ps 폴백 중 TCP listen 만 채택)</li>
 *   <li>DGServer 의 gather_port 는 DGServer.xml 에서 직접 파싱</li>
 *   <li>PlatformJS 포트는 일단 8888 기본값(추후 config 도입 시 갱신)</li>
 *   <li>버전은 home/version 파일 우선 — 없으면 "-"</li>
 *   <li>Repo DB = ServiceConfig.repository().ip:port TCP listen 체크</li>
 * </ul>
 */
@Service
public class OverviewServicesService {

    private static final int PLATFORMJS_DEFAULT_PORT = 8888;

    private final ServiceConfig serviceConfig;
    private final PortChecker portChecker;
    private final DgServerXmlReader xmlReader;
    private final VersionReader versionReader;

    public OverviewServicesService(ServiceConfig serviceConfig, PortChecker portChecker,
                                   DgServerXmlReader xmlReader, VersionReader versionReader) {
        this.serviceConfig = serviceConfig;
        this.portChecker = portChecker;
        this.xmlReader = xmlReader;
        this.versionReader = versionReader;
    }

    /** 응답: {@code {services: [{name, status, port, version, home?}, ...]}}. */
    public Map<String, Object> services() {
        ServicesBlock cfg = serviceConfig.services();
        List<Map<String, Object>> rows = new ArrayList<>();

        // DGServer_M
        rows.add(dgRow("DGServer_M", cfg.dgserverM()));

        // DGServer_S*
        List<String> dgsList = cfg.dgserverS();
        for (int i = 0; i < dgsList.size(); i++) {
            String home = dgsList.get(i);
            if (home == null || home.trim().isEmpty()) continue;
            rows.add(dgRow("DGServer_S" + (i + 1), home));
        }

        // PlatformJS
        rows.add(pjsRow(cfg.platformjs()));

        // Client(version only, no process)
        rows.add(clientRow(cfg.platformjs()));

        // Repo DB
        rows.add(repoDbRow());

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("services", rows);
        return out;
    }

    private Map<String, Object> dgRow(String name, String home) {
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("name", name);
        if (home == null || home.trim().isEmpty() || !Files.isDirectory(Paths.get(home))) {
            r.put("status",  "stopped");
            r.put("port",    "-");
            r.put("version", "-");
            r.put("home",    home == null ? "" : home);
            return r;
        }
        Path homePath = Paths.get(home);
        Path xml = homePath.resolve("conf").resolve("DGServer.xml");
        String portStr = xmlReader.readTagValue(xml, "gather_port");
        int port = parsePort(portStr);
        boolean up = port > 0 && portChecker.isListening(port);
        r.put("status",  up ? "running" : "stopped");
        r.put("port",    port > 0 ? Integer.toString(port) : "-");
        r.put("version", versionReader.readVersion(homePath));
        r.put("home",    home);
        return r;
    }

    private Map<String, Object> pjsRow(String home) {
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("name", "PlatformJS");
        boolean exists = home != null && !home.trim().isEmpty() && Files.isDirectory(Paths.get(home));
        int port = PLATFORMJS_DEFAULT_PORT;
        boolean up = portChecker.isListening(port);
        r.put("status",  up ? "running" : (exists ? "stopped" : "stopped"));
        r.put("port",    Integer.toString(port));
        r.put("version", exists ? versionReader.readVersion(Paths.get(home)) : "-");
        r.put("home",    home == null ? "" : home);
        return r;
    }

    private Map<String, Object> clientRow(String pjsHome) {
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("name", "Client");
        r.put("status", "-");
        r.put("port",   "-");
        // Client 버전은 PlatformJS 의 client 하위 파일에서 읽힐 수 있음 — 단순화로 home/version 만
        String ver = "-";
        if (pjsHome != null && !pjsHome.trim().isEmpty()) {
            Path client = Paths.get(pjsHome).resolve("client");
            if (Files.isDirectory(client)) {
                ver = versionReader.readVersion(client);
            }
        }
        r.put("version", ver);
        r.put("home", "");
        return r;
    }

    private Map<String, Object> repoDbRow() {
        Map<String, Object> r = new LinkedHashMap<>();
        RepositoryConfig repo = serviceConfig.repository();
        String dbLabel = "Repository DB (" + repo.dbType() + ")";
        r.put("name", dbLabel);
        if (!repo.isConfigured()) {
            r.put("status",  "unconfigured");
            r.put("port",    "-");
            r.put("version", "-");
            r.put("home",    "");
            return r;
        }
        int port = repo.port();
        if (port <= 0) {
            // db_type 기본 포트
            port = DbType.fromConfigValue(repo.dbType()).defaultPort();
        }
        boolean up = portChecker.isListening(repo.ip(), port, 500);
        r.put("status",  up ? "running" : "stopped");
        r.put("port",    Integer.toString(port));
        r.put("version", "-");
        r.put("home",    "");
        return r;
    }

    private static int parsePort(String s) {
        if (s == null) return 0;
        try { return Integer.parseInt(s.trim()); } catch (NumberFormatException e) { return 0; }
    }
}
