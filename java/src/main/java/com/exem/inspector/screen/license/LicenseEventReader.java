package com.exem.inspector.screen.license;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import com.exem.inspector.config.ServiceConfig;

/**
 * DGServer_M 로그 디렉토리에서 오늘자 LICENSE 이벤트를 추출한다.
 *
 * <p>원본 {@code _get_license_events()} / {@code _parse_license_line()} 1:1 동등.
 *
 * <ul>
 *   <li>현재 active log 파일({@code DGM_*.log}, .zip 아님): 이름에 yyyymmdd 가 있으면 오늘만, 없으면 오늘 active 로 간주.</li>
 *   <li>오늘자 zip({@code DGM_*_yyyymmdd_*.log.zip}): 내부 엔트리 스트림으로 라인 grep.</li>
 *   <li>제외 패턴: {@code [LICENSE MANAGER]}, {@code SEND ALARM HISTORY to WEBSOCKET},
 *       {@code LICENSE ALERT DAO}, {@code SEND LAST ALARM}, {@code LICENSE DB INFO DAO}.</li>
 * </ul>
 */
@Component
public class LicenseEventReader {

    private static final Logger log = LoggerFactory.getLogger(LicenseEventReader.class);

    private static final DateTimeFormatter YYYYMMDD = DateTimeFormatter.ofPattern("yyyyMMdd");
    private static final DateTimeFormatter YYYY_MM_DD = DateTimeFormatter.ofPattern("yyyy-MM-dd");

    private static final Pattern DATE_IN_NAME = Pattern.compile("(\\d{8})");
    private static final Pattern TIME_BRACKET = Pattern.compile("\\[(\\d{2}:\\d{2}:\\d{2}\\.\\d{3})\\]");
    private static final Pattern SERVER_ID = Pattern.compile("server_id=(\\d+)");
    private static final Pattern VALID_KV  = Pattern.compile("valid=(\\d+|\\w+)");
    private static final Pattern EVENT_BRACKET = Pattern.compile(
            "\\[([^\\]]*LICENSE[^\\]]*)\\]", Pattern.CASE_INSENSITIVE);
    private static final Pattern DESC_KV = Pattern.compile("desc=([^\\]]*)");

    /** 제외 키워드(원본 동일). */
    private static final String[] EXCLUDE = {
            "[LICENSE MANAGER]",
            "SEND ALARM HISTORY to WEBSOCKET",
            "LICENSE ALERT DAO",
            "SEND LAST ALARM",
            "LICENSE DB INFO DAO",
    };

    private final ServiceConfig serviceConfig;

    public LicenseEventReader(ServiceConfig serviceConfig) {
        this.serviceConfig = serviceConfig;
    }

    /**
     * @return (events, error) — error 가 null 이면 events 가 유효(빈 리스트 가능).
     */
    public Result read() {
        String dgmHome = serviceConfig.services().dgserverM();
        if (dgmHome == null || dgmHome.isEmpty()) {
            return new Result(Collections.emptyList(), "DGServer_M이 설정되지 않았습니다.");
        }
        Path logDir = Paths.get(dgmHome, "log");
        if (!Files.isDirectory(logDir)) {
            return new Result(Collections.emptyList(), "로그 디렉토리를 찾을 수 없습니다.");
        }

        LocalDate today = LocalDate.now();
        String todayStr = today.format(YYYYMMDD);
        String todayDateFmt = today.format(YYYY_MM_DD);

        List<LicenseEventRow> events = new ArrayList<>();

        // 1) Current DGM_*.log 파일들 (zip 아님)
        try (DirectoryStream<Path> stream = Files.newDirectoryStream(logDir, "DGM_*.log")) {
            for (Path logfile : stream) {
                String fname = logfile.getFileName().toString();
                if (fname.endsWith(".zip")) continue; // glob 이 이미 거르지만 안전망.
                String logDateFmt;
                Matcher dm = DATE_IN_NAME.matcher(fname);
                if (dm.find()) {
                    String logDate = dm.group(1);
                    if (!logDate.equals(todayStr)) continue; // 오늘 외 스킵
                    logDateFmt = logDate.substring(0, 4) + "-" + logDate.substring(4, 6) + "-" + logDate.substring(6);
                } else {
                    // DGM_<port>.log = 오늘 active log
                    logDateFmt = todayDateFmt;
                }
                grepLicense(logfile, logDateFmt, events);
            }
        } catch (IOException e) {
            log.warn("DGM log 디렉토리 스캔 실패: {}", e.getMessage());
        }

        // 2) 오늘자 zip: DGM_*_yyyymmdd_*.log.zip
        try (DirectoryStream<Path> stream =
                     Files.newDirectoryStream(logDir, "DGM_*_" + todayStr + "_*.log.zip")) {
            for (Path zipPath : stream) {
                grepLicenseInZip(zipPath, todayDateFmt, events);
            }
        } catch (IOException e) {
            log.warn("DGM zip 스캔 실패: {}", e.getMessage());
        }

        // 시간 내림차순 정렬(원본 reverse=True).
        events.sort((a, b) -> b.getTs().compareTo(a.getTs()));
        return new Result(events, null);
    }

    private void grepLicense(Path file, String logDateFmt, List<LicenseEventRow> out) {
        try {
            for (String line : Files.readAllLines(file, StandardCharsets.UTF_8)) {
                handleLine(line, logDateFmt, out);
            }
        } catch (IOException e) {
            log.debug("로그 파일 읽기 실패: {} ({})", file, e.getMessage());
        }
    }

    private void grepLicenseInZip(Path zipPath, String logDateFmt, List<LicenseEventRow> out) {
        try (ZipFile zf = new ZipFile(zipPath.toFile())) {
            Enumeration<? extends ZipEntry> entries = zf.entries();
            while (entries.hasMoreElements()) {
                ZipEntry e = entries.nextElement();
                if (e.isDirectory()) continue;
                try (java.io.BufferedReader br = new java.io.BufferedReader(
                        new java.io.InputStreamReader(zf.getInputStream(e), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = br.readLine()) != null) {
                        if (!line.toUpperCase(Locale.ROOT).contains("LICENSE")) continue;
                        handleLine(line, logDateFmt, out);
                    }
                }
            }
        } catch (IOException e) {
            log.debug("zip 읽기 실패: {} ({})", zipPath, e.getMessage());
        }
    }

    private void handleLine(String line, String logDateFmt, List<LicenseEventRow> out) {
        if (line == null) return;
        if (!line.toUpperCase(Locale.ROOT).contains("LICENSE")) return;
        for (String ex : EXCLUDE) {
            if (line.contains(ex)) return;
        }
        LicenseEventRow row = parseLine(line, logDateFmt);
        if (row != null) out.add(row);
    }

    /**
     * 한 라인 → LicenseEventRow. 시간 패턴이 없으면 null.
     * 원본 _parse_license_line 의 추출 패턴(시간/server_id/valid/event/desc) 그대로.
     */
    static LicenseEventRow parseLine(String line, String logDateFmt) {
        Matcher tm = TIME_BRACKET.matcher(line);
        if (!tm.find()) return null;
        String timeStr = tm.group(1).substring(0, 8); // HH:mm:ss (밀리초 제외)
        String ts = logDateFmt + " " + timeStr;

        Matcher sm = SERVER_ID.matcher(line);
        String serverId = sm.find() ? sm.group(1) : "";

        Matcher vm = VALID_KV.matcher(line);
        String validStr = vm.find() ? vm.group(1) : "";

        String result = "";
        if (!validStr.isEmpty()) {
            String upper = validStr.toUpperCase(Locale.ROOT);
            if (validStr.equals("1") || upper.equals("TRUE") || upper.equals("VALID")) {
                result = "VALID";
            } else if (validStr.equals("0") || upper.equals("FALSE") || upper.equals("INVALID")) {
                result = "INVALID";
            } else {
                result = upper;
            }
        }

        Matcher em = EVENT_BRACKET.matcher(line);
        String event = em.find() ? em.group(1).trim() : "LICENSE";

        Matcher dm = DESC_KV.matcher(line);
        String detail = dm.find() ? dm.group(1).trim() : "";
        if (detail.isEmpty()) {
            int lastBracket = line.lastIndexOf(']');
            if (lastBracket >= 0 && lastBracket < line.length() - 1) {
                detail = line.substring(lastBracket + 1).trim();
            }
        }

        String instance = serverId.isEmpty() ? "-" : serverId;
        return new LicenseEventRow(ts, instance, event, result, detail);
    }

    /** 오늘자 datetime — 테스트 hook(현재는 미사용, 정적). */
    @SuppressWarnings("unused")
    private LocalDateTime now() { return LocalDateTime.now(); }

    /** 결과 컨테이너(원본 (events, error) 튜플). */
    public static final class Result {
        public final List<LicenseEventRow> events;
        public final String error;
        public Result(List<LicenseEventRow> events, String error) {
            this.events = events;
            this.error = error;
        }
    }
}
