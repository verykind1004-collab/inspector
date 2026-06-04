package com.exem.inspector.screen.alert;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

/**
 * AlertService 단위 테스트 — 원본 api_alert_times 1:1 검증.
 *
 * <p>(1) 빈 파라미터 / 부정 문자(따옴표/세미콜론/백슬래시) 거부
 * (2) PG schema sanitize (인스턴스명 → 영문 소문자/숫자/언더스코어만)
 * (3) 행 매핑 + total 합산
 * (4) 매퍼 미가용 시 빈 응답
 */
class AlertServiceTest {

    @SuppressWarnings("unchecked")
    private final ObjectProvider<AlertMapper> mapperProvider = mock(ObjectProvider.class);
    private final AlertMapper mapper = mock(AlertMapper.class);

    private final AlertService service = new AlertService(mapperProvider);

    private LinkedHashMap<String, Object> row(String day, int cnt) {
        LinkedHashMap<String, Object> r = new LinkedHashMap<>();
        r.put("DAY", day);
        r.put("CNT", cnt);
        return r;
    }

    // ── (1) 입력 검증 ───────────────────────────────────────────────
    @Test
    void missingParameters_rejected() {
        assertThatThrownBy(() -> service.build(null, "ALARM"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Missing parameters");
        assertThatThrownBy(() -> service.build("", "ALARM"))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> service.build("INST", null))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> service.build("INST", ""))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void invalidCharacters_rejected() {
        for (String bad : new String[] { "INST'", "INST\"", "INST;", "INST\\" }) {
            assertThatThrownBy(() -> service.build(bad, "ALARM"))
                    .isInstanceOf(IllegalArgumentException.class)
                    .hasMessage("Invalid characters");
        }
        assertThatThrownBy(() -> service.build("INST", "ALARM'"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    // ── (2) PG schema sanitize ──────────────────────────────────────
    @Test
    void schemaSanitize_alphanumLowerOnly() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(mapper.findDailyCounts(anyString(), anyString(), anyString()))
                .willReturn(Collections.emptyList());

        service.build("ORA-19c.Prod", "RTS Server Down");

        // 원본 정규화: lower() 후 [^a-z0-9_] 제거 → "ora19cprod"
        org.mockito.Mockito.verify(mapper).findDailyCounts(
                eq("ora19cprod"), eq("ORA-19c.Prod"), eq("RTS Server Down"));
    }

    // ── (3) 행 매핑 + total ────────────────────────────────────────
    @Test
    void rowMapping_andTotal() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        List<LinkedHashMap<String, Object>> rows = Arrays.asList(
                row("2026-06-04", 5),
                row("2026-06-03", 2),
                row("2026-06-01", 1)
        );
        given(mapper.findDailyCounts(anyString(), anyString(), anyString())).willReturn(rows);

        AlertTimesResponse r = service.build("INST1", "ALARM_X");

        assertThat(r.getDays()).hasSize(3);
        assertThat(r.getDays().get(0).getDay()).isEqualTo("2026-06-04");
        assertThat(r.getDays().get(0).getCount()).isEqualTo(5);
        assertThat(r.getTotal()).isEqualTo(8);
    }

    @Test
    void rowMapping_skipsBlankDay() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        List<LinkedHashMap<String, Object>> rows = Arrays.asList(
                row("", 99),
                row("2026-06-04", 5)
        );
        given(mapper.findDailyCounts(anyString(), anyString(), anyString())).willReturn(rows);

        AlertTimesResponse r = service.build("INST", "ALARM");

        assertThat(r.getDays()).hasSize(1);
        assertThat(r.getTotal()).isEqualTo(5);
    }

    // ── (4) 매퍼 미가용 시 빈 응답 ────────────────────────────────
    @Test
    void mapperUnavailable_emptyResponse() {
        given(mapperProvider.getIfAvailable()).willReturn(null);

        AlertTimesResponse r = service.build("INST", "ALARM");

        assertThat(r.getDays()).isEmpty();
        assertThat(r.getTotal()).isEqualTo(0);
    }

    // ── (5) 매퍼 예외 → IllegalStateException + 120자 절단 ────────
    @Test
    void mapperException_wrappedAndTruncated() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 200; i++) sb.append('x');
        given(mapper.findDailyCounts(anyString(), anyString(), anyString()))
                .willThrow(new RuntimeException(sb.toString()));

        assertThatThrownBy(() -> service.build("INST", "ALARM"))
                .isInstanceOf(IllegalStateException.class)
                .satisfies(e -> assertThat(e.getMessage()).hasSize(120));
    }
}
