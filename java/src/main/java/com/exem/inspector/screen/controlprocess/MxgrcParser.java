package com.exem.inspector.screen.controlprocess;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/**
 * .mxgrc 파일 파서 — 원본 _parse_mxgrc 1:1 동등.
 *
 * <p>대상 키: DG_NAME, DG_XMS, DG_XMX, MXG_HOME, OS_TYPE, JAVA_HOME.
 * key=value 라인만 추출(주석/빈줄/export/alias/PATH 제외).
 */
public final class MxgrcParser {

    private static final Set<String> KEYS = new HashSet<>();
    static {
        Collections.addAll(KEYS, "DG_NAME", "DG_XMS", "DG_XMX", "MXG_HOME", "OS_TYPE", "JAVA_HOME");
    }

    private MxgrcParser() {}

    public static Map<String, String> parse(Path home) {
        Map<String, String> out = new HashMap<>();
        if (home == null) return out;
        Path mxgrc = home.resolve(".mxgrc");
        if (!Files.exists(mxgrc)) return out;
        try {
            for (String line : Files.readAllLines(mxgrc, StandardCharsets.UTF_8)) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) continue;
                if (line.startsWith("export") || line.startsWith("alias") || line.startsWith("PATH")) continue;
                int eq = line.indexOf('=');
                if (eq < 0) continue;
                String key = line.substring(0, eq).trim();
                if (!KEYS.contains(key)) continue;
                String val = line.substring(eq + 1).trim();
                if (val.length() >= 2) {
                    char c0 = val.charAt(0), cN = val.charAt(val.length() - 1);
                    if ((c0 == '"' && cN == '"') || (c0 == '\'' && cN == '\'')) {
                        val = val.substring(1, val.length() - 1);
                    }
                }
                out.put(key, val);
            }
        } catch (IOException ignore) { /* best-effort */ }
        return out;
    }
}
