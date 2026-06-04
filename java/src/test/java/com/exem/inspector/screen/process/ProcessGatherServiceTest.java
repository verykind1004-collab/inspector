package com.exem.inspector.screen.process;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/**
 * ProcessGatherService 단위 테스트 — 정적 헬퍼(matchesErrOrWarn / parseGatherPort /
 * pickLatestLog / scanErrors) 검증. overview() 통합은 별도 mock 으로 가능하나
 * 우선 로직 단위에 집중(원본 1:1 동등성).
 */
class ProcessGatherServiceTest {

    private Path tmp;

    @BeforeEach
    void setUp() throws IOException {
        tmp = Files.createTempDirectory("proc-gather-");
    }

    @AfterEach
    void tearDown() throws IOException {
        if (Files.exists(tmp)) {
            Files.walk(tmp).sorted(java.util.Comparator.reverseOrder())
                .forEach(p -> { try { Files.delete(p); } catch (IOException ignored) {} });
        }
    }

    // ── matchesErrOrWarn ─────────────────────────────────────────────

    @Test
    void matchesErrorBracket() {
        assertThat(ProcessGatherService.matchesErrOrWarn("2026-06-04 [ERROR] something")).isTrue();
        assertThat(ProcessGatherService.matchesErrOrWarn("[ERROR")).isTrue();
    }

    @Test
    void matchesWarnBracket() {
        assertThat(ProcessGatherService.matchesErrOrWarn("2026-06-04 [WARN] caution")).isTrue();
        assertThat(ProcessGatherService.matchesErrOrWarn("[WARNING")).isTrue();
    }

    @Test
    void doesNotMatchInfoOrPlain() {
        assertThat(ProcessGatherService.matchesErrOrWarn("[INFO] hi")).isFalse();
        assertThat(ProcessGatherService.matchesErrOrWarn("plain")).isFalse();
        assertThat(ProcessGatherService.matchesErrOrWarn(null)).isFalse();
    }

    // ── parseGatherPort ─────────────────────────────────────────────

    @Test
    void parseGatherPort_returnsPortFromXml() throws IOException {
        Path xml = tmp.resolve("DGServer.xml");
        Files.write(xml,
            "<root><gather_port>5400</gather_port></root>".getBytes(StandardCharsets.UTF_8));
        assertThat(ProcessGatherService.parseGatherPort(xml)).isEqualTo("5400");
    }

    @Test
    void parseGatherPort_handlesCaseAndWhitespace() throws IOException {
        Path xml = tmp.resolve("DGServer.xml");
        Files.write(xml,
            "<GATHER_PORT>  5401  </GATHER_PORT>".getBytes(StandardCharsets.UTF_8));
        assertThat(ProcessGatherService.parseGatherPort(xml)).isEqualTo("5401");
    }

    @Test
    void parseGatherPort_missingFileReturnsNull() {
        assertThat(ProcessGatherService.parseGatherPort(tmp.resolve("nope.xml"))).isNull();
    }

    @Test
    void parseGatherPort_xmlWithoutPortReturnsNull() throws IOException {
        Path xml = tmp.resolve("plain.xml");
        Files.write(xml, "<root><other>x</other></root>".getBytes(StandardCharsets.UTF_8));
        assertThat(ProcessGatherService.parseGatherPort(xml)).isNull();
    }

    // ── pickLatestLog ───────────────────────────────────────────────

    @Test
    void pickLatestLog_returnsMostRecentMatchingPrefix() throws Exception {
        Path logDir = Files.createDirectory(tmp.resolve("log"));
        Path a = Files.createFile(logDir.resolve("DGM_5400.log"));
        Path b = Files.createFile(logDir.resolve("DGM_5401.log"));
        Path c = Files.createFile(logDir.resolve("DGS_5500.log"));  // 다른 prefix
        Files.setLastModifiedTime(a, java.nio.file.attribute.FileTime.fromMillis(1000));
        Files.setLastModifiedTime(b, java.nio.file.attribute.FileTime.fromMillis(2000));
        Files.setLastModifiedTime(c, java.nio.file.attribute.FileTime.fromMillis(9000));

        assertThat(ProcessGatherService.pickLatestLog(logDir, "DGM_")).isEqualTo(b);
        assertThat(ProcessGatherService.pickLatestLog(logDir, "DGS_")).isEqualTo(c);
    }

    @Test
    void pickLatestLog_noMatchReturnsNull() throws IOException {
        Path logDir = Files.createDirectory(tmp.resolve("log"));
        Files.createFile(logDir.resolve("noise.txt"));
        assertThat(ProcessGatherService.pickLatestLog(logDir, "DGM_")).isNull();
    }

    @Test
    void pickLatestLog_missingDirReturnsNull() {
        assertThat(ProcessGatherService.pickLatestLog(tmp.resolve("nope"), "DGM_")).isNull();
    }

    // ── scanErrors ───────────────────────────────────────────────────

    @Test
    void scanErrors_countsAndKeepsLastN() throws IOException {
        StringBuilder sb = new StringBuilder();
        for (int i = 1; i <= 700; i++) {
            // 짝수만 ERROR 라인 — 총 350개 ERROR.
            if (i % 2 == 0) sb.append("[ERROR] line").append(i).append('\n');
            else sb.append("[INFO]  line").append(i).append('\n');
        }
        Path lf = tmp.resolve("err.log");
        Files.write(lf, sb.toString().getBytes(StandardCharsets.UTF_8));

        ProcessGatherService.ScanResult r = ProcessGatherService.scanErrors(lf);
        assertThat(r.total).isEqualTo(350L);
        // OVERVIEW_LIMIT = 500. 350 < 500 — 모두 유지.
        assertThat(r.recent).hasSize(350);
        assertThat(r.recent.get(r.recent.size() - 1)).contains("line700");
    }

    @Test
    void scanErrors_overLimitKeepsLast500() throws IOException {
        StringBuilder sb = new StringBuilder();
        for (int i = 1; i <= 600; i++) sb.append("[ERROR] e").append(i).append('\n');
        Path lf = tmp.resolve("big.log");
        Files.write(lf, sb.toString().getBytes(StandardCharsets.UTF_8));

        ProcessGatherService.ScanResult r = ProcessGatherService.scanErrors(lf);
        assertThat(r.total).isEqualTo(600L);
        assertThat(r.recent).hasSize(500);
        assertThat(r.recent.get(0)).contains("e101");
        assertThat(r.recent.get(499)).contains("e600");
    }

    @Test
    void scanErrors_emptyFileReturnsZero() throws IOException {
        Path lf = tmp.resolve("empty.log");
        Files.write(lf, new byte[0]);
        ProcessGatherService.ScanResult r = ProcessGatherService.scanErrors(lf);
        assertThat(r.total).isEqualTo(0L);
        assertThat(r.recent).isEmpty();
    }

    // ── 빈 service_config — overview() 통합 ─────────────────────────

    @Test
    void overview_noDgPaths_returnsConfigError() {
        com.exem.inspector.config.ServiceConfig sc =
                org.mockito.Mockito.mock(com.exem.inspector.config.ServiceConfig.class);
        com.exem.inspector.config.ServicesBlock svc =
                org.mockito.Mockito.mock(com.exem.inspector.config.ServicesBlock.class);
        org.mockito.BDDMockito.given(sc.services()).willReturn(svc);
        org.mockito.BDDMockito.given(svc.dgserverM()).willReturn("");
        org.mockito.BDDMockito.given(svc.dgserverS()).willReturn(java.util.Collections.<String>emptyList());

        ProcessGatherService gs = new ProcessGatherService(sc);
        ProcessGatherPayload p = gs.overview();
        assertThat(p.getSections()).isEmpty();
        assertThat(p.getConfigError()).contains("DGServer paths");
        assertThat(p.getErrLimitPerSection()).isEqualTo(500);
    }

    @SuppressWarnings("unused")
    private void _unused() {
        // 미사용 import 경고 회피
        List<String> ignored = java.util.Collections.emptyList();
    }
}
