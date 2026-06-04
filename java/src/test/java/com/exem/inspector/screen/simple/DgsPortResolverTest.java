package com.exem.inspector.screen.simple;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/**
 * DgsPortResolver 단위 테스트 — XML gather_port 파싱 + 로그 sid → 시각 매핑.
 *
 * <p>실제 resolve() 는 ServiceConfig + 파일 시스템 의존이라 핵심 static helper 만 검증.
 */
class DgsPortResolverTest {

    // ── XML gather_port 파싱 ────────────────────────────────────────────
    @Test
    void parseXmlGatherPort_extracts(@TempDir Path tmp) throws IOException {
        Path xml = tmp.resolve("DGServer.xml");
        Files.write(xml, ("<root>\n  <gather_port>3000</gather_port>\n  <other>x</other>\n</root>")
                .getBytes(StandardCharsets.UTF_8));
        assertThat(DgsPortResolver.parseXmlGatherPort(xml)).isEqualTo("3000");
    }

    @Test
    void parseXmlGatherPort_whitespace_tolerated(@TempDir Path tmp) throws IOException {
        Path xml = tmp.resolve("DGServer.xml");
        Files.write(xml, "<gather_port>  4521  </gather_port>".getBytes(StandardCharsets.UTF_8));
        assertThat(DgsPortResolver.parseXmlGatherPort(xml)).isEqualTo("4521");
    }

    @Test
    void parseXmlGatherPort_missing_returnsNull(@TempDir Path tmp) throws IOException {
        Path xml = tmp.resolve("DGServer.xml");
        Files.write(xml, "<root><other>x</other></root>".getBytes(StandardCharsets.UTF_8));
        assertThat(DgsPortResolver.parseXmlGatherPort(xml)).isNull();
    }

    @Test
    void parseXmlGatherPort_fileNotExists_returnsNull(@TempDir Path tmp) {
        assertThat(DgsPortResolver.parseXmlGatherPort(tmp.resolve("missing.xml"))).isNull();
    }

    // ── scanLastBySid — [DB 10MIN SUMMARY] 라인 파싱 ─────────────────
    @Test
    void scanLastBySid_extractsSidTimePairs(@TempDir Path tmp) throws IOException {
        Path log = tmp.resolve("DGS_3000.log");
        Files.write(log, String.join("\n",
                "[10:00:00.123] random line",
                "[10:05:00.456] [DB 10MIN SUMMARY] server_id=7 something",
                "[10:10:00.789] [DB 10MIN SUMMARY] server_id=7 next",
                "[10:15:00.999] [DB 10MIN SUMMARY] server_id=8 other",
                "[10:20:00.000] unrelated line",
                "").getBytes(StandardCharsets.UTF_8));

        Map<String, String> r = DgsPortResolver.scanLastBySid(log);
        // sid=7 의 마지막 시각 = 10:10:00.789 (파일 끝쪽 = 늦은 시각, last-write-wins)
        assertThat(r).containsEntry("7", "10:10:00.789").containsEntry("8", "10:15:00.999");
    }

    @Test
    void scanLastBySid_noSummaryLines_returnsEmpty(@TempDir Path tmp) throws IOException {
        Path log = tmp.resolve("DGS_3000.log");
        Files.write(log, "[10:00:00.123] random\n[10:05:00.456] other".getBytes(StandardCharsets.UTF_8));
        assertThat(DgsPortResolver.scanLastBySid(log)).isEmpty();
    }

    @Test
    void scanLastBySid_missingFile_returnsEmpty(@TempDir Path tmp) {
        assertThat(DgsPortResolver.scanLastBySid(tmp.resolve("missing.log"))).isEmpty();
    }

    // ── pickLogFile — DGS_<port>.log 우선, 없으면 mtime 최신 ────────
    @Test
    void pickLogFile_directMatchExists(@TempDir Path tmp) throws IOException {
        Files.write(tmp.resolve("DGS_3000.log"), "x".getBytes(StandardCharsets.UTF_8));
        Files.write(tmp.resolve("DGS_4000.log"), "x".getBytes(StandardCharsets.UTF_8));
        Path picked = DgsPortResolver.pickLogFile(tmp, "3000");
        assertThat(picked.getFileName().toString()).isEqualTo("DGS_3000.log");
    }

    @Test
    void pickLogFile_directMissing_picksLatest(@TempDir Path tmp) throws IOException, InterruptedException {
        Path older = tmp.resolve("DGS_2000.log");
        Path newer = tmp.resolve("DGS_5000.log");
        Files.write(older, "x".getBytes(StandardCharsets.UTF_8));
        Thread.sleep(20);
        Files.write(newer, "x".getBytes(StandardCharsets.UTF_8));
        // 명시적 mtime 차이 강제
        Files.setLastModifiedTime(newer, java.nio.file.attribute.FileTime.fromMillis(System.currentTimeMillis()));
        Files.setLastModifiedTime(older, java.nio.file.attribute.FileTime.fromMillis(System.currentTimeMillis() - 100000));

        Path picked = DgsPortResolver.pickLogFile(tmp, "3000");
        assertThat(picked.getFileName().toString()).isEqualTo("DGS_5000.log");
    }

    @Test
    void pickLogFile_noDgsLogs_returnsNull(@TempDir Path tmp) throws IOException {
        Files.write(tmp.resolve("unrelated.log"), "x".getBytes(StandardCharsets.UTF_8));
        assertThat(DgsPortResolver.pickLogFile(tmp, "3000")).isNull();
    }

    @Test
    void pickLogFile_dirMissing_returnsNull(@TempDir Path tmp) {
        assertThat(DgsPortResolver.pickLogFile(tmp.resolve("nope"), "3000")).isNull();
    }
}
