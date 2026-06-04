package com.exem.inspector.screen.decrypt;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.exem.inspector.config.ServiceConfig;

/**
 * DGServer.jar encrypt/decrypt 도구 (/decrypt) — 원본 pages/decrypt.py 의 api_decrypt 1:1.
 *
 * <p>DGServer_M home/bin/DGServer.jar 를 `java -jar DGServer.jar <action>` 으로 실행.
 * text 를 stdin 으로 전달 후 stdout 의 "Encrypt: ..." 또는 "Decrypt: ..." 결과 라인 파싱.
 */
@Service
public class DecryptService {

    private static final Logger log = LoggerFactory.getLogger(DecryptService.class);
    private static final Set<String> ALLOWED_ACTIONS = new HashSet<>(Arrays.asList("encrypt", "decrypt"));

    private final ServiceConfig serviceConfig;
    private final JarRunner runner;

    public DecryptService(ServiceConfig serviceConfig, JarRunner runner) {
        this.serviceConfig = serviceConfig;
        this.runner = runner;
    }

    public Map<String, Object> run(String text, String action) {
        Map<String, Object> resp = new LinkedHashMap<>();
        if (text == null || text.trim().isEmpty()) {
            resp.put("ok", false); resp.put("error", "No text provided");
            return resp;
        }
        String act = action == null ? "decrypt" : action.trim().toLowerCase();
        if (!ALLOWED_ACTIONS.contains(act)) {
            resp.put("ok", false); resp.put("error", "Invalid action: " + act);
            return resp;
        }

        String dgmHome = serviceConfig.services().dgserverM();
        if (dgmHome == null || dgmHome.isEmpty()) {
            resp.put("ok", false); resp.put("error", "DGServer_M 경로가 설정되지 않았습니다.");
            return resp;
        }
        Path jarPath = Paths.get(dgmHome, "bin", "DGServer.jar");
        if (!Files.exists(jarPath)) {
            resp.put("ok", false); resp.put("error", "DGServer.jar 파일을 찾을 수 없습니다.");
            return resp;
        }

        JarRunner.Result r = runner.run(jarPath, act, text);
        String output = r.stdout == null ? "" : r.stdout.trim();
        String label = "encrypt".equals(act) ? "Encrypt" : "Decrypt";
        Pattern p = Pattern.compile(label + "\\s*:\\s*(.+)", Pattern.CASE_INSENSITIVE);
        Matcher m = p.matcher(output);
        if (m.find()) {
            resp.put("ok", true);
            resp.put("result", m.group(1).trim());
            resp.put("action", act);
            return resp;
        }
        String err = r.stderr == null ? "" : r.stderr.trim();
        String hint = "";
        String low = err.toLowerCase();
        if (low.contains("command not found") || low.contains("java: not found")) {
            hint = " (java 실행 불가 — JAVA_HOME/PATH 또는 java.path 설정 확인)";
        }
        resp.put("ok", false);
        resp.put("error", "No " + act + " result." + hint + " Output: "
                + (output.length() > 200 ? output.substring(0, 200) : output));
        return resp;
    }

    // ── JarRunner 인터페이스 (단위 테스트 mock 가능) ───────────────────

    public interface JarRunner {
        Result run(Path jarPath, String action, String stdin);

        final class Result {
            public final int exitCode;
            public final String stdout;
            public final String stderr;
            public Result(int exitCode, String stdout, String stderr) {
                this.exitCode = exitCode; this.stdout = stdout; this.stderr = stderr;
            }
        }
    }

    /** 실 ProcessBuilder 구현 — bash -lc 로그인 셸 fallback (원본 _resolve_java_cmd 1:1). */
    @org.springframework.stereotype.Component
    public static class ProcessJarRunner implements JarRunner {
        @Override
        public Result run(Path jarPath, String action, String stdin) {
            try {
                String inner = "exec java -jar " + jarPath + " " + action;
                ProcessBuilder pb = new ProcessBuilder("bash", "-lc", inner);
                pb.directory(jarPath.getParent().toFile());
                pb.redirectErrorStream(false);
                Process p = pb.start();
                try (OutputStream os = p.getOutputStream()) {
                    os.write((stdin + "\n").getBytes(StandardCharsets.UTF_8));
                    os.flush();
                }
                byte[] outB = readAll(p.getInputStream());
                byte[] errB = readAll(p.getErrorStream());
                if (!p.waitFor(10, TimeUnit.SECONDS)) {
                    p.destroyForcibly();
                    return new Result(-1, new String(outB, StandardCharsets.UTF_8),
                            new String(errB, StandardCharsets.UTF_8) + "\n[timeout]");
                }
                return new Result(p.exitValue(),
                        new String(outB, StandardCharsets.UTF_8),
                        new String(errB, StandardCharsets.UTF_8));
            } catch (IOException | InterruptedException e) {
                if (e instanceof InterruptedException) Thread.currentThread().interrupt();
                return new Result(-1, "", e.getMessage());
            }
        }
        private static byte[] readAll(java.io.InputStream in) throws IOException {
            java.io.ByteArrayOutputStream baos = new java.io.ByteArrayOutputStream();
            byte[] buf = new byte[4096]; int n;
            while ((n = in.read(buf)) > 0) baos.write(buf, 0, n);
            return baos.toByteArray();
        }
    }
}
