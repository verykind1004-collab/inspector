package com.exem.inspector.security;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.exem.inspector.config.ServiceConfig;

/**
 * DGServer.jar decrypt 외부 호출 — auth.py _dgs_decrypt 1:1.
 *
 * <p>java -jar {dgserver_m}/bin/DGServer.jar decrypt 를 stdin 으로 암호문 + 개행 전달,
 * stdout 에서 "Decrypt:" 라인 찾아 평문 추출 (auth.py 의 정규식 Decrypt\s*:\s*(.*) 와 동등).
 * timeout 10초. 실패 시 null + 사유 로그.
 */
@Service
public class DgsDecryptService {

    private static final Logger log = LoggerFactory.getLogger(DgsDecryptService.class);
    private static final long TIMEOUT_SECONDS = 10L;
    private static final char NEWLINE = (char) 10;
    private static final String MARKER = "decrypt";

    private final ServiceConfig serviceConfig;

    public DgsDecryptService(ServiceConfig serviceConfig) {
        this.serviceConfig = serviceConfig;
    }

    public String decrypt(String encryptedText) {
        if (encryptedText == null || encryptedText.isEmpty()) {
            return null;
        }
        String dgmHome = serviceConfig.services().dgserverM();
        if (dgmHome == null || dgmHome.isEmpty()) {
            log.warn("DGServer_M not configured (service_config.json services.dgserver_m)");
            return null;
        }
        File jarPath = new File(dgmHome, "bin/DGServer.jar");
        if (!jarPath.isFile()) {
            log.warn("DGServer.jar not found: {}", jarPath);
            return null;
        }

        String javaHome = System.getenv("JAVA_HOME");
        String javaCmd = (javaHome != null && !javaHome.isEmpty())
                ? javaHome + "/bin/java"
                : "java";

        ProcessBuilder pb = new ProcessBuilder(javaCmd, "-jar", jarPath.getAbsolutePath(), "decrypt");
        pb.directory(new File(dgmHome, "bin"));
        pb.redirectErrorStream(false);

        Process proc = null;
        try {
            proc = pb.start();
            try (OutputStream stdin = proc.getOutputStream()) {
                stdin.write(encryptedText.getBytes(StandardCharsets.UTF_8));
                stdin.write(NEWLINE);
                stdin.flush();
            }

            boolean finished = proc.waitFor(TIMEOUT_SECONDS, TimeUnit.SECONDS);
            if (!finished) {
                proc.destroyForcibly();
                log.warn("DGServer.jar decrypt timeout ({}s)", TIMEOUT_SECONDS);
                return null;
            }

            StringBuilder output = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(proc.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    output.append(line);
                    output.append(NEWLINE);
                }
            }
            String extracted = extractDecryptResult(output.toString());
            if (extracted != null) {
                return extracted;
            }
            String preview = output.length() > 200 ? output.substring(0, 200) : output.toString();
            log.warn("DGServer.jar unexpected output: {}", preview);
            return null;
        } catch (IOException e) {
            log.warn("DGServer.jar invocation failed", e);
            return null;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            if (proc != null) {
                proc.destroyForcibly();
            }
            return null;
        }
    }

    /**
     * 출력 텍스트에서 "Decrypt:" 패턴 찾아 콜론 이후 라인 끝까지 trim 결과 반환.
     * auth.py 의 정규식 Decrypt\s*:\s*(.*) (CASE_INSENSITIVE) 와 의미상 동등.
     * 매칭 없으면 null.
     */
    static String extractDecryptResult(String text) {
        if (text == null || text.isEmpty()) {
            return null;
        }
        String lower = text.toLowerCase();
        int from = 0;
        while (from < lower.length()) {
            int idx = lower.indexOf(MARKER, from);
            if (idx < 0) {
                return null;
            }
            int p = idx + MARKER.length();
            // \s*  — 공백 스킵
            while (p < text.length() && Character.isWhitespace(text.charAt(p))) {
                p++;
            }
            if (p < text.length() && text.charAt(p) == ':') {
                p++;
                // 콜론 이후 공백 스킵
                while (p < text.length() && Character.isWhitespace(text.charAt(p))) {
                    p++;
                }
                // 라인 끝(=개행 or EOF) 까지
                int end = p;
                while (end < text.length() && text.charAt(end) != NEWLINE) {
                    end++;
                }
                return text.substring(p, end).trim();
            }
            from = idx + 1;
        }
        return null;
    }
}
