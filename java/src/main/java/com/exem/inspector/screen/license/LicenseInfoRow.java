package com.exem.inspector.screen.license;

/**
 * License Info 카드 한 행 — apm_license + apm_license_db_info 조인 결과 + 파일명 파싱.
 *
 * <p>원본 {@code _get_license_info()} 의 dict 와 1:1 동등.
 */
public class LicenseInfoRow {

    private final String id;
    private final String name;
    private final String modified;
    private final String expiry;     // YYYY-MM-DD 또는 null
    private final String product;    // MFO / MXG / MAXGAUGE 또는 null
    private final Integer dDay;      // expiry - today (TERM=null)
    private final boolean perpetual; // TERM = true
    private final String licenseType; // TRIAL or TERM

    public LicenseInfoRow(String id, String name, String modified, String expiry,
                          String product, Integer dDay, boolean perpetual, String licenseType) {
        this.id = id;
        this.name = name;
        this.modified = modified;
        this.expiry = expiry;
        this.product = product;
        this.dDay = dDay;
        this.perpetual = perpetual;
        this.licenseType = licenseType;
    }

    public String getId() { return id; }
    public String getName() { return name; }
    public String getModified() { return modified; }
    public String getExpiry() { return expiry; }
    public String getProduct() { return product; }
    public Integer getDDay() { return dDay; }
    public boolean isPerpetual() { return perpetual; }
    public String getLicenseType() { return licenseType; }
}
