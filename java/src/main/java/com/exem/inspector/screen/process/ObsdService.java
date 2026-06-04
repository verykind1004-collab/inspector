package com.exem.inspector.screen.process;

import java.io.IOException;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.regex.Pattern;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.exem.inspector.config.ServiceConfig;
import com.exem.inspector.config.ServicesBlock;

/**
 * OBSD 로그 파일 목록 서비스 — 원본 process.py::_gather_obsd_html 1:1.
 *
 * <p>각 DGServer 의 {@code log/maxgauge/} 디렉토리 하위에서 {@code obsd\d+\.log(\.zip)?}
 * 패턴 매칭 파일을 mtime DESC 로 정렬해 반환한다.
 */
@Service
public class ObsdService {

    private static final Logger log = LoggerFactory.getLogger(ObsdService.class);
    private static final Pattern OBSD_RE = Pattern.compile("^obsd\\d+\\.log(\\.zip)?$");

    private final ServiceConfig serviceConfig;

    public ObsdService(ServiceConfig serviceConfig) {
        this.serviceConfig = serviceConfig;
    }

    public ObsdPayload listProcs() {
        ServicesBlock svc;
        try {
            svc = serviceConfig.services();
        } catch (RuntimeException e) {
            return new ObsdPayload(Collections.<ObsdPayload.Proc>emptyList(),
                    "service_config 로드 실패: " + e.getMessage());
        }

        List<ObsdPayload.Proc> procs = new ArrayList<>();
        String dgm = nz(svc.dgserverM());
        if (!dgm.isEmpty()) {
            procs.add(buildProc("dgm", "DGServer_M", Paths.get(dgm, "log", "maxgauge")));
        }
        List<String> dgsList = svc.dgserverS();
        if (dgsList != null) {
            for (int i = 0; i < dgsList.size(); i++) {
                String dgs = nz(dgsList.get(i));
                if (dgs.isEmpty()) continue;
                procs.add(buildProc("dgs" + (i + 1), "DGServer_S" + (i + 1),
                        Paths.get(dgs, "log", "maxgauge")));
            }
        }

        String cfgError = procs.isEmpty() ? "DGServer paths 가 설정되지 않았습니다." : null;
        return new ObsdPayload(procs, cfgError);
    }

    private ObsdPayload.Proc buildProc(String id, String name, Path logDir) {
        String logDirStr = logDir.toString();
        if (!Files.isDirectory(logDir)) {
            // 디렉토리 미존재 — 빈 파일 리스트(에러 메시지 없음, UI 가 "OBSD 로그 파일이 없습니다." 표시)
            return new ObsdPayload.Proc(id, name, logDirStr, Collections.<ObsdPayload.File>emptyList(), null);
        }
        List<ObsdPayload.File> files = new ArrayList<>();
        try (DirectoryStream<Path> ds = Files.newDirectoryStream(logDir)) {
            for (Path p : ds) {
                String fname = p.getFileName().toString();
                if (!OBSD_RE.matcher(fname).matches()) continue;
                try {
                    long size = Files.size(p);
                    long mtime = Files.getLastModifiedTime(p).toMillis();
                    files.add(new ObsdPayload.File(fname, size, mtime, p.toString()));
                } catch (IOException ignored) { /* skip */ }
            }
        } catch (IOException e) {
            log.warn("OBSD 디렉토리 읽기 실패: {} ({})", logDir, e.getMessage());
            return new ObsdPayload.Proc(id, name, logDirStr, Collections.<ObsdPayload.File>emptyList(),
                    "디렉토리 읽기 실패: " + e.getMessage());
        }
        files.sort(new Comparator<ObsdPayload.File>() {
            @Override public int compare(ObsdPayload.File a, ObsdPayload.File b) {
                return Long.compare(b.getMtime(), a.getMtime()); // DESC
            }
        });
        return new ObsdPayload.Proc(id, name, logDirStr, files, null);
    }

    private static String nz(String s) { return s == null ? "" : s.trim(); }
}
