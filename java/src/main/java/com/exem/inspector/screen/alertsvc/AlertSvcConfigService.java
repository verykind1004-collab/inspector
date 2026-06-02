package com.exem.inspector.screen.alertsvc;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

import org.springframework.stereotype.Service;

import com.exem.inspector.config.ServiceConfig;

/**
 * Alert Service Config (SMS/API/Mail) 의 read/save/copy 서비스.
 *
 * <p>원본 {@code pages/alert_svc_config.py} 의 {@code api_alert_svc_read/save/copy} 와 1:1 동등.
 * service_config.json 의 {@code services.dgserver_s} 배열을 순회해 {@code <dgserver>/svc/{kind}.xml}
 * (활성) 또는 {@code sample_{kind}.xml}(비활성) 을 다룬다.
 *
 * <p>I절 규약: 화면이 파일 시스템에 직접 접근하지 않음 — 본 서비스가 격리.
 */
@Service
public class AlertSvcConfigService {

    private static final DateTimeFormatter BAK_DATE = DateTimeFormatter.ofPattern("yyMMdd");
    private static final String[] EXTS_ACTIVATE = { ".jar", ".unit" };
    private static final String[] EXTS_DEACTIVATE = { ".xml", ".jar", ".unit" };

    private final ServiceConfig serviceConfig;

    public AlertSvcConfigService(ServiceConfig serviceConfig) {
        this.serviceConfig = serviceConfig;
    }

    // ── READ ────────────────────────────────────────────────────────────────

    /**
     * 모든 DGServer_S 의 해당 kind XML 을 읽어 entry 리스트로 반환한다.
     *
     * @throws IllegalArgumentException kind 미지원
     * @throws IllegalStateException    DGServer_S 미설정
     */
    public AlertSvcReadResult read(AlertSvcKind kind) {
        if (kind == null) {
            throw new IllegalArgumentException("Invalid kind");
        }
        List<DgServer> servers = listDgServers();
        if (servers.isEmpty()) {
            throw new IllegalStateException("No DGServer_S configured");
        }
        List<AlertSvcEntry> entries = new ArrayList<>();
        for (DgServer s : servers) {
            entries.add(readOne(s, kind));
        }
        return new AlertSvcReadResult(kind.lower(), entries);
    }

    private AlertSvcEntry readOne(DgServer s, AlertSvcKind kind) {
        XmlTarget t = resolveXmlTarget(s.svcDir, kind);
        AlertSvcXmlParser.Parsed p = AlertSvcXmlParser.parse(t.read);
        return new AlertSvcEntry(
                s.name, s.svcDir.toString(), t.active, t.read.toString(),
                p.config, p.binds, p.headers, p.raw);
    }

    // ── SAVE ────────────────────────────────────────────────────────────────

    /**
     * 단일 DGServer_S 에 XML 저장 + activate/deactivate 처리.
     *
     * @throws IllegalArgumentException kind 미지원 / 디렉토리 없음
     */
    public AlertSvcSaveResult save(AlertSvcSaveRequest req) {
        AlertSvcKind kind = AlertSvcKind.fromString(req == null ? null : req.getKind());
        if (kind == null) {
            throw new IllegalArgumentException("Invalid kind");
        }
        String svcDirRaw = req.getSvcDir();
        if (svcDirRaw == null || svcDirRaw.isEmpty()) {
            throw new IllegalArgumentException("svc dir not found");
        }
        Path svcDir = Paths.get(svcDirRaw);
        if (!Files.isDirectory(svcDir)) {
            throw new IllegalArgumentException("svc dir not found");
        }

        Path activePath = svcDir.resolve(kind.lower() + ".xml");
        Path samplePath = svcDir.resolve("sample_" + kind.lower() + ".xml");
        boolean isActive = Files.exists(activePath);
        String rawXml = req.getRawXml();
        Boolean activate = req.getActivate();

        List<String> results = new ArrayList<>();
        try {
            // 1) XML 본문 저장(존재 파일 백업 후).
            if (rawXml != null && !rawXml.isEmpty()) {
                Path target = isActive ? activePath : samplePath;
                Path bak = backupIfExists(target);
                if (bak != null) {
                    results.add("Backup: " + bak.getFileName().toString());
                }
                Files.write(target, rawXml.getBytes(StandardCharsets.UTF_8));
                results.add("XML saved: " + target.getFileName().toString());
            }

            // 2) Activate (현재 inactive → active 로 전환).
            if (Boolean.TRUE.equals(activate) && !isActive) {
                if (Files.exists(samplePath)) {
                    Files.copy(samplePath, activePath, StandardCopyOption.REPLACE_EXISTING);
                }
                for (String ext : EXTS_ACTIVATE) {
                    Path s = svcDir.resolve("sample_" + kind.lower() + ext);
                    Path a = svcDir.resolve(kind.lower() + ext);
                    if (Files.exists(s) && !Files.exists(a)) {
                        Files.copy(s, a);
                        results.add("Activated: " + a.getFileName().toString());
                    }
                }
                results.add("Service activated. Restart DGServer_S to apply.");
            } else if (Boolean.FALSE.equals(activate) && isActive) {
                // 3) Deactivate (active 파일들 삭제, sample 은 유지).
                for (String ext : EXTS_DEACTIVATE) {
                    Path a = svcDir.resolve(kind.lower() + ext);
                    if (Files.deleteIfExists(a)) {
                        results.add("Removed: " + a.getFileName().toString());
                    }
                }
                results.add("Service deactivated. Restart DGServer_S to apply.");
            }
        } catch (IOException e) {
            // 원본은 메시지를 그대로 300자 컷. 우리도 동일.
            String msg = e.getMessage() == null ? e.toString() : e.getMessage();
            throw new RuntimeException(msg.length() > 300 ? msg.substring(0, 300) : msg);
        }
        return new AlertSvcSaveResult(results);
    }

    // ── COPY ────────────────────────────────────────────────────────────────

    /** 여러 target DGServer 에 동일 XML 일괄 복사(원본 PG api_alert_svc_copy 와 1:1 동등). */
    public AlertSvcCopyResult copy(AlertSvcCopyRequest req) {
        AlertSvcKind kind = AlertSvcKind.fromString(req == null ? null : req.getKind());
        if (kind == null) {
            throw new IllegalArgumentException("Invalid kind");
        }
        String rawXml = req == null ? null : req.getRawXml();
        if (rawXml == null || rawXml.isEmpty()) {
            throw new IllegalArgumentException("No XML content");
        }
        List<String> targets = req.getTargetSvcDirs();
        if (targets == null || targets.isEmpty()) {
            throw new IllegalArgumentException("No targets selected");
        }
        Boolean activate = req.getActivate();
        byte[] xmlBytes = rawXml.getBytes(StandardCharsets.UTF_8);

        List<AlertSvcCopyResult.Item> items = new ArrayList<>();
        for (String dir : targets) {
            items.add(copyOne(dir, kind, xmlBytes, activate));
        }
        boolean allOk = items.stream().allMatch(i -> "ok".equals(i.getStatus()));
        return new AlertSvcCopyResult(allOk, items);
    }

    private AlertSvcCopyResult.Item copyOne(String dirRaw, AlertSvcKind kind,
                                            byte[] xmlBytes, Boolean activate) {
        Path svcDir = Paths.get(dirRaw);
        if (!Files.isDirectory(svcDir)) {
            return new AlertSvcCopyResult.Item(dirRaw, "error", null, null, "Directory not found");
        }
        try {
            Path activePath = svcDir.resolve(kind.lower() + ".xml");
            Path samplePath = svcDir.resolve("sample_" + kind.lower() + ".xml");
            Path bak;
            Path written;

            if (Boolean.TRUE.equals(activate)) {
                // 원본: backup(active) or backup(sample) — 둘 중 존재하는 첫 항목.
                bak = backupIfExists(activePath);
                if (bak == null) bak = backupIfExists(samplePath);
                Files.write(samplePath, xmlBytes);
                Files.write(activePath, xmlBytes);
                for (String ext : EXTS_ACTIVATE) {
                    Path s = svcDir.resolve("sample_" + kind.lower() + ext);
                    Path a = svcDir.resolve(kind.lower() + ext);
                    if (Files.exists(s) && !Files.exists(a)) {
                        Files.copy(s, a);
                    }
                }
                written = activePath;
            } else if (Boolean.FALSE.equals(activate)) {
                bak = backupIfExists(samplePath);
                Files.write(samplePath, xmlBytes);
                for (String ext : EXTS_DEACTIVATE) {
                    Files.deleteIfExists(svcDir.resolve(kind.lower() + ext));
                }
                written = samplePath;
            } else {
                Path target = Files.exists(activePath) ? activePath : samplePath;
                bak = backupIfExists(target);
                Files.write(target, xmlBytes);
                written = target;
            }
            return new AlertSvcCopyResult.Item(
                    dirRaw, "ok",
                    written.getFileName().toString(),
                    bak == null ? null : bak.getFileName().toString(),
                    null);
        } catch (IOException e) {
            String msg = e.getMessage() == null ? e.toString() : e.getMessage();
            return new AlertSvcCopyResult.Item(
                    dirRaw, "error", null, null,
                    msg.length() > 200 ? msg.substring(0, 200) : msg);
        }
    }

    // ── helpers ─────────────────────────────────────────────────────────────

    private List<DgServer> listDgServers() {
        List<DgServer> out = new ArrayList<>();
        List<String> raw = serviceConfig.services().dgserverS();
        for (int i = 0; i < raw.size(); i++) {
            String dgs = raw.get(i);
            if (dgs == null || dgs.isEmpty()) continue;
            Path svcDir = Paths.get(dgs, "svc");
            if (Files.isDirectory(svcDir)) {
                out.add(new DgServer("DGServer_S" + (i + 1), svcDir));
            }
        }
        return out;
    }

    /** {@code (read, write, active)} — active 면 active 파일, 아니면 sample 파일. */
    private XmlTarget resolveXmlTarget(Path svcDir, AlertSvcKind kind) {
        Path active = svcDir.resolve(kind.lower() + ".xml");
        Path sample = svcDir.resolve("sample_" + kind.lower() + ".xml");
        if (Files.exists(active)) {
            return new XmlTarget(active, sample, true);
        }
        return new XmlTarget(sample, sample, false);
    }

    /**
     * 백업 파일명 = {@code {path}.bak_{yyMMdd}_{seq}}, seq 는 0..N. 원본 알고리즘 동일.
     * 대상 파일이 없으면 null.
     */
    Path backupIfExists(Path target) throws IOException {
        if (!Files.exists(target)) return null;
        String today = LocalDate.now().format(BAK_DATE);
        int seq = 0;
        Path bak;
        while (true) {
            bak = target.resolveSibling(target.getFileName() + ".bak_" + today + "_" + seq);
            if (!Files.exists(bak)) break;
            seq++;
        }
        Files.copy(target, bak, StandardCopyOption.COPY_ATTRIBUTES);
        return bak;
    }

    /** DGServer 한 인스턴스 — display name + svc dir. */
    private static final class DgServer {
        final String name;
        final Path svcDir;
        DgServer(String name, Path svcDir) { this.name = name; this.svcDir = svcDir; }
    }

    /** XML 경로 컨테이너 — read 대상 + 활성 여부. */
    private static final class XmlTarget {
        final Path read;
        @SuppressWarnings("unused") final Path samplePath;
        final boolean active;
        XmlTarget(Path read, Path samplePath, boolean active) {
            this.read = read; this.samplePath = samplePath; this.active = active;
        }
    }
}
