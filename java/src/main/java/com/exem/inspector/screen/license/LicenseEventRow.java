package com.exem.inspector.screen.license;

/**
 * Recent License Events 한 행 — DGM 로그/zip 의 LICENSE 라인 파싱.
 *
 * <p>원본 {@code _parse_license_line()} 의 dict 와 1:1 동등.
 */
public class LicenseEventRow {

    private final String ts;         // YYYY-MM-DD HH:mm:ss
    private final String instance;   // server_id 또는 "-"
    private final String event;      // 이벤트 라벨(예: LICENSE / Key Reloaded)
    private final String result;     // VALID / INVALID / 또는 빈 값
    private final String desc;       // 상세

    public LicenseEventRow(String ts, String instance, String event, String result, String desc) {
        this.ts = ts;
        this.instance = instance;
        this.event = event;
        this.result = result;
        this.desc = desc;
    }

    public String getTs() { return ts; }
    public String getInstance() { return instance; }
    public String getEvent() { return event; }
    public String getResult() { return result; }
    public String getDesc() { return desc; }
}
