package com.exem.inspector.screen.license;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;

import org.junit.jupiter.api.Test;

import com.exem.inspector.config.ServiceConfig;

class LicenseServiceTest {

    private LicenseService svc() {
        // 파일명 파싱은 매퍼/이벤트 의존 없이 단위 테스트 가능 — mock 만 채워둠.
        return new LicenseService(null, mock(ServiceConfig.class), mock(LicenseEventReader.class));
    }

    private LinkedHashMap<String, Object> row(String licId, String name, String modified) {
        LinkedHashMap<String, Object> m = new LinkedHashMap<>();
        m.put("license_id", licId);
        m.put("license_name", name);
        m.put("modified", modified);
        m.put("license_type", "-");
        return m;
    }

    @Test
    void 파일명에_YYYYMMDD가_있으면_TRIAL_그리고_dDay_계산() {
        // 30일 후 만료
        String future = LocalDate.now().plusDays(30).format(DateTimeFormatter.ofPattern("yyyyMMdd"));
        LicenseInfoRow r = svc().mapLicenseInfoRow(row("1", "MFO.client.20260801." + future + ".lic", "2026-06-01"));
        // 위 라인의 .20260801. 와 future 둘 다 8자리지만 mapLicenseInfoRow 는 첫 매치만 expiry 로 사용(원본 동일).
        assertThat(r.getLicenseType()).isEqualTo("TRIAL");
        assertThat(r.isPerpetual()).isFalse();
        assertThat(r.getExpiry()).isNotNull();
        assertThat(r.getDDay()).isNotNull();
    }

    @Test
    void 날짜가_없으면_TERM_영구() {
        LicenseInfoRow r = svc().mapLicenseInfoRow(row("1", "MXG.client.PROD.lic", "2026-06-01"));
        assertThat(r.getLicenseType()).isEqualTo("TERM");
        assertThat(r.isPerpetual()).isTrue();
        assertThat(r.getExpiry()).isNull();
        assertThat(r.getDDay()).isNull();
        assertThat(r.getProduct()).isEqualTo("MXG");
    }

    @Test
    void product_MFO_MXG_MAXGAUGE_대소문자_무관_추출() {
        assertThat(svc().mapLicenseInfoRow(row("1", "mfo.x.lic", "x")).getProduct()).isEqualTo("MFO");
        assertThat(svc().mapLicenseInfoRow(row("1", "MaxGauge.x.lic", "x")).getProduct()).isEqualTo("MAXGAUGE");
    }

    @Test
    void 무효_8자리_숫자는_무시되어_TERM() {
        // 99999999는 유효한 날짜 아님 → expiry null → TERM
        LicenseInfoRow r = svc().mapLicenseInfoRow(row("1", "MFO.99999999.lic", "x"));
        assertThat(r.getLicenseType()).isEqualTo("TERM");
    }
}
