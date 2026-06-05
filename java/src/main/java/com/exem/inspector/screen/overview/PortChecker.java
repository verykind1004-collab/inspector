package com.exem.inspector.screen.overview;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.List;

import org.springframework.stereotype.Component;

/**
 * TCP 포트 listen 여부 + PID 식별(원본 system_utils._port_is_listening / _get_pid_by_port 와 동등).
 *
 * <p>listen: localhost / 임의 host 대상 timeout connect. 권한 없이도 동작.
 * pidByPort: {@code ss -tlnp} 우선 → {@code netstat -tlnp} 폴백. 비-root 환경에선
 * PID 가 숨겨지면 null 반환(원본도 동일 한계).
 */
@Component
public class PortChecker {

    private static final int DEFAULT_TIMEOUT_MS = 300;
    private static final List<String> SS_PATHS = Arrays.asList("/usr/sbin/ss", "/sbin/ss", "/bin/ss", "ss");
    private static final List<String> NETSTAT_PATHS = Arrays.asList("/usr/bin/netstat", "/bin/netstat", "netstat");

    /** localhost:port. timeout 안에 connect 성공 시 true. */
    public boolean isListening(int port) {
        return isListening("127.0.0.1", port, DEFAULT_TIMEOUT_MS);
    }

    /** 주어진 host:port. */
    public boolean isListening(String host, int port, int timeoutMs) {
        if (port <= 0) return false;
        try (Socket s = new Socket()) {
            s.connect(new InetSocketAddress(host, port), timeoutMs);
            return true;
        } catch (IOException e) {
            return false;
        }
    }

    /**
     * 주어진 포트에서 listen 중인 프로세스의 PID. 식별 실패 시 null.
     * 원본 _get_pid_by_port 와 동일 (ss → netstat 순).
     */
    public String pidByPort(int port) {
        if (port <= 0) return null;
        String marker = ":" + port;
        // ss 우선
        for (String ss : SS_PATHS) {
            String pid = parsePidFrom(runQuiet(ss, "-tlnp"), marker);
            if (pid != null) return pid;
        }
        // netstat 폴백
        for (String ns : NETSTAT_PATHS) {
            String pid = parsePidFrom(runQuiet(ns, "-tlnp"), marker);
            if (pid != null) return pid;
        }
        return null;
    }

    /** ss/netstat 출력 한 줄씩 보고 ':PORT ' 매칭 라인에서 pid 추출. */
    static String parsePidFrom(String output, String portMarker) {
        if (output == null) return null;
        String[] lines = output.split("\\R");
        for (String line : lines) {
            if (!line.contains(portMarker)) continue;
            // ss: "users:((\"java\",pid=12345,fd=...))"
            int piEq = line.indexOf("pid=");
            if (piEq >= 0) {
                int from = piEq + 4;
                int to = from;
                while (to < line.length() && Character.isDigit(line.charAt(to))) to++;
                if (to > from) return line.substring(from, to);
            }
            // netstat: "12345/java"
            for (String tok : line.split("\\s+")) {
                int slash = tok.indexOf('/');
                if (slash > 0) {
                    String head = tok.substring(0, slash);
                    if (head.chars().allMatch(Character::isDigit)) return head;
                }
            }
        }
        return null;
    }

    private static String runQuiet(String... cmd) {
        try {
            ProcessBuilder pb = new ProcessBuilder(cmd).redirectErrorStream(true);
            Process p = pb.start();
            StringBuilder sb = new StringBuilder();
            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = br.readLine()) != null) sb.append(line).append('\n');
            }
            // 1초 안에 끝나야 함. 너무 길면 무시.
            if (!p.waitFor(1, java.util.concurrent.TimeUnit.SECONDS)) {
                p.destroyForcibly();
                return null;
            }
            return sb.toString();
        } catch (Exception e) {
            return null;
        }
    }
}
