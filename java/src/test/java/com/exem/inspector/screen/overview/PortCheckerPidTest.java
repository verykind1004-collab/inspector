package com.exem.inspector.screen.overview;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

/**
 * PortChecker.parsePidFrom 단위 테스트 — ss/netstat 출력 파싱 규칙.
 */
class PortCheckerPidTest {

    @Test
    void ssOutput_pidEqFormat() {
        String out =
                "State  Recv-Q  Send-Q  Local Address:Port  Peer Address:Port\n" +
                "LISTEN 0      50      *:8083              *:*    users:((\"java\",pid=12345,fd=78))\n";
        assertThat(PortChecker.parsePidFrom(out, ":8083")).isEqualTo("12345");
    }

    @Test
    void netstatOutput_pidSlashName() {
        String out =
                "Active Internet connections (only servers)\n" +
                "tcp  0  0  0.0.0.0:5050  0.0.0.0:*  LISTEN  9876/jetty\n";
        assertThat(PortChecker.parsePidFrom(out, ":5050")).isEqualTo("9876");
    }

    @Test
    void noMatch_returnsNull() {
        String out = "LISTEN 0 50 *:9999 *:* users:((\"x\",pid=1,fd=2))\n";
        assertThat(PortChecker.parsePidFrom(out, ":8083")).isNull();
    }

    @Test
    void nullOutput_returnsNull() {
        assertThat(PortChecker.parsePidFrom(null, ":8083")).isNull();
    }
}
