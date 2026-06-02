package com.exem.inspector.screen.controlprocess;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.exem.inspector.config.ServiceConfig;
import com.exem.inspector.config.ServicesBlock;

/**
 * 프로세스 제어 — DGServer_M / DGServer_S* / PlatformJS start/stop/restart.
 *
 * <p>원본 pages/control_process.py 의 _start_dgserver / _stop_dgserver / _start_platformjs / _stop_platformjs
 * 와 동등. 본 단계는 핵심 액션만 구현하고 Observer(mxg_obsd) 시작/정지는 후속 보강(START_DG 시 observer 도
 * 같이 띄우는 원본 흐름은 보존하되, 실패해도 메인 액션은 성공 처리).
 */
@Service
public class ControlProcessService {

    private static final Logger log = LoggerFactory.getLogger(ControlProcessService.class);

    private final ServiceConfig serviceConfig;

    public ControlProcessService(ServiceConfig serviceConfig) {
        this.serviceConfig = serviceConfig;
    }

    public ControlProcessResult start(String name) {
        Target t = resolve(name);
        if (t == null) return new ControlProcessResult(false, "Unknown service: " + name);
        if (t.isDg()) return startDgserver(t.home);
        if (t.isPjs()) return startPlatformJs(t.home);
        return new ControlProcessResult(false, "Unsupported: " + name);
    }

    public ControlProcessResult stop(String name) {
        Target t = resolve(name);
        if (t == null) return new ControlProcessResult(false, "Unknown service: " + name);
        if (t.isDg()) return stopDgserver(t.home);
        if (t.isPjs()) return stopPlatformJs(t.home);
        return new ControlProcessResult(false, "Unsupported: " + name);
    }

    public ControlProcessResult restart(String name) {
        ControlProcessResult s1 = stop(name);
        sleep(2);
        ControlProcessResult s2 = start(name);
        return new ControlProcessResult(s2.isOk(),
                "Stop: " + s1.getMessage() + " / Start: " + s2.getMessage());
    }

    // ── DGServer ────────────────────────────────────────────────────────────

    private ControlProcessResult startDgserver(Path home) {
        Map<String, String> mxgrc = MxgrcParser.parse(home);
        String dgName = mxgrc.getOrDefault("DG_NAME", "");
        String xms = mxgrc.getOrDefault("DG_XMS", "1024");
        String xmx = mxgrc.getOrDefault("DG_XMX", "1024");
        if (dgName.isEmpty()) {
            return new ControlProcessResult(false, ".mxgrc에 DG_NAME이 설정되지 않았습니다.");
        }
        Path binDir = home.resolve("bin");
        if (!Files.exists(binDir.resolve("DGServer.jar"))) {
            return new ControlProcessResult(false, "DGServer.jar not found in " + binDir);
        }
        // 이미 가동 중이면 skip(원본은 _dg_info 로 ps 검사 — 우리는 PID 직접 검색).
        String existing = findDgPid(dgName);
        if (existing != null) {
            return new ControlProcessResult(false, dgName + " is already running. (PID: " + existing + ")");
        }

        String cmd = "nohup java -Xms" + xms + "m -Xmx" + xmx + "m -" + dgName
                + " -jar DGServer.jar 1>/dev/null 2>&1 &";
        runBg(cmd, binDir, buildEnv(mxgrc));

        String pid = null;
        for (int i = 0; i < 5; i++) {
            sleep(1);
            pid = findDgPid(dgName);
            if (pid != null) break;
        }
        if (pid == null) {
            return new ControlProcessResult(false, dgName + " start failed. Check logs.");
        }
        return new ControlProcessResult(true, dgName + " started. (PID: " + pid + ")");
    }

    private ControlProcessResult stopDgserver(Path home) {
        Map<String, String> mxgrc = MxgrcParser.parse(home);
        String dgName = mxgrc.getOrDefault("DG_NAME", "DGServer");
        String pid = findDgPid(dgName);
        if (pid == null) {
            return new ControlProcessResult(true, dgName + " is not running.");
        }
        runShell("kill " + pid, null, null);
        sleep(5);
        // 여전히 살아있으면 -9.
        String alive = findDgPid(dgName);
        if (alive != null) {
            runShell("kill -9 " + pid, null, null);
            sleep(2);
        }
        return new ControlProcessResult(true, dgName + " stopped. (PID: " + pid + ")");
    }

    private String findDgPid(String dgName) {
        if (dgName == null || dgName.isEmpty()) return null;
        String[] cmd = {"bash", "-c",
                "ps -ef | grep -w '" + dgName + "' | grep DGServer.jar | grep -v grep | awk '{print $2}'"};
        String out = runShellCapture(cmd);
        if (out == null) return null;
        String first = out.trim().split("\n")[0].trim();
        if (first.isEmpty() || !first.matches("\\d+")) return null;
        return first;
    }

    // ── PlatformJS ──────────────────────────────────────────────────────────

    private ControlProcessResult startPlatformJs(Path home) {
        Path startSh = home.resolve("platformjs.start.sh");
        if (!Files.exists(startSh)) {
            return new ControlProcessResult(false, "platformjs.start.sh not found in " + home);
        }
        Map<String, String> mxgrc = MxgrcParser.parse(home);
        runBg("bash platformjs.start.sh -r", home, buildEnv(mxgrc));
        String pid = null;
        for (int i = 0; i < 5; i++) {
            sleep(1);
            pid = findPjsPid();
            if (pid != null) break;
        }
        if (pid == null) {
            return new ControlProcessResult(false, "PlatformJS start failed. Check logs.");
        }
        return new ControlProcessResult(true, "PlatformJS started. (PID: " + pid + ")");
    }

    private ControlProcessResult stopPlatformJs(Path home) {
        Path stopSh = home.resolve("platformjs.stop.sh");
        if (Files.exists(stopSh)) {
            runShell("bash platformjs.stop.sh", home, buildEnv(MxgrcParser.parse(home)));
            sleep(3);
        }
        String pid = findPjsPid();
        if (pid != null) {
            runShell("kill " + pid, null, null);
            sleep(3);
            String alive = findPjsPid();
            if (alive != null) {
                runShell("kill -9 " + alive, null, null);
                sleep(1);
            }
        }
        return new ControlProcessResult(true, "PlatformJS stopped." + (pid != null ? " (PID: " + pid + ")" : ""));
    }

    private String findPjsPid() {
        String[] cmd = {"bash", "-c",
                "ps -ef | grep DPJS | grep -v mxg_obsd | grep -v grep | awk '{print $2}'"};
        String out = runShellCapture(cmd);
        if (out == null || out.trim().isEmpty()) return null;
        String first = out.trim().split("\n")[0].trim();
        return first.matches("\\d+") ? first : null;
    }

    // ── resolve(name) → home path + type ──────────────────────────────────

    private Target resolve(String name) {
        if (name == null) return null;
        ServicesBlock svc = serviceConfig.services();
        if ("DGServer_M".equals(name)) {
            return svc.dgserverM().isEmpty() ? null : new Target(Paths.get(svc.dgserverM()), Type.DG);
        }
        if (name.startsWith("DGServer_S")) {
            int idx;
            try { idx = Integer.parseInt(name.substring("DGServer_S".length())) - 1; }
            catch (NumberFormatException e) { return null; }
            List<String> list = svc.dgserverS();
            if (idx < 0 || idx >= list.size()) return null;
            String home = list.get(idx);
            if (home == null || home.isEmpty()) return null;
            return new Target(Paths.get(home), Type.DG);
        }
        if ("PlatformJS".equals(name)) {
            return svc.platformjs().isEmpty() ? null : new Target(Paths.get(svc.platformjs()), Type.PJS);
        }
        return null;
    }

    private enum Type { DG, PJS }

    private static final class Target {
        final Path home;
        final Type type;
        Target(Path home, Type type) { this.home = home; this.type = type; }
        boolean isDg() { return type == Type.DG; }
        boolean isPjs() { return type == Type.PJS; }
    }

    // ── 쉘/환경 헬퍼 ────────────────────────────────────────────────────────

    String[] buildEnv(Map<String, String> mxgrc) {
        Map<String, String> env = new java.util.HashMap<>(System.getenv());
        for (String k : new String[]{"DG_NAME", "DG_XMS", "DG_XMX", "MXG_HOME", "OS_TYPE"}) {
            if (mxgrc.containsKey(k)) env.put(k, mxgrc.get(k));
        }
        String javaHome = mxgrc.get("JAVA_HOME");
        if (javaHome != null && !javaHome.isEmpty()) {
            env.put("JAVA_HOME", javaHome);
            env.put("PATH", javaHome + "/bin:" + env.getOrDefault("PATH", ""));
        }
        String mxgHome = mxgrc.get("MXG_HOME");
        if (mxgHome != null && !mxgHome.isEmpty()) {
            env.put("PATH", mxgHome + "/bin:" + env.getOrDefault("PATH", ""));
        }
        List<String> arr = new ArrayList<>(env.size());
        for (Map.Entry<String, String> e : env.entrySet()) arr.add(e.getKey() + "=" + e.getValue());
        return arr.toArray(new String[0]);
    }

    private void runBg(String cmd, Path cwd, String[] env) {
        try {
            ProcessBuilder pb = new ProcessBuilder("bash", "-c", cmd);
            if (cwd != null) pb.directory(cwd.toFile());
            // env: env array → ProcessBuilder.environment() (clear+populate)
            if (env != null) {
                pb.environment().clear();
                for (String kv : env) {
                    int eq = kv.indexOf('=');
                    if (eq > 0) pb.environment().put(kv.substring(0, eq), kv.substring(eq + 1));
                }
            }
            java.io.File devNull = new java.io.File("/dev/null");
            pb.redirectOutput(ProcessBuilder.Redirect.to(devNull));
            pb.redirectError(ProcessBuilder.Redirect.to(devNull));
            pb.start();
        } catch (IOException e) {
            log.debug("runBg 실패: {}", e.getMessage());
        }
    }

    private int runShell(String cmd, Path cwd, String[] env) {
        try {
            ProcessBuilder pb = new ProcessBuilder("bash", "-c", cmd);
            if (cwd != null) pb.directory(cwd.toFile());
            if (env != null) {
                pb.environment().clear();
                for (String kv : env) {
                    int eq = kv.indexOf('=');
                    if (eq > 0) pb.environment().put(kv.substring(0, eq), kv.substring(eq + 1));
                }
            }
            Process p = pb.start();
            if (!p.waitFor(30, TimeUnit.SECONDS)) {
                p.destroyForcibly();
                return -1;
            }
            return p.exitValue();
        } catch (IOException | InterruptedException e) {
            if (e instanceof InterruptedException) Thread.currentThread().interrupt();
            return -1;
        }
    }

    private String runShellCapture(String[] argv) {
        try {
            ProcessBuilder pb = new ProcessBuilder(argv);
            pb.redirectErrorStream(true);
            Process p = pb.start();
            byte[] out = readAll(p.getInputStream());
            if (!p.waitFor(10, TimeUnit.SECONDS)) {
                p.destroyForcibly();
                return null;
            }
            return new String(out, java.nio.charset.StandardCharsets.UTF_8);
        } catch (IOException | InterruptedException e) {
            if (e instanceof InterruptedException) Thread.currentThread().interrupt();
            return null;
        }
    }

    private static byte[] readAll(java.io.InputStream in) throws IOException {
        java.io.ByteArrayOutputStream baos = new java.io.ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int n;
        while ((n = in.read(buf)) > 0) baos.write(buf, 0, n);
        return baos.toByteArray();
    }

    private void sleep(long secs) {
        try { Thread.sleep(secs * 1000); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }

    /** 지원 서비스 목록(라우팅 화이트리스트). */
    public static List<String> supportedNames() {
        return Arrays.asList("DGServer_M", "DGServer_S1", "DGServer_S2", "PlatformJS");
    }
}
