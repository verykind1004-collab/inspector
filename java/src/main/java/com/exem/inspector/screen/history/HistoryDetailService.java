package com.exem.inspector.screen.history;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

/**
 * Inspector History 상세 화면 — OS(CPU/Memory) 등 페이지별 차트 데이터.
 *
 * <p>원본 history_views.py 의 api_history_os/tbs/heap/qcnt/service 1:1.
 * 통합 단순 표는 {@link HistoryService} 가 담당하고, 본 서비스는 차트용 시계열 응답을 만든다.
 */
@Service
public class HistoryDetailService {

    private static final DateTimeFormatter DATE_FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd");

    private final ObjectProvider<HistoryMapper> mapperProvider;

    public HistoryDetailService(ObjectProvider<HistoryMapper> mapperProvider) {
        this.mapperProvider = mapperProvider;
    }

    /**
     * api_history_os 1:1 — date + from(HH:MM) + to(HH:MM) → 시계열 rows.
     *
     * <p>잘못된 date/time 은 원본과 동일하게 기본값(today / 00:00 / 23:59)으로 대체.
     */
    public HistoryOsPayload os(String dateRaw, String fromRaw, String toRaw) {
        String date = normalizeDate(dateRaw);
        String from = normalizeTime(fromRaw, "00:00");
        String to   = normalizeTime(toRaw,   "23:59");
        String start = date + " " + from + ":00";
        String end   = date + " " + to   + ":59";

        HistoryMapper mapper = mapperProvider.getIfAvailable();
        List<HistoryOsRow> rows;
        if (mapper == null) {
            rows = Collections.emptyList();
        } else {
            List<LinkedHashMap<String, Object>> raw = mapper.findOsRange(start, end);
            rows = new ArrayList<>(raw.size());
            for (LinkedHashMap<String, Object> r : raw) {
                rows.add(new HistoryOsRow(
                        asString(r.get("ts")),
                        asDouble(r.get("cpu_pct")),
                        asDouble(r.get("cpu_user")),
                        asDouble(r.get("cpu_sys")),
                        asDouble(r.get("cpu_io")),
                        asDouble(r.get("mem_total")),
                        asDouble(r.get("mem_used")),
                        asDouble(r.get("mem_free")),
                        asDouble(r.get("mem_pct"))));
            }
        }
        return new HistoryOsPayload(rows, date, from, to);
    }

    // ── helpers ──────────────────────────────────────────────────────────

    static String normalizeDate(String raw) {
        if (raw == null || raw.isEmpty()) {
            return LocalDate.now().format(DATE_FMT);
        }
        try {
            return LocalDate.parse(raw, DATE_FMT).format(DATE_FMT);
        } catch (RuntimeException ignored) {
            return LocalDate.now().format(DATE_FMT);
        }
    }

    static String normalizeTime(String raw, String fallback) {
        if (raw == null || raw.length() != 5 || raw.charAt(2) != ':') {
            return fallback;
        }
        try {
            int hh = Integer.parseInt(raw.substring(0, 2));
            int mm = Integer.parseInt(raw.substring(3, 5));
            if (hh < 0 || hh > 23 || mm < 0 || mm > 59) {
                return fallback;
            }
            return raw;
        } catch (NumberFormatException e) {
            return fallback;
        }
    }

    private static String asString(Object v) {
        return v == null ? null : v.toString();
    }

    private static Double asDouble(Object v) {
        if (v == null) return null;
        if (v instanceof Number) return ((Number) v).doubleValue();
        try {
            return Double.parseDouble(v.toString());
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
