package com.exem.inspector.screen.controlprocess;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Observer(mxg_obsd) helpers — 원본 control_process.py 의 _get_dg_obsd_pid /
 * _get_pjs_obsd_pid / _stop_obsd / _start_dg_obsd / _start_pjs_obsd 1:1 동등.
 *
 * <p>Observer 는 DGServer / PlatformJS 와 동반 가동되는 외부 모니터링 데몬.
 * 본 클래스는 PID 조회 / 정지 / 시작 의 외부 명령 호출을 담당하며 ControlProcessService 에서
 * start/stop 흐름에 동반 호출된다.
 */
@Component
public class ObsdHelper {

    private static final Logger log = LoggerFactory.getLogger(ObsdHelper.class);

    /** Observer 동작 결과 — (ok, message). */
    public static final class Result {
        public final boolean ok;
        public final String message;
        public Result(boolean ok, String message) { this.ok = ok; this.message = message; }
    }

    private final CommandRunner runner;

    public ObsdHelper(CommandRunner runner) {
        this.runner = runner;
    }

    // ── PID 조회 ────────────────────────────────────────────────────────────

    /** DG observer PID — `ps -ef | grep mxg_obsd | grep -w <DG_NAME> | grep -v grep | awk '{print $2}'`. */
    public String getDgObsdPid(String dgName) {
        if (dgName == null || dgName.isEmpty()) return null;
        String cmd = "ps -ef | grep mxg_obsd | grep -w '" + dgName + "' | grep -v grep | awk '{print $2}'";
        return parseFirstPid(runner.capture(new String[] { "bash", "-c", cmd }));
    }

    /** PJS observer PID — `ps -ef | grep mxg_obsd | grep 'DPJS<port>' | grep common.console.conf | grep -v grep`. */
    public String getPjsObsdPid(String servicePort) {
        if (servicePort == null || servicePort.isEmpty()) return null;
        String cmd = "ps -ef | grep mxg_obsd | grep 'DPJS" + servicePort
                + "' | grep common.console.conf | grep -v grep | awk '{print $2}'";
        return parseFirstPid(runner.capture(new String[] { "bash", "-c", cmd }));
    }

    private static String parseFirstPid(String out) {
        if (out == null || out.trim().isEmpty()) return null;
        String first = out.trim().split("\n")[0].trim();
        return first.matches("\\d+") ? first : null;
    }

    // ── 정지 ────────────────────────────────────────────────────────────────

    /** Observer 정지 — kill → 1초 후 살아있으면 kill -9. 원본 _stop_obsd 1:1. */
    public Result stopObsd(String pid) {
        if (pid == null || pid.isEmpty()) return new Result(true, "Observer not running.");
        runner.run("kill " + pid, null, null);
        sleepMs(1000);
        String alive = runner.capture(new String[] { "bash", "-c", "ps -p " + pid + " -o pid= 2>/dev/null" });
        if (alive != null && !alive.trim().isEmpty()) {
            runner.run("kill -9 " + pid, null, null);
            sleepMs(500);
        }
        return new Result(true, "Observer stopped. (PID: " + pid + ")");
    }

    // ── 시작 ────────────────────────────────────────────────────────────────

    /** DG Observer 시작 — 원본 _start_dg_obsd 1:1. */
    public Result startDgObsd(Path home, Map<String, String> mxgrc) {
        String dgName = mxgrc.getOrDefault("DG_NAME", "");
        String osType = mxgrc.getOrDefault("OS_TYPE", "linux64");
        if (dgName.isEmpty()) return new Result(false, "DG_NAME not set in .mxgrc");

        String existing = getDgObsdPid(dgName);
        if (existing != null) return new Result(false, "Observer already running. (PID: " + existing + ")");

        Path obsdBin = home.resolve("bin").resolve("mxg_obsd").resolve(osType).resolve("mxg_obsd");
        Path confFile = home.resolve("conf").resolve("DG").resolve("common_linux.conf");
        if (!Files.exists(obsdBin)) return new Result(false, "mxg_obsd binary not found: " + obsdBin);
        if (!Files.exists(confFile)) return new Result(false, "Observer config not found: " + confFile);

        Map<String, String> env = buildEnv(mxgrc);
        Path binDir = home.resolve("bin");
        String cmd = obsdBin + " -c " + dgName + " -f " + confFile + " -OTHERD -i 10 -D";
        runner.runBg(cmd, binDir, env);
        sleepMs(1000);

        String pid = getDgObsdPid(dgName);
        if (pid != null) return new Result(true, "Observer started. (PID: " + pid + ")");
        return new Result(false, "Observer start failed.");
    }

    /** PJS Observer 시작 — 원본 _start_pjs_obsd 1:1. */
    public Result startPjsObsd(Path pjsHome, String servicePort) {
        if (servicePort == null || servicePort.isEmpty()) return new Result(false, "Service port unknown.");

        String existing = getPjsObsdPid(servicePort);
        if (existing != null) return new Result(false, "Observer already running. (PID: " + existing + ")");

        Path obsdBin = pjsHome.resolve("mxg_obsd").resolve("linux64").resolve("mxg_obsd");
        Path confFile = pjsHome.resolve("config").resolve("common.console.conf");
        if (!Files.exists(obsdBin)) return new Result(false, "mxg_obsd binary not found: " + obsdBin);
        if (!Files.exists(confFile)) return new Result(false, "Observer config not found: " + confFile);

        Map<String, String> mxgrc = MxgrcParser.parse(pjsHome);
        Map<String, String> env = buildEnv(mxgrc);
        env.put("MXG_HOME", pjsHome.toString());

        String cmd = obsdBin + " --DPJS" + servicePort + " -f " + confFile + " -OTHERD -i 30 -D";
        runner.runBg(cmd, pjsHome, env);
        sleepMs(1000);

        String pid = getPjsObsdPid(servicePort);
        if (pid != null) return new Result(true, "Observer started. (PID: " + pid + ")");
        return new Result(false, "Observer start failed.");
    }

    // ── helpers ────────────────────────────────────────────────────────────

    private static Map<String, String> buildEnv(Map<String, String> mxgrc) {
        Map<String, String> env = new HashMap<>(System.getenv());
        for (String k : new String[] { "DG_NAME", "MXG_HOME", "OS_TYPE" }) {
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
        return env;
    }

    private static void sleepMs(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }

    // ── ProcessBuilder wrapper (테스트 시 mock 가능) ───────────────────────

    /** 외부 명령 실행 추상 — 테스트에서 mock. 기본 구현 SystemCommandRunner. */
    public interface CommandRunner {
        /** stdout 캡처. 실패 시 null. */
        String capture(String[] argv);
        /** foreground 실행, exit code 반환. -1 = 실패. */
        int run(String cmd, Path cwd, Map<String, String> env);
        /** background 실행, 호출 즉시 반환. */
        void runBg(String cmd, Path cwd, Map<String, String> env);
    }

    /** SystemCommandRunner — 실제 OS 명령 실행 (Spring DI 시 자동 주입). */
    @Component
    public static class SystemCommandRunner implements CommandRunner {

        @Override
        public String capture(String[] argv) {
            try {
                ProcessBuilder pb = new ProcessBuilder(argv);
                pb.redirectErrorStream(true);
                Process p = pb.start();
                byte[] out = readAll(p.getInputStream());
                if (!p.waitFor(10, TimeUnit.SECONDS)) {
                    p.destroyForcibly();
                    return null;
                }
                return new String(out, StandardCharsets.UTF_8);
            } catch (IOException | InterruptedException e) {
                if (e instanceof InterruptedException) Thread.currentThread().interrupt();
                return null;
            }
        }

        @Override
        public int run(String cmd, Path cwd, Map<String, String> env) {
            try {
                ProcessBuilder pb = new ProcessBuilder("bash", "-c", cmd);
                if (cwd != null) pb.directory(cwd.toFile());
                applyEnv(pb, env);
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

        @Override
        public void runBg(String cmd, Path cwd, Map<String, String> env) {
            try {
                ProcessBuilder pb = new ProcessBuilder("bash", "-c", cmd);
                if (cwd != null) pb.directory(cwd.toFile());
                applyEnv(pb, env);
                java.io.File devNull = new java.io.File("/dev/null");
                pb.redirectOutput(ProcessBuilder.Redirect.to(devNull));
                pb.redirectError(ProcessBuilder.Redirect.to(devNull));
                pb.start();
            } catch (IOException e) {
                log.debug("runBg 실패: {}", e.getMessage());
            }
        }

        private static void applyEnv(ProcessBuilder pb, Map<String, String> env) {
            if (env == null) return;
            pb.environment().clear();
            pb.environment().putAll(env);
        }

        private static byte[] readAll(InputStream in) throws IOException {
            java.io.ByteArrayOutputStream baos = new java.io.ByteArrayOutputStream();
            byte[] buf = new byte[4096];
            int n;
            while ((n = in.read(buf)) > 0) baos.write(buf, 0, n);
            return baos.toByteArray();
        }

        // suppress unused warning
        @SuppressWarnings("unused")
        private void _suppress(List<?> l) { /* unused */ }
        @SuppressWarnings("unused")
        private void _suppress2(ArrayList<?> l) { /* unused */ }
    }
}
