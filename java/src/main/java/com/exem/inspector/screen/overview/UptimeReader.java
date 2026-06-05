package com.exem.inspector.screen.overview;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

import org.springframework.stereotype.Component;

/**
 * 프로세스 elapsed time 조회 — 원본 system_utils._proc_uptime 1:1.
 *
 * <p>{@code ps -p PID -o etime=} 호출 후 "DD-HH:MM:SS" / "HH:MM:SS" / "MM:SS" 포맷 파싱.
 * 결과를 "Nd Nh Nm Ns" 형식으로 변환(d/h/m 은 0 일 때 생략).
 * PID 가 없거나 ps 실패 시 "-" 반환.
 */
@Component
public class UptimeReader {

    /** 원본 _proc_uptime 의 표시 문자열 반환. */
    public String readUptime(String pid) {
        if (pid == null || pid.isEmpty() || "-".equals(pid)) return "-";
        String etime = runEtime(pid);
        if (etime == null || etime.isEmpty()) return "-";
        return formatEtime(etime);
    }

    /** 원본 동일 파서. visible for tests. */
    static String formatEtime(String raw) {
        String t = raw.trim();
        if (t.isEmpty()) return "-";
        try {
            String[] parts = t.replace('-', ':').split(":");
            long[] nums = new long[parts.length];
            for (int i = 0; i < parts.length; i++) nums[i] = Long.parseLong(parts[i]);
            long total;
            switch (nums.length) {
                case 2:  total = nums[0] * 60 + nums[1]; break;
                case 3:  total = nums[0] * 3600 + nums[1] * 60 + nums[2]; break;
                case 4:  total = nums[0] * 86400 + nums[1] * 3600 + nums[2] * 60 + nums[3]; break;
                default: return "-";
            }
            long d = total / 86400; long r = total % 86400;
            long h = r / 3600;       r = r % 3600;
            long m = r / 60;         long s = r % 60;
            StringBuilder sb = new StringBuilder();
            if (d > 0) sb.append(d).append("d ");
            if (h > 0) sb.append(h).append("h ");
            if (m > 0) sb.append(m).append("m ");
            sb.append(s).append('s');
            return sb.toString();
        } catch (NumberFormatException e) {
            return "-";
        }
    }

    private String runEtime(String pid) {
        try {
            ProcessBuilder pb = new ProcessBuilder("ps", "-p", pid, "-o", "etime=").redirectErrorStream(true);
            Process p = pb.start();
            StringBuilder sb = new StringBuilder();
            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = br.readLine()) != null) sb.append(line).append('\n');
            }
            if (!p.waitFor(1, TimeUnit.SECONDS)) {
                p.destroyForcibly();
                return null;
            }
            return sb.toString();
        } catch (Exception e) {
            return null;
        }
    }
}
