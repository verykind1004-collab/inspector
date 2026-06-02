package com.exem.inspector.screen.license;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

import com.exem.inspector.common.db.DbType;
import com.exem.inspector.common.web.screen.ColumnDef;
import com.exem.inspector.common.web.screen.ColumnRole;
import com.exem.inspector.common.web.screen.ColumnType;
import com.exem.inspector.common.web.screen.ScreenResponse;
import com.exem.inspector.config.ServiceConfig;

/**
 * License Check 화면의 통합 서비스 — 원본 page_license_check() 의 3 카드 데이터 조립.
 */
@Service
public class LicenseService {

    private static final Logger log = LoggerFactory.getLogger(LicenseService.class);

    private static final DateTimeFormatter YYYYMMDD = DateTimeFormatter.ofPattern("yyyyMMdd");

    /** 파일명에서 제품명 추출 대상 — 원본 ('MFO','MXG','MAXGAUGE'). */
    private static final List<String> PRODUCTS = Arrays.asList("MFO", "MXG", "MAXGAUGE");

    private final ObjectProvider<LicenseMapper> mapperProvider;
    private final ServiceConfig serviceConfig;
    private final LicenseEventReader eventReader;

    public LicenseService(ObjectProvider<LicenseMapper> mapperProvider,
                          ServiceConfig serviceConfig,
                          LicenseEventReader eventReader) {
        this.mapperProvider = mapperProvider;
        this.serviceConfig = serviceConfig;
        this.eventReader = eventReader;
    }

    public LicenseCheckResult build() {
        DbType dbType = DbType.fromConfigValue(serviceConfig.repository().dbType());
        LicenseMapper mapper = mapperProvider.getIfAvailable();

        // ── License Info ─────────────────────────────────────────────────
        List<LicenseInfoRow> infoRows = null;
        String infoErr = null;
        if (mapper == null) {
            infoErr = "리포지토리가 설정되지 않았습니다(service_config.json 확인).";
        } else {
            try {
                List<LinkedHashMap<String, Object>> raw = mapper.findLicenseInfo();
                if (raw == null || raw.isEmpty()) {
                    infoErr = "No license registered";
                } else {
                    infoRows = new ArrayList<>(raw.size());
                    for (LinkedHashMap<String, Object> r : raw) {
                        infoRows.add(mapLicenseInfoRow(r));
                    }
                }
            } catch (RuntimeException e) {
                log.warn("License Info 조회 실패", e);
                infoErr = e.getMessage();
            }
        }

        // ── Instance License Status ──────────────────────────────────────
        ScreenResponse instances = null;
        String instancesErr = null;
        if (mapper == null) {
            instancesErr = "리포지토리가 설정되지 않았습니다(service_config.json 확인).";
        } else {
            try {
                List<LinkedHashMap<String, Object>> rows = mapper.findInstanceLicenseStatus();
                instances = buildInstanceScreen(rows == null ? Collections.emptyList() : rows, dbType);
            } catch (RuntimeException e) {
                log.warn("Instance License Status 조회 실패", e);
                instancesErr = e.getMessage();
            }
        }

        // ── Recent License Events ────────────────────────────────────────
        LicenseEventReader.Result evt = eventReader.read();
        return new LicenseCheckResult(
                infoRows, infoErr,
                instances, instancesErr,
                evt.events, evt.error);
    }

    // ── 파일명 파싱 ─────────────────────────────────────────────────────────

    /**
     * 원본 dict → LicenseInfoRow.
     *
     * <p>파일명을 '.' 으로 split → 8자리 숫자(=YYYYMMDD)면 expiry, MFO/MXG/MAXGAUGE 면 product.
     * expiry 있으면 TRIAL(d_day 계산), 없으면 TERM(영구 = d_day null).
     */
    LicenseInfoRow mapLicenseInfoRow(LinkedHashMap<String, Object> r) {
        String licId = str(r.get("license_id"));
        String name = str(r.get("license_name"));
        String modified = str(r.get("modified"));

        LocalDate expiry = null;
        String product = null;
        for (String p : name.split("\\.")) {
            if (p.length() == 8 && isAllDigits(p) && expiry == null) {
                try {
                    expiry = LocalDate.parse(p, YYYYMMDD);
                } catch (DateTimeParseException ignore) {
                    // 무효 날짜는 무시(원본 동일).
                }
            }
            String pu = p.toUpperCase();
            if (PRODUCTS.contains(pu)) {
                product = pu;
            }
        }
        String licenseType = expiry != null ? "TRIAL" : "TERM";
        boolean perpetual = "TERM".equals(licenseType);
        Integer dDay = perpetual ? null : (int) ChronoUnit.DAYS.between(LocalDate.now(), expiry);
        String expiryStr = expiry == null ? null : expiry.toString();
        return new LicenseInfoRow(licId, name, modified, expiryStr, product, dDay, perpetual, licenseType);
    }

    private static boolean isAllDigits(String s) {
        for (int i = 0; i < s.length(); i++) {
            if (!Character.isDigit(s.charAt(i))) return false;
        }
        return true;
    }

    private static String str(Object o) {
        return o == null ? "" : String.valueOf(o).trim();
    }

    // ── Instance Screen ────────────────────────────────────────────────────

    /**
     * apm_db_info + apm_license_db_info LEFT JOIN 결과 → ScreenResponse(2층 ScreenTable 소비).
     * STATUS 컬럼은 valid/license_status 가 분리돼 있어 별도로 PLAIN 으로 표시(원본도 두 컬럼 표시).
     */
    private ScreenResponse buildInstanceScreen(List<LinkedHashMap<String, Object>> rows, DbType dbType) {
        ScreenResponse.Builder b = ScreenResponse.builder(
                "license_check_instances", "Instance License Status", dbType.name());
        b.column(ColumnDef.of("db_id", "DB ID", ColumnType.NUMBER, ColumnRole.ID));
        b.column(ColumnDef.of("instance_name", "Instance Name", ColumnType.STRING, ColumnRole.INSTANCE));
        b.column(ColumnDef.of("host_ip", "Host IP", ColumnType.STRING, ColumnRole.PLAIN));
        b.column(ColumnDef.of("port", "Port", ColumnType.STRING, ColumnRole.PLAIN));
        b.column(ColumnDef.of("valid", "Valid", ColumnType.STRING, ColumnRole.PLAIN));
        b.column(ColumnDef.of("license_type", "License Type", ColumnType.STRING, ColumnRole.PLAIN));
        b.column(ColumnDef.of("license_status", "License Status", ColumnType.STRING, ColumnRole.PLAIN));
        b.column(ColumnDef.of("core", "Core", ColumnType.STRING, ColumnRole.PLAIN));
        b.column(ColumnDef.of("last_check", "Last Check", ColumnType.DATETIME, ColumnRole.PLAIN));
        for (LinkedHashMap<String, Object> r : rows) {
            b.rowFromMap(r);
        }
        return b.build();
    }
}
