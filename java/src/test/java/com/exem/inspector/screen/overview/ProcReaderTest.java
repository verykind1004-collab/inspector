package com.exem.inspector.screen.overview;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/**
 * ProcReader 의 파싱 로직만 격리 단위 테스트한다.
 *
 * <p>실 /proc 접근(readCpuPercent / readUptime / readCpuCores) 는 Linux 전용이라
 * CI 비호환 — 임의 텍스트 파일을 대상으로 한 {@code readStatCounters / readMeminfo}
 * 만 검증한다.
 */
class ProcReaderTest {

    private final ProcReader r = new ProcReader();

    @Test
    void readStatCounters_parsesFirstLineNumbers(@TempDir Path tmp) throws IOException {
        // 원본 /proc/stat 첫 줄 포맷 그대로
        Path stat = tmp.resolve("stat");
        Files.write(stat,
                "cpu  100 5 50 800 10 0 2 0 0 0\n".getBytes(StandardCharsets.UTF_8));

        long[] v = r.readStatCounters(stat);

        // user nice system idle iowait irq softirq steal guest guest_nice → 10 컬럼
        assertThat(v).containsExactly(100L, 5L, 50L, 800L, 10L, 0L, 2L, 0L, 0L, 0L);
    }

    @Test
    void readMeminfo_parsesKbValues(@TempDir Path tmp) throws IOException {
        Path mem = tmp.resolve("meminfo");
        Files.write(mem, (
                "MemTotal:       16380400 kB\n"
              + "MemFree:         1024000 kB\n"
              + "Buffers:          200000 kB\n"
              + "Cached:          4000000 kB\n"
              + "Other:           ignored\n").getBytes(StandardCharsets.UTF_8));

        java.util.Map<String, Long> info = r.readMeminfo(mem);

        assertThat(info)
                .containsEntry("MemTotal", 16380400L)
                .containsEntry("MemFree",   1024000L)
                .containsEntry("Buffers",    200000L)
                .containsEntry("Cached",    4000000L)
                .doesNotContainKey("nonexistent");
    }

    @Test
    void readMeminfo_skipsNonNumericLines(@TempDir Path tmp) throws IOException {
        Path mem = tmp.resolve("meminfo");
        Files.write(mem, (
                "Broken line no colon\n"
              + "Bad:           not a number kB\n"
              + "Good:                100 kB\n").getBytes(StandardCharsets.UTF_8));

        java.util.Map<String, Long> info = r.readMeminfo(mem);

        assertThat(info).containsEntry("Good", 100L);
        assertThat(info).doesNotContainKey("Bad");
    }
}
