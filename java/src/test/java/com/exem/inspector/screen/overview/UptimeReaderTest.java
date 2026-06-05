package com.exem.inspector.screen.overview;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

/**
 * UptimeReader.formatEtime 단위 테스트 — 원본 _proc_uptime 변환 규칙.
 */
class UptimeReaderTest {

    @Test
    void empty_returnsDash() {
        assertThat(UptimeReader.formatEtime("")).isEqualTo("-");
        assertThat(UptimeReader.formatEtime("   ")).isEqualTo("-");
    }

    @Test
    void mmss_secondsOnly() {
        // 03:25 → 3 min 25 sec
        assertThat(UptimeReader.formatEtime("03:25")).isEqualTo("3m 25s");
    }

    @Test
    void hhmmss_hourMinSec() {
        // 02:30:15
        assertThat(UptimeReader.formatEtime("02:30:15")).isEqualTo("2h 30m 15s");
    }

    @Test
    void ddhhmmss_full() {
        // 5-12:34:56 (5 days 12 hours 34 min 56 sec)
        assertThat(UptimeReader.formatEtime("5-12:34:56")).isEqualTo("5d 12h 34m 56s");
    }

    @Test
    void zeroComponentsOmitted() {
        // 1-00:00:30 → "1d 30s" (h, m 생략)
        assertThat(UptimeReader.formatEtime("1-00:00:30")).isEqualTo("1d 30s");
    }

    @Test
    void invalid_returnsDash() {
        assertThat(UptimeReader.formatEtime("abc")).isEqualTo("-");
        assertThat(UptimeReader.formatEtime("1:2:3:4:5")).isEqualTo("-");
    }
}
