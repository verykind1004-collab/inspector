package com.exem.inspector.screen.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import com.exem.inspector.config.ServiceConfig;

/**
 * ConfigService 단위 테스트 — service_config.json read/write + insp_config.json CRUD.
 */
class ConfigServiceTest {

    private final ServiceConfig serviceConfig = mock(ServiceConfig.class);

    private ConfigService build(Path svcConfigPath, Path inspConfigPath) {
        return new ConfigService(serviceConfig, svcConfigPath.toString(), inspConfigPath.toString());
    }

    // ── service_config.json read ─────────────────────────────────────────
    @Test
    void readMissingFile_returnsEmptyMaps(@TempDir Path tmp) {
        Path svc = tmp.resolve("service_config.json");
        Path insp = tmp.resolve("insp_config.json");
        ConfigService s = build(svc, insp);
        ConfigPagePayload p = s.read();
        assertThat(p.getRepository()).isEmpty();
        assertThat(p.getServices()).isEmpty();
        assertThat(p.getLogPaths()).isEmpty();
        assertThat(p.getConfigFilePath()).contains("service_config.json");
    }

    @Test
    void readExistingFile_parsesRepoServices(@TempDir Path tmp) throws IOException {
        Path svc = tmp.resolve("service_config.json");
        Files.write(svc, ("{\"repository\":{\"db_type\":\"Oracle\",\"ip\":\"10.0.0.1\"},"
                + "\"services\":{\"platformjs\":\"/pjs\"},"
                + "\"log_paths\":{\"platformjs\":\"/pjs/log\"}}").getBytes(StandardCharsets.UTF_8));
        Path insp = tmp.resolve("insp_config.json");

        ConfigPagePayload p = build(svc, insp).read();
        assertThat(p.getRepository()).containsEntry("db_type", "Oracle").containsEntry("ip", "10.0.0.1");
        assertThat(p.getServices()).containsEntry("platformjs", "/pjs");
        assertThat(p.getLogPaths()).containsEntry("platformjs", "/pjs/log");
    }

    // ── service_config.json write ─────────────────────────────────────────
    @Test
    void write_savesAndReloads(@TempDir Path tmp) throws IOException {
        Path svc = tmp.resolve("nested").resolve("service_config.json");
        Path insp = tmp.resolve("insp_config.json");
        ConfigService s = build(svc, insp);

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("repository", java.util.Collections.singletonMap("db_type", "PostgreSQL"));
        s.write(body);

        assertThat(Files.exists(svc)).isTrue();
        String content = new String(Files.readAllBytes(svc), StandardCharsets.UTF_8);
        assertThat(content).contains("PostgreSQL");
        // reload() 호출 검증
        org.mockito.Mockito.verify(serviceConfig).reload();
    }

    @Test
    void write_nullBody_throws(@TempDir Path tmp) {
        ConfigService s = build(tmp.resolve("a.json"), tmp.resolve("b.json"));
        org.assertj.core.api.Assertions.assertThatThrownBy(() -> s.write(null))
                .isInstanceOf(IllegalArgumentException.class);
    }

    // ── insp_config.json read ────────────────────────────────────────────
    @Test
    void readInsp_missingFile_returnsDefaults(@TempDir Path tmp) {
        Path insp = tmp.resolve("insp_config.json");
        InspHistoryConfig c = build(tmp.resolve("a.json"), insp).readInspHistory();
        // 원본 default — enabled=false / tables_initialized=false / retention=31 / log=10
        assertThat(c.isEnabled()).isFalse();
        assertThat(c.isTablesInitialized()).isFalse();
        assertThat(c.getRetentionDays()).isEqualTo(31);
        assertThat(c.getLogRetentionDays()).isEqualTo(10);
    }

    @Test
    void readInsp_existingFile_parsesKeys(@TempDir Path tmp) throws IOException {
        Path insp = tmp.resolve("insp_config.json");
        Files.write(insp, ("{\"enabled\":true,\"tables_initialized\":true,"
                + "\"retention_days\":60,\"log_retention_days\":7}")
                .getBytes(StandardCharsets.UTF_8));

        InspHistoryConfig c = build(tmp.resolve("svc.json"), insp).readInspHistory();
        assertThat(c.isEnabled()).isTrue();
        assertThat(c.isTablesInitialized()).isTrue();
        assertThat(c.getRetentionDays()).isEqualTo(60);
        assertThat(c.getLogRetentionDays()).isEqualTo(7);
    }

    @Test
    void readInsp_missingKeys_useDefaults(@TempDir Path tmp) throws IOException {
        Path insp = tmp.resolve("insp_config.json");
        Files.write(insp, "{\"enabled\":true}".getBytes(StandardCharsets.UTF_8));

        InspHistoryConfig c = build(tmp.resolve("svc.json"), insp).readInspHistory();
        assertThat(c.isEnabled()).isTrue();
        assertThat(c.isTablesInitialized()).isFalse();
        assertThat(c.getRetentionDays()).isEqualTo(31);
        assertThat(c.getLogRetentionDays()).isEqualTo(10);
    }

    @Test
    void readInsp_corruptJson_returnsDefaults(@TempDir Path tmp) throws IOException {
        Path insp = tmp.resolve("insp_config.json");
        Files.write(insp, "{not-json".getBytes(StandardCharsets.UTF_8));
        InspHistoryConfig c = build(tmp.resolve("svc.json"), insp).readInspHistory();
        assertThat(c.getRetentionDays()).isEqualTo(31);
    }

    // ── insp_config.json save ────────────────────────────────────────────
    @Test
    void saveInsp_writesJsonWithOrderedKeys(@TempDir Path tmp) throws IOException {
        Path insp = tmp.resolve("insp_config.json");
        InspHistoryConfig body = new InspHistoryConfig(true, false, 90, 14);
        InspHistoryConfig saved = build(tmp.resolve("svc.json"), insp).saveInspHistory(body);

        assertThat(saved.isEnabled()).isTrue();
        assertThat(Files.exists(insp)).isTrue();
        String content = new String(Files.readAllBytes(insp), StandardCharsets.UTF_8);
        // 원본 키 순서 보존 검증
        int e = content.indexOf("\"enabled\"");
        int ti = content.indexOf("\"tables_initialized\"");
        int rd = content.indexOf("\"retention_days\"");
        int lr = content.indexOf("\"log_retention_days\"");
        assertThat(e).isLessThan(ti);
        assertThat(ti).isLessThan(rd);
        assertThat(rd).isLessThan(lr);
        assertThat(content).contains("\"retention_days\" : 90");
    }

    @Test
    void saveInsp_nullBody_throws(@TempDir Path tmp) {
        ConfigService s = build(tmp.resolve("svc.json"), tmp.resolve("insp.json"));
        org.assertj.core.api.Assertions.assertThatThrownBy(() -> s.saveInspHistory(null))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
