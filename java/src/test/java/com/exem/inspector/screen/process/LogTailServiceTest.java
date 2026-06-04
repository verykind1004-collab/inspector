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
 * LogTailService 단위 테스트 — 원본 api_log_tail 동등성 + 안전성 검증.
 */
class LogTailServiceTest {

    private Path tmpDir;
    private LogTailService svc;

    @BeforeEach
    void setUp() throws IOException {
        tmpDir = Files.createTempDirectory("log-tail-test-");
        svc = new LogTailService(tmpDir.toAbsolutePath().toString());
    }

    @AfterEach
    void tearDown() throws IOException {
        // 재귀 삭제
        if (Files.exists(tmpDir)) {
            Files.walk(tmpDir)
                 .sorted(java.util.Comparator.reverseOrder())
                 .forEach(p -> { try { Files.delete(p); } catch (IOException ignored) {} });
        }
    }

    private Path writeFile(String name, String content) throws IOException {
        Path p = tmpDir.resolve(name);
        Files.write(p, content.getBytes(StandardCharsets.UTF_8));
        return p;
    }

    // ── 안전성 ───────────────────────────────────────────────────────

    @Test
    void rejectsPathOutsideAllowedRoot() {
        LogTailResult r = svc.read("/etc/passwd", 0);
        assertThat(r.getError()).isEqualTo("forbidden path");
        assertThat(r.getLines()).isNull();
    }

    @Test
    void rejectsNullOrEmptyPath() {
        assertThat(svc.read(null, 0).getError()).isEqualTo("file not found");
        assertThat(svc.read("",   0).getError()).isEqualTo("file not found");
    }

    @Test
    void reportsFileNotFound() {
        LogTailResult r = svc.read(tmpDir.resolve("nope.log").toString(), 0);
        assertThat(r.getError()).isEqualTo("file not found");
    }

    // ── offset == 0 (tail 마지막 N 줄) ────────────────────────────────

    @Test
    void offset0_returnsLastNLinesAndFileSize() throws IOException {
        StringBuilder sb = new StringBuilder();
        for (int i = 1; i <= 500; i++) sb.append("line").append(i).append('\n');
        Path p = writeFile("a.log", sb.toString());

        LogTailResult r = svc.read(p.toString(), 0);
        assertThat(r.getError()).isNull();
        assertThat(r.getOffset()).isEqualTo(Files.size(p));
        // TAIL_LINES = 300
        assertThat(r.getLines()).hasSize(300);
        assertThat(r.getLines().get(0)).isEqualTo("line201");
        assertThat(r.getLines().get(299)).isEqualTo("line500");
    }

    @Test
    void offset0_smallFileReturnsAllLines() throws IOException {
        Path p = writeFile("small.log", "alpha\nbeta\ngamma\n");
        LogTailResult r = svc.read(p.toString(), 0);
        assertThat(r.getLines()).containsExactly("alpha", "beta", "gamma");
        assertThat(r.getOffset()).isEqualTo(Files.size(p));
    }

    @Test
    void offset0_emptyFileReturnsEmptyLines() throws IOException {
        Path p = writeFile("empty.log", "");
        LogTailResult r = svc.read(p.toString(), 0);
        assertThat(r.getError()).isNull();
        assertThat(r.getLines()).isEmpty();
        assertThat(r.getOffset()).isEqualTo(0L);
    }

    // ── offset > 0 (incremental seek) ───────────────────────────────

    @Test
    void incremental_returnsOnlyNewLines() throws IOException {
        Path p = writeFile("inc.log", "a\nb\n");
        LogTailResult first = svc.read(p.toString(), 0);
        long off = first.getOffset();

        // append
        Files.write(p, "c\nd\n".getBytes(StandardCharsets.UTF_8),
                java.nio.file.StandardOpenOption.APPEND);

        LogTailResult next = svc.read(p.toString(), off);
        assertThat(next.getLines()).containsExactly("c", "d");
        assertThat(next.getOffset()).isEqualTo(Files.size(p));
    }

    @Test
    void incremental_noChangesReturnsEmpty() throws IOException {
        Path p = writeFile("stable.log", "single\n");
        LogTailResult first = svc.read(p.toString(), 0);
        LogTailResult next  = svc.read(p.toString(), first.getOffset());
        assertThat(next.getLines()).isEmpty();
        assertThat(next.getOffset()).isEqualTo(first.getOffset());
    }

    @Test
    void offsetBeyondSize_resetsToZero_returnsAllAsFresh() throws IOException {
        // 파일이 rotate 된 시나리오: 기존 offset 이 새 파일보다 크다.
        Path p = writeFile("rotated.log", "alpha\nbeta\n");
        LogTailResult r = svc.read(p.toString(), 9_999_999L);
        // reset to 0 → 마지막 N 라인 반환(여기선 2줄)
        assertThat(r.getError()).isNull();
        assertThat(r.getLines()).containsExactly("alpha", "beta");
    }

    // ── splitLines 유틸 ────────────────────────────────────────────

    @Test
    void splitLines_trailingNewlineNotEmptyLine() {
        assertThat(LogTailService.splitLines("a\nb\n")).containsExactly("a", "b");
    }

    @Test
    void splitLines_noTrailingNewline_keepsLast() {
        assertThat(LogTailService.splitLines("a\nb")).containsExactly("a", "b");
    }

    @Test
    void splitLines_emptyReturnsEmpty() {
        assertThat(LogTailService.splitLines("")).isEmpty();
        assertThat(LogTailService.splitLines(null)).isEmpty();
    }

    @Test
    void readTailLines_handlesTrailingNewlineOnly() throws IOException {
        Path p = writeFile("trailing.log", "alpha\n");
        List<String> out = LogTailService.readTailLines(p, 10);
        assertThat(out).containsExactly("alpha");
    }
}
