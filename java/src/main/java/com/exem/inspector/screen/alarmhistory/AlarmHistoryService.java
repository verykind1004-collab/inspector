package com.exem.inspector.screen.alarmhistory;

import java.nio.file.Path;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

/**
 * Alarm Send History 서비스 — SQL 결과 + 로그 파싱으로 행별 status/sendType 매핑.
 *
 * <p>원본 page_alarm_history 1:1 동등:
 * <ul>
 *   <li>kind 별(sms/api/mail) 로그를 분리 파싱 → 각 statusMap[kind] 생성</li>
 *   <li>알람 epoch 당 매칭되는 kind 개수만큼 sub-row 생성 (sendType=kind)</li>
 *   <li>어느 kind 도 매칭 안 되면 sendType=null + status=skipped 1행</li>
 * </ul>
 */
@Service
public class AlarmHistoryService {

    private static final Logger log = LoggerFactory.getLogger(AlarmHistoryService.class);

    private static final DateTimeFormatter YYYY_MM_DD = DateTimeFormatter.ofPattern("yyyy-MM-dd");
    private static final List<String> KINDS = Arrays.asList("sms", "api", "mail");

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

        // 2) kind 별 statusMap (원본 _kind_status)
        Map<String, Map<String, AlarmLogParser.Status>> kindStatus = new LinkedHashMap<>();
        for (String kind : KINDS) {
            List<Path> paths = logsResult.paths.getOrDefault(kind, Collections.emptyList());
            kindStatus.put(kind, paths.isEmpty()
                    ? Collections.emptyMap()
                    : logParser.parseSendLogs(paths));
        }

        // 3) latest status (모든 type 통합 최근값 — fallback error 메시지 용)
        String latestError = "";
        long latestEpoch = -1;
        for (Map<String, AlarmLogParser.Status> m : kindStatus.values()) {
            for (Map.Entry<String, AlarmLogParser.Status> e : m.entrySet()) {
                long ep;
                try { ep = Long.parseLong(e.getKey()); } catch (NumberFormatException ex) { continue; }
                if (ep > latestEpoch) {
                    latestEpoch = ep;
                    latestError = e.getValue().error == null ? "" : e.getValue().error;
                }
            }
        }

        // 4) SQL 알람 조회
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

        // 5) 행 매핑 — 각 알람 epoch 별 매칭 kind 만큼 sub-row 분리
        int success = 0, failed = 0, skipped = 0;
        List<AlarmHistoryRow> rows = new ArrayList<>();
        for (LinkedHashMap<String, Object> r : rawRows) {
            String instance = str(r.get("instance_name"));
            String alertTime = str(r.get("alert_time"));
            long epoch = lng(r.get("alert_epoch"));
            String type = str(r.get("alert_type"));
            String name = str(r.get("alert_name"));
            String value = str(r.get("alert_value"));
            String epochKey = stripFraction(String.valueOf(epoch));

            List<String> matchedKinds = new ArrayList<>();
            for (String kind : KINDS) {
                if (kindStatus.get(kind).containsKey(epochKey)) {
                    matchedKinds.add(kind);
                }
            }

            if (matchedKinds.isEmpty()) {
                // 어느 kind 매칭 안 됨 — skipped 1행
                rows.add(new AlarmHistoryRow(instance, alertTime, epoch, type, name, value,
                        null, "skipped", ""));
                skipped++;
            } else {
                for (String kind : matchedKinds) {
                    AlarmLogParser.Status info = kindStatus.get(kind).get(epochKey);
                    String status = info.status == null ? "skipped" : info.status;
                    String error = "";
                    if ("failed".equals(status)) {
                        error = (info.error == null || info.error.isEmpty()) ? latestError : info.error;
                    }
                    rows.add(new AlarmHistoryRow(instance, alertTime, epoch, type, name, value,
                            kind, status, error));
                    if ("success".equals(status)) success++;
                    else if ("failed".equals(status)) failed++;
                    else skipped++;
                }
            }
        }

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
}
