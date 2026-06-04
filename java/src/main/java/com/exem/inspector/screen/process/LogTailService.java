package com.exem.inspector.screen.process;

import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

/**
 * 로그 파일 tail/seek 서비스 — 원본 process.py::api_log_tail 1:1 포팅.
 *
 * <p>{@code offset == 0}: 마지막 N 라인 + 파일 크기.
 * {@code offset > 0}: 해당 위치부터 추가 라인 + 새 offset.
 * 파일이 줄어들었다면(rotate 등) offset 을 0 으로 reset 하여 재시작.
 *
 * <p>안전성: 화이트리스트 prefix 하위 경로만 허용(arbitrary file read 방지).
 */
@Service
public class LogTailService {

    private static final Logger log = LoggerFactory.getLogger(LogTailService.class);

    /** offset == 0 호출 시 가져올 라인 수(원본: tail -n 300). */
    static final int TAIL_LINES = 300;

    private final List<Path> allowedRoots;

    public LogTailService(@Value("${inspector.log-tail.allowed-roots:/home/inspector,/var/log}") String roots) {
        List<Path> list = new ArrayList<>();
        for (String r : roots.split(",")) {
            String t = r.trim();
            if (!t.isEmpty()) list.add(Paths.get(t).toAbsolutePath().normalize());
        }
        this.allowedRoots = Collections.unmodifiableList(list);
    }

    public LogTailResult read(String pathStr, long offset) {
        if (pathStr == null || pathStr.isEmpty()) {
            return LogTailResult.error("file not found");
        }
        Path path;
        try {
            path = Paths.get(pathStr).toAbsolutePath().normalize();
        } catch (RuntimeException e) {
            return LogTailResult.error("invalid path");
        }
        if (!isUnderAllowedRoot(path)) {
            return LogTailResult.error("forbidden path");
        }
        if (!Files.exists(path) || !Files.isRegularFile(path)) {
            return LogTailResult.error("file not found");
        }
        long fsize;
        try {
            fsize = Files.size(path);
        } catch (IOException e) {
            return LogTailResult.error(e.getMessage());
        }

        if (offset <= 0L) {
            try {
                return LogTailResult.ok(readTailLines(path, TAIL_LINES), fsize);
            } catch (IOException e) {
                return LogTailResult.error(e.getMessage());
            }
        }
        // rotate / truncate 감지: file 이 더 작아졌으면 처음부터 다시.
        long startOffset = offset > fsize ? 0L : offset;
        try {
            return readFrom(path, startOffset);
        } catch (IOException e) {
            return LogTailResult.error(e.getMessage());
        }
    }

    private boolean isUnderAllowedRoot(Path path) {
        if (allowedRoots.isEmpty()) return true;
        for (Path root : allowedRoots) {
            if (path.startsWith(root)) return true;
        }
        return false;
    }

    /** 파일 끝에서부터 줄 단위로 N 라인 추출(원본 {@code tail -n N}).
     *  알고리즘: 파일 끝에서 역방향 스캔하며 {@code N} 번째 newline 을 찾는다.
     *  찾으면 그 다음 byte 위치가 마지막 N 라인의 시작점.
     *  N 보다 줄이 적으면 pos == 0 (전체 파일). */
    static List<String> readTailLines(Path file, int n) throws IOException {
        if (n <= 0) return Collections.emptyList();
        try (RandomAccessFile raf = new RandomAccessFile(file.toFile(), "r")) {
            long size = raf.length();
            if (size <= 0L) return Collections.emptyList();
            long pos = size;
            int linesFound = 0;
            while (pos > 0L && linesFound < n) {
                pos--;
                raf.seek(pos);
                int b = raf.read();
                if (b == '\n') {
                    // 파일 끝의 trailing newline 은 줄 구분이 아니라 종료 표시 — skip.
                    if (pos == size - 1L) continue;
                    linesFound++;
                }
            }
            // n 번째 newline 을 찾았으면 그 다음 byte 가 마지막 N 라인의 시작.
            // n 보다 줄이 적어 pos == 0 까지 도달한 경우는 그대로 0(파일 처음부터).
            if (linesFound >= n) pos++;
            raf.seek(pos);
            byte[] buf = new byte[(int) Math.max(0L, size - pos)];
            raf.readFully(buf);
            String chunk = new String(buf, StandardCharsets.UTF_8);
            return splitLines(chunk);
        }
    }

    private LogTailResult readFrom(Path file, long offset) throws IOException {
        try (RandomAccessFile raf = new RandomAccessFile(file.toFile(), "r")) {
            raf.seek(offset);
            long size = raf.length();
            int remaining = (int) Math.min(Integer.MAX_VALUE, size - offset);
            if (remaining <= 0) return LogTailResult.ok(Collections.<String>emptyList(), size);
            byte[] buf = new byte[remaining];
            raf.readFully(buf);
            long newOffset = raf.getFilePointer();
            String chunk = new String(buf, StandardCharsets.UTF_8);
            List<String> lines = chunk.trim().isEmpty() ? Collections.<String>emptyList() : splitLines(chunk);
            return LogTailResult.ok(lines, newOffset);
        }
    }

    /** {@code str.splitlines()} 동등. trailing newline 은 빈 라인 만들지 않음. */
    static List<String> splitLines(String s) {
        if (s == null || s.isEmpty()) return Collections.emptyList();
        // 마지막 \n 은 빈 라인을 만들지 않음 — Python splitlines 의 동작.
        String trimmed = s.endsWith("\n") ? s.substring(0, s.length() - 1) : s;
        if (trimmed.isEmpty()) return Collections.emptyList();
        return new ArrayList<>(Arrays.asList(trimmed.split("\\R", -1)));
    }

    /** 미사용 import 경고 회피용 더미(향후 작업 시 사용 가능). */
    @SuppressWarnings("unused")
    private static void _unused() { log.trace("log-tail bootstrap"); }
}
