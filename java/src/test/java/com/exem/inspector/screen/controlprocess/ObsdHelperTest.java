package com.exem.inspector.screen.controlprocess;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/**
 * ObsdHelper 단위 테스트 — 원본 _get_dg_obsd_pid / _stop_obsd / _start_dg_obsd 1:1 검증.
 *
 * <p>CommandRunner mock 으로 외부 ps/kill 호출 결과 주입.
 */
class ObsdHelperTest {

    private final ObsdHelper.CommandRunner runner = mock(ObsdHelper.CommandRunner.class);
    private final ObsdHelper helper = new ObsdHelper(runner);

    // ── PID 조회 ────────────────────────────────────────────────────────────
    @Test
    void getDgObsdPid_parsesFirstNumericLine() {
        given(runner.capture(any(String[].class))).willReturn("12345\n67890\n");
        assertThat(helper.getDgObsdPid("DGServer_M")).isEqualTo("12345");
    }

    @Test
    void getDgObsdPid_emptyOutput_returnsNull() {
        given(runner.capture(any(String[].class))).willReturn("");
        assertThat(helper.getDgObsdPid("DGServer_M")).isNull();
    }

    @Test
    void getDgObsdPid_nonNumeric_returnsNull() {
        given(runner.capture(any(String[].class))).willReturn("abc\n");
        assertThat(helper.getDgObsdPid("DGServer_M")).isNull();
    }

    @Test
    void getDgObsdPid_nullDgName_returnsNull() {
        assertThat(helper.getDgObsdPid(null)).isNull();
        assertThat(helper.getDgObsdPid("")).isNull();
    }

    @Test
    void getPjsObsdPid_emptyPort_returnsNull() {
        assertThat(helper.getPjsObsdPid(null)).isNull();
        assertThat(helper.getPjsObsdPid("")).isNull();
    }

    // ── 정지 ────────────────────────────────────────────────────────────────
    @Test
    void stopObsd_nullPid_returnsNotRunning() {
        ObsdHelper.Result r = helper.stopObsd(null);
        assertThat(r.ok).isTrue();
        assertThat(r.message).contains("not running");
    }

    @Test
    void stopObsd_killAndVerify_returnsStopped() {
        // After kill, ps -p <pid> returns empty → no SIGKILL needed
        given(runner.capture(any(String[].class))).willReturn("");
        ObsdHelper.Result r = helper.stopObsd("12345");
        assertThat(r.ok).isTrue();
        assertThat(r.message).contains("12345");
        verify(runner).run(anyString(), any(), any());  // kill 호출 검증
    }

    // ── DG 시작 ────────────────────────────────────────────────────────────
    @Test
    void startDgObsd_emptyDgName_fails() {
        Map<String, String> mxgrc = new HashMap<>();
        ObsdHelper.Result r = helper.startDgObsd(java.nio.file.Paths.get("/tmp"), mxgrc);
        assertThat(r.ok).isFalse();
        assertThat(r.message).contains("DG_NAME");
    }

    @Test
    void startDgObsd_existingPid_returnsAlreadyRunning() {
        Map<String, String> mxgrc = new HashMap<>();
        mxgrc.put("DG_NAME", "DGServer_M");
        given(runner.capture(any(String[].class))).willReturn("99999\n");

        ObsdHelper.Result r = helper.startDgObsd(java.nio.file.Paths.get("/tmp"), mxgrc);
        assertThat(r.ok).isFalse();
        assertThat(r.message).contains("already running");
        assertThat(r.message).contains("99999");
    }

    @Test
    void startDgObsd_missingBinary_fails(@TempDir Path home) {
        Map<String, String> mxgrc = new HashMap<>();
        mxgrc.put("DG_NAME", "DGServer_M");
        mxgrc.put("OS_TYPE", "linux64");
        // no PID, no binary file
        given(runner.capture(any(String[].class))).willReturn("");

        ObsdHelper.Result r = helper.startDgObsd(home, mxgrc);
        assertThat(r.ok).isFalse();
        assertThat(r.message).contains("mxg_obsd binary not found");
    }

    @Test
    void startDgObsd_missingConf_fails(@TempDir Path home) throws IOException {
        Map<String, String> mxgrc = new HashMap<>();
        mxgrc.put("DG_NAME", "DGServer_M");
        mxgrc.put("OS_TYPE", "linux64");

        Path obsdBin = home.resolve("bin").resolve("mxg_obsd").resolve("linux64").resolve("mxg_obsd");
        Files.createDirectories(obsdBin.getParent());
        Files.write(obsdBin, "dummy".getBytes(StandardCharsets.UTF_8));

        given(runner.capture(any(String[].class))).willReturn("");

        ObsdHelper.Result r = helper.startDgObsd(home, mxgrc);
        assertThat(r.ok).isFalse();
        assertThat(r.message).contains("Observer config not found");
    }

    // ── PJS 시작 ────────────────────────────────────────────────────────────
    @Test
    void startPjsObsd_emptyPort_fails() {
        ObsdHelper.Result r = helper.startPjsObsd(java.nio.file.Paths.get("/tmp"), null);
        assertThat(r.ok).isFalse();
        assertThat(r.message).contains("Service port unknown");
    }

    @Test
    void startPjsObsd_existingPid_returnsAlreadyRunning() {
        given(runner.capture(any(String[].class))).willReturn("77777\n");
        ObsdHelper.Result r = helper.startPjsObsd(java.nio.file.Paths.get("/tmp"), "8888");
        assertThat(r.ok).isFalse();
        assertThat(r.message).contains("already running");
    }
}
