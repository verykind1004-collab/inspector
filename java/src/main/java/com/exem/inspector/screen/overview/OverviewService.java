package com.exem.inspector.screen.overview;

import java.util.LinkedHashMap;
import java.util.Map;

import org.springframework.stereotype.Service;

/**
 * Overview 화면 데이터 조립 서비스.
 *
 * <p>원본 {@code pages/overview.py::page_overview / api_vitals} 와 등가:
 * 카드별 JSON 페이로드를 만든다(System / Vitals 우선 구현, Disk·Services 는 이후 단계).
 *
 * <p>상태 분류({@code _pct_status}) 도 원본 그대로:
 * CPU 60/80, Mem 80/90, Disk/Tablespace 80/90 (warn/crit).
 */
@Service
public class OverviewService {

    private final ProcReader procReader;
    private final HostInfo hostInfo;

    // 원본 _pct_status 의 임계값 (Python 코드값 그대로 백엔드 보존)
    static final int CPU_WARN = 60;
    static final int CPU_CRIT = 80;
    static final int MEM_WARN = 80;
    static final int MEM_CRIT = 90;

    public OverviewService(ProcReader procReader, HostInfo hostInfo) {
        this.procReader = procReader;
        this.hostInfo = hostInfo;
    }

    /** System 카드 정적 정보(원본 page_overview System 카드 부분). */
    public Map<String, Object> system() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("hostname", hostInfo.hostname());
        m.put("os",       hostInfo.osDisplay());
        m.put("uptime",   procReader.readUptime());
        m.put("cores",    procReader.readCpuCores());
        return m;
    }

    /** 폴링용 vitals — 원본 api_vitals 와 동일 구조. */
    public Map<String, Object> vitals() {
        ProcReader.CpuStat cpu = procReader.readCpuPercent();
        ProcReader.MemoryStat mem = procReader.readMemory();

        Map<String, Object> cpuMap = new LinkedHashMap<>();
        cpuMap.put("percent", cpu.getPercent());
        cpuMap.put("user",    cpu.getUser());
        cpuMap.put("system",  cpu.getSystem());
        cpuMap.put("iowait",  cpu.getIowait());
        cpuMap.put("status",  pctStatus(cpu.getPercent(), CPU_WARN, CPU_CRIT));

        Map<String, Object> memMap = new LinkedHashMap<>();
        memMap.put("percent",  mem.getPercent());
        memMap.put("total_gb", mem.getTotalGb());
        memMap.put("used_gb",  mem.getUsedGb());
        memMap.put("free_gb",  mem.getFreeGb());
        memMap.put("status",   pctStatus(mem.getPercent(), MEM_WARN, MEM_CRIT));

        Map<String, Object> root = new LinkedHashMap<>();
        root.put("cpu", cpuMap);
        root.put("mem", memMap);
        return root;
    }

    /** 원본 _pct_status 1:1. 임계 이상 critical, 경고 이상 warning, 그 외 ok. */
    static String pctStatus(double pct, int warn, int crit) {
        if (pct >= crit) return "critical";
        if (pct >= warn) return "warning";
        return "ok";
    }
}
