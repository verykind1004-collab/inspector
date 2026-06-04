package com.exem.inspector.screen.alert;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.regex.Pattern;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

/**
 * Alert 일별 카운트 서비스 — 원본 {@code api_alert_times} 1:1.
 *
 * <p>검증 규칙(원본 동일):
 * <ul>
 *   <li>inst/alarm 필수</li>
 *   <li>{@code ' " ; \\} 4 문자 포함 시 거부(인젝션 방지)</li>
 *   <li>PG 의 schema 는 {@code [^a-z0-9_]} 제거(원본 정규화) 후 비어 있으면 거부</li>
 * </ul>
 */
@Service
public class AlertService {

    private static final Logger log = LoggerFactory.getLogger(AlertService.class);
    private static final Pattern BAD = Pattern.compile("['\";\\\\]");
    private static final Pattern SCHEMA_KEEP = Pattern.compile("[^a-z0-9_]");

    private final ObjectProvider<AlertMapper> mapperProvider;

    public AlertService(ObjectProvider<AlertMapper> mapperProvider) {
        this.mapperProvider = mapperProvider;
    }

    public AlertTimesResponse build(String inst, String alarm) {
        if (inst == null || inst.isEmpty() || alarm == null || alarm.isEmpty()) {
            throw new IllegalArgumentException("Missing parameters");
        }
        if (BAD.matcher(inst).find() || BAD.matcher(alarm).find()) {
            throw new IllegalArgumentException("Invalid characters");
        }

        // PG schema (Oracle 에서는 사용되지 않음). 원본 sanitize 동일.
        String schema = SCHEMA_KEEP.matcher(inst.toLowerCase()).replaceAll("");

        AlertMapper mapper = mapperProvider.getIfAvailable();
        if (mapper == null) {
            // 리포지토리 DB 미설정 — 빈 응답으로 안전 처리
            return new AlertTimesResponse(Collections.emptyList(), 0);
        }

        List<LinkedHashMap<String, Object>> rows;
        try {
            rows = mapper.findDailyCounts(schema, inst, alarm);
        } catch (RuntimeException e) {
            log.warn("ora_alarm_history 일별 조회 실패", e);
            String msg = e.getMessage() == null ? "조회 실패" : e.getMessage();
            if (msg.length() > 120) msg = msg.substring(0, 120);
            throw new IllegalStateException(msg);
        }
        if (rows == null) rows = Collections.emptyList();

        List<AlertTimesResponse.Day> days = new ArrayList<>(rows.size());
        int total = 0;
        for (LinkedHashMap<String, Object> r : rows) {
            String day = str(r.get("DAY"));
            if (day.isEmpty()) continue;
            int cnt = toInt(r.get("CNT"));
            days.add(new AlertTimesResponse.Day(day, cnt));
            total += cnt;
        }
        return new AlertTimesResponse(days, total);
    }

    private static String str(Object o) {
        return o == null ? "" : String.valueOf(o).trim();
    }

    private static int toInt(Object o) {
        if (o == null) return 0;
        if (o instanceof Number) return ((Number) o).intValue();
        try { return Integer.parseInt(String.valueOf(o).trim()); }
        catch (NumberFormatException e) { return 0; }
    }
}
