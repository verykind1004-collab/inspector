package com.exem.inspector.screen.alarmhistory;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Collections;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import com.exem.inspector.config.ServiceConfig;

/**
 * AlarmLogParser 단위 테스트 — 원본 _parse_send_logs 1:1 동등 검증.
 *
 * <p>Status 결정 케이스:
 * (1) Finish → success (선행 failed 없을 때)
 * (2) Failed/Exception/Error 키워드 → failed
 * (3) [ERROR] 라인 직전 thread + epoch 매핑 → failed
 * (4) Connection success → 선행 failed 도 success 로 덮어쓰기
 * (5) Failed 라인 직후 N라인 내 Caused by / ORA-/Exception 메시지 → error detail
 */
class AlarmLogParserTest {

    private final ServiceConfig serviceConfig = mock(ServiceConfig.class);
    private final AlarmLogParser parser = new AlarmLogParser(serviceConfig);

    private Path writeLog(Path dir, String name, String content) throws IOException {
        Path p = dir.resolve(name);
        Files.write(p, content.getBytes(StandardCharsets.UTF_8));
        return p;
    }

    // ── (1) Finish → success ─────────────────────────────────────────────
    @Test
    void finish_marks_success(@TempDir Path tmp) throws IOException {
        String body =
                "#1 @1 :[a, b, c, 5, 1717300000000, x]\n" +
                "#1 Finish\n";
        Path p = writeLog(tmp, "sms.log", body);

        Map<String, AlarmLogParser.Status> r = parser.parseSendLogs(Collections.singletonList(p));
        assertThat(r).containsKey("1717300000000");
        assertThat(r.get("1717300000000").status).isEqualTo("success");
    }

    // ── (2) Failed/Exception 키워드 → failed ─────────────────────────────
    @Test
    void failedKeyword_marks_failed(@TempDir Path tmp) throws IOException {
        String body =
                "#2 @1 :[a, b, c, 5, 1717400000000, x]\n" +
                "#2 send Failed\n";
        Path p = writeLog(tmp, "sms.log", body);

        Map<String, AlarmLogParser.Status> r = parser.parseSendLogs(Collections.singletonList(p));
        assertThat(r.get("1717400000000").status).isEqualTo("failed");
    }

    // ── (3) Connection success 가 선행 failed 덮어쓰기 ────────────────────
    @Test
    void connectionSuccess_overrides_priorFailed(@TempDir Path tmp) throws IOException {
        String body =
                "#3 @1 :[a, b, c, 5, 1717500000000, x]\n" +
                "#3 Connection failed\n" +
                "#3 Connection success\n";
        Path p = writeLog(tmp, "sms.log", body);

        Map<String, AlarmLogParser.Status> r = parser.parseSendLogs(Collections.singletonList(p));
        assertThat(r.get("1717500000000").status).isEqualTo("success");
    }

    // ── (4) API 패턴 ([ALARM PARAM] time=epoch) ──────────────────────────
    @Test
    void apiPattern_parsed(@TempDir Path tmp) throws IOException {
        String body =
                "#10 [ALARM PARAM] alarm time=1717600000000\n" +
                "[ERROR] #10 Connection refused\n";
        Path p = writeLog(tmp, "api.log", body);

        Map<String, AlarmLogParser.Status> r = parser.parseSendLogs(Collections.singletonList(p));
        assertThat(r).containsKey("1717600000000");
        assertThat(r.get("1717600000000").status).isEqualTo("failed");
    }

    // ── (5) Failed 직후 ORA- detail 캡처 ─────────────────────────────────
    @Test
    void failedDetail_orError_captured(@TempDir Path tmp) throws IOException {
        String body =
                "#20 @1 :[a, b, c, 5, 1717700000000, x]\n" +
                "#20 send Failed\n" +
                "ORA-12541: TNS:no listener\n";
        Path p = writeLog(tmp, "sms.log", body);

        Map<String, AlarmLogParser.Status> r = parser.parseSendLogs(Collections.singletonList(p));
        assertThat(r.get("1717700000000").status).isEqualTo("failed");
        assertThat(r.get("1717700000000").error).contains("ORA-12541");
    }

    // ── (6) 빈 입력 → 빈 map ─────────────────────────────────────────────
    @Test
    void emptyInput_returnsEmpty() {
        Map<String, AlarmLogParser.Status> r = parser.parseSendLogs(Collections.emptyList());
        assertThat(r).isEmpty();
    }

    // ── (7) 멀티 epoch 한 파일 ────────────────────────────────────────────
    @Test
    void multipleEpochs_parsedIndependently(@TempDir Path tmp) throws IOException {
        String body = String.join("\n", Arrays.asList(
                "#1 @1 :[a, b, c, 5, 1717800000000, x]",
                "#1 Finish",
                "#2 @1 :[a, b, c, 5, 1717800000001, x]",
                "#2 send Failed",
                ""));
        Path p = writeLog(tmp, "sms.log", body);

        Map<String, AlarmLogParser.Status> r = parser.parseSendLogs(Collections.singletonList(p));
        assertThat(r).hasSize(2);
        assertThat(r.get("1717800000000").status).isEqualTo("success");
        assertThat(r.get("1717800000001").status).isEqualTo("failed");
    }
}
