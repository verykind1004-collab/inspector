package com.exem.inspector.screen.decrypt;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import com.exem.inspector.config.ServiceConfig;
import com.exem.inspector.config.ServicesBlock;

/**
 * DecryptService 단위 테스트 — 입력 검증 + jar 존재 + 결과 라인 파싱 + 에러 hint.
 */
class DecryptServiceTest {

    private final ServiceConfig serviceConfig = mock(ServiceConfig.class);
    private final DecryptService.JarRunner runner = mock(DecryptService.JarRunner.class);
    private final DecryptService service = new DecryptService(serviceConfig, runner);

    private Path makeDgmWithJar(Path tmp) throws IOException {
        Path bin = tmp.resolve("bin");
        Files.createDirectories(bin);
        Files.write(bin.resolve("DGServer.jar"), "dummy".getBytes(StandardCharsets.UTF_8));
        return tmp;
    }

    private void wireDgm(String home) {
        ServicesBlock sb = mock(ServicesBlock.class);
        given(sb.dgserverM()).willReturn(home == null ? "" : home);
        given(serviceConfig.services()).willReturn(sb);
    }

    // ── 입력 검증 ────────────────────────────────────────────────────
    @Test
    void emptyText_returnsError() {
        Map<String, Object> r = service.run("", "encrypt");
        assertThat(r.get("ok")).isEqualTo(false);
        assertThat(String.valueOf(r.get("error"))).contains("No text provided");
    }

    @Test
    void invalidAction_returnsError() {
        Map<String, Object> r = service.run("hello", "delete");
        assertThat(r.get("ok")).isEqualTo(false);
        assertThat(String.valueOf(r.get("error"))).contains("Invalid action");
    }

    @Test
    void nullAction_defaultsToDecrypt(@TempDir Path tmp) throws IOException {
        Path home = makeDgmWithJar(tmp);
        wireDgm(home.toString());
        given(runner.run(any(Path.class), anyString(), anyString()))
                .willReturn(new DecryptService.JarRunner.Result(0, "Decrypt: PWD123", ""));

        Map<String, Object> r = service.run("encoded", null);
        assertThat(r.get("ok")).isEqualTo(true);
        assertThat(r.get("action")).isEqualTo("decrypt");
        assertThat(r.get("result")).isEqualTo("PWD123");
    }

    // ── DGServer_M 미설정 ─────────────────────────────────────────────
    @Test
    void noDgmHome_returnsError() {
        wireDgm("");
        Map<String, Object> r = service.run("hi", "encrypt");
        assertThat(r.get("ok")).isEqualTo(false);
        assertThat(String.valueOf(r.get("error"))).contains("DGServer_M");
    }

    @Test
    void jarMissing_returnsError(@TempDir Path tmp) {
        wireDgm(tmp.toString());
        Map<String, Object> r = service.run("hi", "encrypt");
        assertThat(r.get("ok")).isEqualTo(false);
        assertThat(String.valueOf(r.get("error"))).contains("DGServer.jar");
    }

    // ── 결과 라인 파싱 ────────────────────────────────────────────────
    @Test
    void encryptSuccess_parsesResult(@TempDir Path tmp) throws IOException {
        Path home = makeDgmWithJar(tmp);
        wireDgm(home.toString());
        given(runner.run(any(Path.class), anyString(), anyString()))
                .willReturn(new DecryptService.JarRunner.Result(0, "Encrypt: AbC123==", ""));
        Map<String, Object> r = service.run("plain", "encrypt");
        assertThat(r.get("ok")).isEqualTo(true);
        assertThat(r.get("result")).isEqualTo("AbC123==");
        assertThat(r.get("action")).isEqualTo("encrypt");
    }

    @Test
    void caseInsensitive_matchesEncrypt(@TempDir Path tmp) throws IOException {
        Path home = makeDgmWithJar(tmp);
        wireDgm(home.toString());
        given(runner.run(any(Path.class), anyString(), anyString()))
                .willReturn(new DecryptService.JarRunner.Result(0, "encrypt:lowercase_ok", ""));
        Map<String, Object> r = service.run("plain", "encrypt");
        assertThat(r.get("ok")).isEqualTo(true);
        assertThat(r.get("result")).isEqualTo("lowercase_ok");
    }

    @Test
    void noResultLine_returnsErrorWithOutput(@TempDir Path tmp) throws IOException {
        Path home = makeDgmWithJar(tmp);
        wireDgm(home.toString());
        given(runner.run(any(Path.class), anyString(), anyString()))
                .willReturn(new DecryptService.JarRunner.Result(0, "Some other line", ""));
        Map<String, Object> r = service.run("plain", "decrypt");
        assertThat(r.get("ok")).isEqualTo(false);
        assertThat(String.valueOf(r.get("error"))).contains("No decrypt result");
        assertThat(String.valueOf(r.get("error"))).contains("Some other line");
    }

    @Test
    void javaNotFound_addsHint(@TempDir Path tmp) throws IOException {
        Path home = makeDgmWithJar(tmp);
        wireDgm(home.toString());
        given(runner.run(any(Path.class), anyString(), anyString()))
                .willReturn(new DecryptService.JarRunner.Result(127, "", "bash: java: command not found"));
        Map<String, Object> r = service.run("plain", "encrypt");
        assertThat(r.get("ok")).isEqualTo(false);
        assertThat(String.valueOf(r.get("error"))).contains("java 실행 불가");
    }
}
