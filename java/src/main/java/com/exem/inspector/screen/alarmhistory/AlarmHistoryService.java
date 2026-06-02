package com.exem.inspector.screen.alarmhistory;

import java.nio.file.Path;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

/**
 * Alarm Send History 서비스 — SQL 결과 + 로그 파싱으로 행별 status 매핑.
 *
 * <p>원본 page_alarm_history 와 1:1 동등(데이터 부분).
 */
@Service
public class AlarmHistoryService {

    private static final Logger log = LoggerFactory.getLogger(AlarmHistoryService.class);

    private static final DateTimeFormatter YYYY_MM_DD = DateTimeFormatter.ofPattern("yyyy-MM-dd");

    private final ObjectProvider<AlarmHistoryMapper> mapperProvider;
    private final AlarmLogParser logParser;

    public AlarmHistoryService(ObjectProvider<AlarmHistoryMapper> mapperProvider,
                               AlarmLogParser logParser) {
        this.mapperProvider = mapperProvider;
        this.logParser = logParser;
    }

    public AlarmHistoryPayload build(String dateParam) {
        String selDate = normalizeDate(dateParam);

        // 1) 로그 수집 + jarActive
        AlarmLogParser.Result logsResult = logParser.findLogs(selDate);
        List<Path> all = new ArrayList<>();
        all.addAll(logsResult.paths.getOrDefault("sms", Collections.emptyList()));
        all.addAll(logsResult.paths.getOrDefault("api", Collections.emptyList()));
        all.addAll(logsResult.paths.getOrDefault("mail", Collections.emptyList()));
        Map<String, AlarmLogParser.Status> statusMap =
                all.isEmpty() ? Collections.emptyMap() : logParser.parseSendLogs(all);

        // 2) SQL 알람 조회
        List<LinkedHashMap<String, Object>> rawRows = Collections.emptyList();
        AlarmHistoryMapper mapper = mapperProvider.getIfAvailable();
        if (mapper != null) {
            try {
                List<LinkedHashMap<String, Object>> r = mapper.findAlarms(selDate);
                if (r != null) rawRows = r;
            } catch (RuntimeException e) {
                log.warn("ora_alarm_history 조회 실패", e);
            }
        }

        // 3) 행 매핑 + 카운트
        boolean anyJar = Boolean.TRUE.equals(logsResult.jarActive.get("sms"))
                || Boolean.TRUE.equals(logsResult.jarActive.get("api"))
                || Boolean.TRUE.equals(logsResult.jarActive.get("mail"));
        String latestStatus = "";
        String latestError = "";
        if (!statusMap.isEmpty()) {
            String latestKey = Collections.max(statusMap.keySet());
            AlarmLogParser.Status s = statusMap.get(latestKey);
            latestStatus = s.status;
            latestError = s.error;
        }

        int success = 0, failed = 0, skipped = 0;
        List<AlarmHistoryRow> rows = new ArrayList<>(rawRows.size());
        for (LinkedHashMap<String, Object> r : rawRows) {
            String instance = str(r.get("instance_name"));
            String alertTime = str(r.get("alert_time"));
            long epoch = lng(r.get("alert_epoch"));
            String type = str(r.get("alert_type"));
            String name = str(r.get("alert_name"));
            String value = str(r.get("alert_value"));
            String epochKey = stripFraction(String.valueOf(epoch));
            String status;
            String error = "";
            AlarmLogParser.Status info = statusMap.get(epochKey);
            if (info != null && "success".equals(info.status)) {
                status = "success";
            } else if (info != null && "failed".equals(info.status)) {
                status = "failed";
                error = info.error == null ? latestError : info.error;
            } else {
                status = "skipped";
                _suppress(anyJar);
            }
            rows.add(new AlarmHistoryRow(instance, alertTime, epoch, type, name, value, status, error));
            if ("success".equals(status)) success++;
            else if ("failed".equals(status)) failed++;
            else skipped++;
        }
        _suppress(latestStatus); _suppress(latestError);

        Map<String, Boolean> jarActive = new LinkedHashMap<>();
        jarActive.put("sms",  Boolean.TRUE.equals(logsResult.jarActive.get("sms")));
        jarActive.put("api",  Boolean.TRUE.equals(logsResult.jarActive.get("api")));
        jarActive.put("mail", Boolean.TRUE.equals(logsResult.jarActive.get("mail")));

        return new AlarmHistoryPayload(selDate, jarActive, success, failed, skipped, rows);
    }

    private static String normalizeDate(String date) {
        if (date == null || date.isEmpty()) {
            return LocalDate.now().format(YYYY_MM_DD);
        }
        try {
            return LocalDate.parse(date.substring(0, Math.min(10, date.length())), YYYY_MM_DD)
                    .format(YYYY_MM_DD);
        } catch (DateTimeParseException e) {
            return LocalDate.now().format(YYYY_MM_DD);
        }
    }

    private static String stripFraction(String epoch) {
        int dot = epoch.indexOf('.');
        return dot >= 0 ? epoch.substring(0, dot) : epoch;
    }

    private static String str(Object o) { return o == null ? "" : String.valueOf(o).trim(); }
    private static long lng(Object o) {
        if (o == null) return 0;
        if (o instanceof Number) return ((Number) o).longValue();
        try { return Long.parseLong(String.valueOf(o).trim()); }
        catch (NumberFormatException e) { return 0; }
    }
    @SuppressWarnings("unused")
    private static void _suppress(Object o) { /* satisfy javac unused */ }
}
