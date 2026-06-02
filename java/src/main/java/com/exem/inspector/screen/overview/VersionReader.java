package com.exem.inspector.screen.overview;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import org.springframework.stereotype.Component;

/**
 * 컴포넌트 버전 파일 읽기(원본 _get_dg_version / _get_pjs_version / _get_client_version 등가).
 *
 * <p>각 home/version 또는 home/VERSION 파일 첫 줄 trim. 없으면 "-" 반환.
 */
@Component
public class VersionReader {

    public String readVersion(Path home) {
        if (home == null) return "-";
        // version, VERSION, dgsv.ver, PlatformJS.ver 등 다양 — 우선순위로 시도
        String[] candidates = {"version", "VERSION", "dgsv.ver", "PlatformJS.ver"};
        for (String name : candidates) {
            Path p = home.resolve(name);
            if (Files.isRegularFile(p)) {
                try {
                    String s = new String(Files.readAllBytes(p), StandardCharsets.UTF_8).trim();
                    if (!s.isEmpty()) {
                        // 다중 라인이면 첫 줄
                        int nl = s.indexOf('\n');
                        return nl >= 0 ? s.substring(0, nl).trim() : s;
                    }
                } catch (IOException ignore) {
                    // 다음 후보 시도
                }
            }
        }
        return "-";
    }
}
