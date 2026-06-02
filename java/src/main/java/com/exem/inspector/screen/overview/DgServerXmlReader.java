package com.exem.inspector.screen.overview;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.springframework.stereotype.Component;

/**
 * DGServer.xml 파서 — 단일 태그 값 추출.
 *
 * <p>원본 system_utils._xml_val 와 동등. DGServer.xml 은 단순 구조라 정규식 1줄 파서면 충분.
 * 누락/미존재 시 빈 문자열.
 */
@Component
public class DgServerXmlReader {

    /** 예: tag="gather_port" → {@code <gather_port>5050</gather_port>} 의 5050. */
    public String readTagValue(Path xmlFile, String tag) {
        if (xmlFile == null || !Files.isRegularFile(xmlFile)) {
            return "";
        }
        String content;
        try {
            content = new String(Files.readAllBytes(xmlFile), StandardCharsets.UTF_8);
        } catch (IOException e) {
            return "";
        }
        // <tag>VALUE</tag> 매칭. 화이트스페이스 허용. 첫 번째 일치만 사용.
        Pattern p = Pattern.compile("<" + Pattern.quote(tag) + ">\\s*([^<]*)\\s*</" + Pattern.quote(tag) + ">");
        Matcher m = p.matcher(content);
        if (m.find()) {
            return m.group(1).trim();
        }
        return "";
    }
}
