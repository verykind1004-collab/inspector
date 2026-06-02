package com.exem.inspector.screen.license;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.apache.ibatis.annotations.Mapper;

/**
 * License Check 의 두 SQL — Oracle/PG databaseId 분기는 XML 에서 처리.
 *
 * <p>표 응답을 LinkedHashMap 으로 받아 원본 _parse_db_table 의 헤더-값 매핑과 동등.
 */
@Mapper
public interface LicenseMapper {

    /** apm_license + apm_license_db_info → license 파일 라인 표. */
    List<LinkedHashMap<String, Object>> findLicenseInfo();

    /** apm_db_info + apm_license_db_info LEFT JOIN → 인스턴스별 라이선스 상태. */
    List<LinkedHashMap<String, Object>> findInstanceLicenseStatus();
}
