package com.exem.inspector.screen.alertsvc;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Alert Service XML 단순 파서 — 원본 {@code _parse_xml_simple()} 와 1:1 동등.
 *
 * <p>정식 XML 파서가 아닌 정규식 기반(원본 그대로). 다음을 추출한다:
 * <ul>
 *   <li>{@code <tag>value</tag>} 평면 태그</li>
 *   <li>{@code <tag attr="value" .../>} 속성</li>
 *   <li>다중 라인 블록(SMS_INSERT_QUERY/DATA/CONTENT/SUBJECT)</li>
 *   <li>bind 파라미터({@code <b0>}, {@code <b1>}, ...)</li>
 *   <li>header 파라미터({@code <h0>}, {@code <h1>}, ...)</li>
 *   <li>RAC Node</li>
 *   <li>{@code <sms_database_sid service="...">} 서비스 속성</li>
 * </ul>
 */
public final class AlertSvcXmlParser {

    private static final Pattern TAG_VALUE = Pattern.compile(
            "<([a-zA-Z_]\\w*)(?:\\s+[^>]*)?>([^<]*)</\\1>");

    private static final Pattern ATTRS = Pattern.compile(
            "<(\\w+)\\s+((?:\\w+=\"[^\"]*\"\\s*)+)/?>");

    private static final Pattern ATTR_KV = Pattern.compile("(\\w+)=\"([^\"]*)\"");

    private static final Pattern BIND  = Pattern.compile("<(b\\d+)>([^<]*)</\\1>");
    private static final Pattern HEAD  = Pattern.compile("<(h\\d+)>([^<]*)</\\1>");
    private static final Pattern NODE  = Pattern.compile("<Node>([^<]*)</Node>");
    private static final Pattern SMS_SVC = Pattern.compile(
            "<sms_database_sid\\s+service=\"(\\w+)\">");

    private static final String[] BLOCK_TAGS =
            { "SMS_INSERT_QUERY", "DATA", "CONTENT", "SUBJECT" };

    private AlertSvcXmlParser() {}

    /**
     * 파일을 읽어 파싱. 결과는 원본 dict 와 동일한 구조(키 보존). 파일 없음/오류 시 빈 결과.
     *
     * @return {@link Parsed} — config / binds / headers / raw / error 분리 보관.
     */
    public static Parsed parse(Path path) {
        Parsed result = new Parsed();
        if (path == null || !Files.exists(path)) {
            return result;
        }
        String content;
        try {
            content = new String(Files.readAllBytes(path), StandardCharsets.UTF_8);
        } catch (IOException e) {
            result.error = e.getMessage();
            return result;
        }
        result.raw = content;

        // 평면 태그 — 후속 추출이 같은 키에 덮어쓸 수 있도록 먼저 채운다(원본 순서).
        Matcher m = TAG_VALUE.matcher(content);
        while (m.find()) {
            result.config.put(m.group(1), m.group(2).trim());
        }

        // 자기-닫는 태그의 속성 — {tag}_attrs 키.
        m = ATTRS.matcher(content);
        while (m.find()) {
            String tag = m.group(1);
            Map<String, String> attrs = new LinkedHashMap<>();
            Matcher am = ATTR_KV.matcher(m.group(2));
            while (am.find()) {
                attrs.put(am.group(1), am.group(2));
            }
            if (!attrs.isEmpty()) {
                result.config.put(tag + "_attrs", attrs);
            }
        }

        // 다중 라인 블록 — DOTALL 로 줄 넘김 포함 캡처(원본 re.DOTALL 등가).
        for (String blockTag : BLOCK_TAGS) {
            Pattern blockP = Pattern.compile(
                    "<" + blockTag + ">(.*?)</" + blockTag + ">", Pattern.DOTALL);
            Matcher bm = blockP.matcher(content);
            if (bm.find()) {
                result.config.put(blockTag, bm.group(1).trim());
            }
        }

        // bind / header / RAC node / sms_database_sid 의 service 속성
        result.binds.putAll(collect(content, BIND));
        result.headers.putAll(collect(content, HEAD));
        Matcher nm = NODE.matcher(content);
        if (nm.find()) {
            result.config.put("rac_node", nm.group(1).trim());
        }
        Matcher sm = SMS_SVC.matcher(content);
        if (sm.find()) {
            result.config.put("sms_database_sid_service", sm.group(1));
        }
        return result;
    }

    private static Map<String, String> collect(String content, Pattern p) {
        Map<String, String> out = new LinkedHashMap<>();
        Matcher m = p.matcher(content);
        while (m.find()) {
            out.put(m.group(1), m.group(2).trim());
        }
        return out;
    }

    /** 파싱 결과 — 원본 dict 의 {@code _binds}/{@code _headers}/{@code _raw}/{@code _error} 를 필드 분리. */
    public static final class Parsed {
        /** 평면 태그/속성/블록 — 키 보존 순서. */
        public final Map<String, Object> config = new LinkedHashMap<>();
        public final Map<String, String> binds = new LinkedHashMap<>();
        public final Map<String, String> headers = new LinkedHashMap<>();
        public String raw = "";
        public String error;
    }
}
