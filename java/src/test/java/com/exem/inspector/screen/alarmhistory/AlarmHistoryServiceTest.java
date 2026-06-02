package com.exem.inspector.screen.alarmhistory;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

/**
 * AlarmHistoryService 페이로드 조립 단위 테스트.
 *
 * <p>원본 page_alarm_history 1:1 동등 검증:
 * (1) Send Type 별 sub-row 분리 — 한 epoch 에 sms+api+mail 매칭 → 3행
 * (2) 매칭 없으면 sendType=null + status=skipped 1행
 * (3) success/failed/skipped 카운트
 * (4) Failed 행 error 메시지 fallback
 */
class AlarmHistoryServiceTest {

    @SuppressWarnings("unchecked")
    private final ObjectProvider<AlarmHistoryMapper> mapperProvider = mock(ObjectProvider.class);
    private final AlarmHistoryMapper mapper = mock(AlarmHistoryMapper.class);
    private final AlarmLogParser logParser = mock(AlarmLogParser.class);

    private final AlarmHistoryService service = new AlarmHistoryService(mapperProvider, logParser);

    private AlarmLogParser.Result emptyLogsResult() {
        AlarmLogParser.Result r = new AlarmLogParser.Result();
        for (String k : new String[] { "sms", "api", "mail" }) {
            r.paths.put(k, new ArrayList<>());
            r.jarActive.put(k, false);
        }
        return r;
    }

    private AlarmLogParser.Result logsWithKind(String kind, boolean active) {
        AlarmLogParser.Result r = emptyLogsResult();
        r.paths.get(kind).add(Paths.get("/tmp/dummy/" + kind + ".log"));
        r.jarActive.put(kind, active);
        return r;
    }

    private LinkedHashMap<String, Object> alarmRow(String inst, String time, long epoch,
                                                    String type, String name, String value) {
        LinkedHashMap<String, Object> r = new LinkedHashMap<>();
        r.put("instance_name", inst);
        r.put("alert_time", time);
        r.put("alert_epoch", epoch);
        r.put("alert_type", type);
        r.put("alert_name", name);
        r.put("alert_value", value);
        return r;
    }

    private void wireMapperRows(List<LinkedHashMap<String, Object>> rows) {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(mapper.findAlarms(anyString())).willReturn(rows);
    }

    // ── (1) Send Type 분리 — 한 epoch 에 sms + api 매칭 → 2 행 ──────────────
    @Test
    void subRows_perMatchedKind() {
        long epoch = 1717300000000L;
        wireMapperRows(Arrays.asList(alarmRow("ORA19", "2026-06-02 10:00:00", epoch,
                "Server Alert", "CPU_HIGH", "95")));

        AlarmLogParser.Result logs = emptyLogsResult();
        logs.paths.get("sms").add(Paths.get("/tmp/sms.log"));
        logs.paths.get("api").add(Paths.get("/tmp/api.log"));
        logs.jarActive.put("sms", true);
        logs.jarActive.put("api", true);
        given(logParser.findLogs(anyString())).willReturn(logs);

        Map<String, AlarmLogParser.Status> smsMap = new HashMap<>();
        smsMap.put(String.valueOf(epoch), new AlarmLogParser.Status("success", ""));
        given(logParser.parseSendLogs(logs.paths.get("sms"))).willReturn(smsMap);

        Map<String, AlarmLogParser.Status> apiMap = new HashMap<>();
        apiMap.put(String.valueOf(epoch), new AlarmLogParser.Status("failed", "Connection refused"));
        given(logParser.parseSendLogs(logs.paths.get("api"))).willReturn(apiMap);

        given(logParser.parseSendLogs(logs.paths.get("mail"))).willReturn(Collections.emptyMap());

        AlarmHistoryPayload p = service.build("2026-06-02");

        assertThat(p.getRows()).hasSize(2);
        AlarmHistoryRow smsRow = p.getRows().get(0);
        AlarmHistoryRow apiRow = p.getRows().get(1);

        // 정렬: KINDS 순서 sms→api→mail
        assertThat(smsRow.getSendType()).isEqualTo("sms");
        assertThat(smsRow.getStatus()).isEqualTo("success");
        assertThat(apiRow.getSendType()).isEqualTo("api");
        assertThat(apiRow.getStatus()).isEqualTo("failed");
        assertThat(apiRow.getError()).isEqualTo("Connection refused");

        assertThat(p.getSuccess()).isEqualTo(1);
        assertThat(p.getFailed()).isEqualTo(1);
        assertThat(p.getSkipped()).isEqualTo(0);
    }

    // ── (2) 매칭 없음 → sendType=null + skipped 1행 ──────────────────────
    @Test
    void noMatch_singleSkippedRow_nullSendType() {
        long epoch = 1717400000000L;
        wireMapperRows(Arrays.asList(alarmRow("ORA19", "2026-06-02 11:00:00", epoch,
                "Stat Alert", "MEM_HIGH", "90")));
        given(logParser.findLogs(anyString())).willReturn(emptyLogsResult());
        given(logParser.parseSendLogs(Collections.emptyList())).willReturn(Collections.emptyMap());

        AlarmHistoryPayload p = service.build("2026-06-02");

        assertThat(p.getRows()).hasSize(1);
        AlarmHistoryRow r = p.getRows().get(0);
        assertThat(r.getSendType()).isNull();
        assertThat(r.getStatus()).isEqualTo("skipped");
        assertThat(p.getSkipped()).isEqualTo(1);
        assertThat(p.getSuccess()).isZero();
        assertThat(p.getFailed()).isZero();
    }

    // ── (3) Mapper 없음 → 빈 rows, jarActive 만 반환 ────────────────────
    @Test
    void noMapper_emptyRows_butJarActiveStillReturned() {
        given(mapperProvider.getIfAvailable()).willReturn(null);
        given(logParser.findLogs(anyString())).willReturn(logsWithKind("sms", true));
        given(logParser.parseSendLogs(Collections.emptyList())).willReturn(Collections.emptyMap());

        AlarmHistoryPayload p = service.build("2026-06-02");

        assertThat(p.getRows()).isEmpty();
        assertThat(p.getJarActive().get("sms")).isTrue();
        assertThat(p.getJarActive().get("api")).isFalse();
        assertThat(p.getDate()).isEqualTo("2026-06-02");
    }

    // ── (4) Failed 행 error 비어있으면 latestError 로 fallback ───────────
    @Test
    void failed_error_fallbacks_to_latestError() {
        long oldEpoch = 1717100000000L;
        long newEpoch = 1717500000000L;
        wireMapperRows(Arrays.asList(alarmRow("ORA19", "2026-06-02 12:00:00", oldEpoch,
                "Server Alert", "X", "1")));

        AlarmLogParser.Result logs = emptyLogsResult();
        logs.paths.get("sms").add(Paths.get("/tmp/sms.log"));
        given(logParser.findLogs(anyString())).willReturn(logs);

        Map<String, AlarmLogParser.Status> smsMap = new HashMap<>();
        // oldEpoch 알람은 error 비어있는 failed, newEpoch 는 detail error 있는 failed
        smsMap.put(String.valueOf(oldEpoch), new AlarmLogParser.Status("failed", ""));
        smsMap.put(String.valueOf(newEpoch), new AlarmLogParser.Status("failed", "Network unreachable"));
        given(logParser.parseSendLogs(logs.paths.get("sms"))).willReturn(smsMap);
        given(logParser.parseSendLogs(logs.paths.get("api"))).willReturn(Collections.emptyMap());
        given(logParser.parseSendLogs(logs.paths.get("mail"))).willReturn(Collections.emptyMap());

        AlarmHistoryPayload p = service.build("2026-06-02");

        assertThat(p.getRows()).hasSize(1);
        AlarmHistoryRow r = p.getRows().get(0);
        assertThat(r.getStatus()).isEqualTo("failed");
        assertThat(r.getError()).isEqualTo("Network unreachable"); // latestError 사용
    }

    // ── (5) Date 정규화 — null/잘못된 형식 → today ─────────────────────
    @Test
    void normalizeDate_handlesNullAndInvalid() {
        given(mapperProvider.getIfAvailable()).willReturn(null);
        given(logParser.findLogs(anyString())).willReturn(emptyLogsResult());

        AlarmHistoryPayload p1 = service.build(null);
        AlarmHistoryPayload p2 = service.build("invalid-date");
        assertThat(p1.getDate()).matches("\\d{4}-\\d{2}-\\d{2}");
        assertThat(p2.getDate()).matches("\\d{4}-\\d{2}-\\d{2}");

        AlarmHistoryPayload p3 = service.build("2026-06-02T15:30:00");
        assertThat(p3.getDate()).isEqualTo("2026-06-02");
    }
}
