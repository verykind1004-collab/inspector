package com.exem.inspector.screen.overview;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

/**
 * Linux {@code /proc} 파일 시스템 파서.
 *
 * <p>기존 Python {@code system_utils.py} 의 {@code _cpu_percent / _memory /
 * _uptime / _cpu_cores} 와 1:1 대응. 모든 메소드는 IO 예외 시 안전한 폴백
 * 값을 반환한다(원본 except: 폴백 동작 보존).
 *
 * <p>비-Linux 환경(테스트 PC 등) 에선 /proc 미존재 → 폴백 값. 운영 서버는 항상 Linux.
 */
@Component
public class ProcReader {

    private static final Path PROC_STAT     = Paths.get("/proc/stat");
    private static final Path PROC_MEMINFO  = Paths.get("/proc/meminfo");
    private static final Path PROC_UPTIME   = Paths.get("/proc/uptime");
    private static final Path PROC_CPUINFO  = Paths.get("/proc/cpuinfo");

    /**
     * CPU 사용률 측정. 300ms 간격으로 /proc/stat 두 번 읽고 차분 계산.
     *
     * <p>원본 _cpu_percent 와 동일 — total = 1 - idle_diff/total_diff,
     * user/system/iowait 는 각 컬럼 차분 비율.
     */
    public CpuStat readCpuPercent() {
        try {
            long[] v1 = readStatCounters(PROC_STAT);
            try { Thread.sleep(300L); } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            long[] v2 = readStatCounters(PROC_STAT);
            long dt = sum(v2) - sum(v1);
            if (dt == 0L) {
                return new CpuStat(0.0, 0.0, 0.0, 0.0);
            }
            double total = round1((1.0 - (v2[3] - v1[3]) / (double) dt) * 100.0);
            return new CpuStat(
                    total,
                    round1((v2[0] - v1[0]) / (double) dt * 100.0),  // user
                    round1((v2[2] - v1[2]) / (double) dt * 100.0),  // system
                    round1((v2[4] - v1[4]) / (double) dt * 100.0)); // iowait
        } catch (IOException e) {
            return new CpuStat(0.0, 0.0, 0.0, 0.0);
        }
    }

    /** /proc/meminfo 파싱. KB 단위 값을 GB 로 환산(원본 _memory). */
    public MemoryStat readMemory() {
        try {
            Map<String, Long> info = readMeminfo(PROC_MEMINFO);
            long total = info.getOrDefault("MemTotal", 0L);
            long free  = info.getOrDefault("MemFree", 0L);
            long buff  = info.getOrDefault("Buffers", 0L);
            long cached = info.getOrDefault("Cached", 0L);
            if (total == 0L) {
                return new MemoryStat(0.0, 0.0, 0.0, 0.0);
            }
            long used = total - free - buff - cached;
            long freeNet = total - used;
            double pct = round1(used / (double) total * 100.0);
            return new MemoryStat(round1(toGb(total)), round1(toGb(used)),
                    round1(toGb(freeNet)), pct);
        } catch (IOException e) {
            return new MemoryStat(0.0, 0.0, 0.0, 0.0);
        }
    }

    /**
     * /proc/uptime 초 단위 → "Xd Yh Zm Ws" 포맷(원본 _uptime).
     * 0 인 단위는 생략, 초는 항상 표시.
     */
    public String readUptime() {
        try {
            String first = new String(Files.readAllBytes(PROC_UPTIME), StandardCharsets.UTF_8)
                    .trim().split("\\s+")[0];
            long sec = (long) Double.parseDouble(first);
            long d = sec / 86400L; sec -= d * 86400L;
            long h = sec / 3600L;  sec -= h * 3600L;
            long m = sec / 60L;    sec -= m * 60L;
            StringBuilder sb = new StringBuilder();
            if (d > 0L) sb.append(d).append("d ");
            if (h > 0L) sb.append(h).append("h ");
            if (m > 0L) sb.append(m).append("m ");
            sb.append(sec).append("s");
            return sb.toString();
        } catch (IOException | NumberFormatException e) {
            return "-";
        }
    }

    /** /proc/cpuinfo 의 "processor" 라인 수 (원본 _cpu_cores). */
    public int readCpuCores() {
        try {
            int count = 0;
            for (String line : Files.readAllLines(PROC_CPUINFO, StandardCharsets.UTF_8)) {
                if (line.startsWith("processor")) count++;
            }
            return count;
        } catch (IOException e) {
            return 0;
        }
    }

    // ---- 내부 유틸 ----

    long[] readStatCounters(Path statPath) throws IOException {
        // 첫 줄: "cpu  user nice system idle iowait irq softirq steal guest ..."
        String first;
        try (java.io.BufferedReader r = Files.newBufferedReader(statPath, StandardCharsets.UTF_8)) {
            first = r.readLine();
        }
        if (first == null) {
            throw new IOException("empty /proc/stat");
        }
        String[] parts = first.trim().split("\\s+");
        // index 0 = "cpu", 1..N = counters
        List<Long> nums = new ArrayList<>();
        for (int i = 1; i < parts.length; i++) {
            try {
                nums.add(Long.parseLong(parts[i]));
            } catch (NumberFormatException ignore) {
                // skip non-numeric token
            }
        }
        long[] arr = new long[nums.size()];
        for (int i = 0; i < arr.length; i++) arr[i] = nums.get(i);
        return arr;
    }

    Map<String, Long> readMeminfo(Path memPath) throws IOException {
        Map<String, Long> out = new HashMap<>();
        for (String line : Files.readAllLines(memPath, StandardCharsets.UTF_8)) {
            int colon = line.indexOf(':');
            if (colon < 0) continue;
            String key = line.substring(0, colon).trim();
            String rest = line.substring(colon + 1).trim();
            String[] tok = rest.split("\\s+");
            try {
                out.put(key, Long.parseLong(tok[0]));
            } catch (NumberFormatException ignore) {
                // skip
            }
        }
        return out;
    }

    private static long sum(long[] a) {
        long s = 0L;
        for (long v : a) s += v;
        return s;
    }

    private static double toGb(long kb) {
        return kb / 1048576.0;
    }

    private static double round1(double v) {
        return Math.round(v * 10.0) / 10.0;
    }

    // ---- 값 객체 ----

    /** CPU 사용률 (퍼센트, 1자리 소수). */
    public static final class CpuStat {
        private final double percent;
        private final double user;
        private final double system;
        private final double iowait;

        public CpuStat(double percent, double user, double system, double iowait) {
            this.percent = percent; this.user = user; this.system = system; this.iowait = iowait;
        }
        public double getPercent() { return percent; }
        public double getUser()    { return user; }
        public double getSystem()  { return system; }
        public double getIowait()  { return iowait; }
    }

    /** 메모리 사용량 (GB · 1자리 소수). */
    public static final class MemoryStat {
        private final double totalGb;
        private final double usedGb;
        private final double freeGb;
        private final double percent;

        public MemoryStat(double totalGb, double usedGb, double freeGb, double percent) {
            this.totalGb = totalGb; this.usedGb = usedGb; this.freeGb = freeGb; this.percent = percent;
        }
        public double getTotalGb() { return totalGb; }
        public double getUsedGb()  { return usedGb; }
        public double getFreeGb()  { return freeGb; }
        public double getPercent() { return percent; }
    }
}
