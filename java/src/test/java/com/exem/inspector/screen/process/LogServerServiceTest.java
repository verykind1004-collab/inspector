package com.exem.inspector.screen.process;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import com.exem.inspector.config.LogPathsBlock;
import com.exem.inspector.config.ServiceConfig;

/**
 * LogServerService 단위 테스트 — 원본 _gather_log_server_html 핵심 동작 1:1 검증.
 */
class LogServerServiceTest {

    private final ServiceConfig serviceConfig = mock(ServiceConfig.class);
    private final LogServerService service = new LogServerService(serviceConfig);

    private void wireLogPaths(String dgmDir, List<String> dgsDirs) {
        LogPathsBlock lp = mock(LogPathsBlock.class);
        given(lp.dgserverM()).willReturn(dgmDir == null ? "" : dgmDir);
        given(lp.dgserverS()).willReturn(dgsDirs);
        given(serviceConfig.logPaths()).willReturn(lp);
    }

    // ── 탭 빌드 ───────────────────────────────────────────────────
    @Test
    void noLogPaths_configError() {
        wireLogPaths("", Collections.<String>emptyList());
        LogServerPayload p = service.build("dgm", null, null, null, null);
        assertThat(p.getTabs()).isEmpty();
        assertThat(p.getConfigError()).contains("설정되지 않았습니다");
    }

    @Test
    void tabs_dgmAndDgsList(@TempDir Path tmp) throws IOException {
        Path d = tmp.resolve("dgm"); Files.createDirectories(d);
        Path s1 = tmp.resolve("s1"); Files.createDirectories(s1);
        wireLogPaths(d.toString(), Arrays.asList(s1.toString()));

        LogServerPayload p = service.build("dgm", null, null, null, null);
        assertThat(p.getTabs()).extracting(LogServerPayload.Tab::getId)
                .containsExactly("dgm", "dgs1");
        assertThat(p.getCurrentTab().getTabId()).isEqualTo("dgm");
    }

    @Test
    void unknownTabId_fallsBackToFirst(@TempDir Path tmp) throws IOException {
        Path d = tmp.resolve("dgm"); Files.createDirectories(d);
        wireLogPaths(d.toString(), Collections.<String>emptyList());
        LogServerPayload p = service.build("bogus", null, null, null, null);
        assertThat(p.getCurrentTab().getTabId()).isEqualTo("dgm");
    }

    // ── 파일 그룹 분류 ────────────────────────────────────────────
    @Test
    void groupOf_classifies() {
        assertThat(LogServerService.groupOf("DGM_18800.log")).isEqualTo("DG");
        assertThat(LogServerService.groupOf("DGS_19001.log")).isEqualTo("DG");
        assertThat(LogServerService.groupOf("maxgauge/obsd1.log")).isEqualTo("OBSD");
        assertThat(LogServerService.groupOf("system.log")).isEqualTo("Other");
    }

    @Test
    void scanFiles_includesMaxgaugeSubdir(@TempDir Path tmp) throws IOException {
        Path d = tmp.resolve("dgm"); Files.createDirectories(d);
        Files.write(d.resolve("DGM_18800.log"), "x".getBytes());
        Path mg = d.resolve("maxgauge"); Files.createDirectories(mg);
        Files.write(mg.resolve("obsd1.log"), "y".getBytes());
        wireLogPaths(d.toString(), Collections.<String>emptyList());

        LogServerPayload p = service.build("dgm", null, null, null, null);
        List<String> names = p.getCurrentTab().getFiles().stream()
                .map(LogServerPayload.File::getName)
                .collect(java.util.stream.Collectors.toList());
        assertThat(names).contains("DGM_18800.log", "maxgauge/obsd1.log");
    }

    // ── 본문 읽기 ────────────────────────────────────────────────
    @Test
    void noFilter_returnsLastTail(@TempDir Path tmp) throws IOException {
        Path d = tmp.resolve("dgm"); Files.createDirectories(d);
        StringBuilder sb = new StringBuilder();
        for (int i = 1; i <= 1500; i++) sb.append("line").append(i).append('\n');
        Files.write(d.resolve("DGM_X.log"), sb.toString().getBytes());
        wireLogPaths(d.toString(), Collections.<String>emptyList());

        LogServerPayload p = service.build("dgm", "DGM_X.log", null, null, null);
        assertThat(p.getContent().getFilterLabel()).isEqualTo("Latest 1,000 lines");
        assertThat(p.getContent().getLines()).hasSize(1000);
        assertThat(p.getContent().getLines().get(0)).isEqualTo("line501");
        assertThat(p.getContent().getTotalMatch()).isNull();
        assertThat(p.getContent().isTruncated()).isFalse();
    }

    @Test
    void searchFilter_caseInsensitive_500cap(@TempDir Path tmp) throws IOException {
        Path d = tmp.resolve("dgm"); Files.createDirectories(d);
        StringBuilder sb = new StringBuilder();
        for (int i = 1; i <= 700; i++) sb.append("[ERROR] entry ").append(i).append('\n');
        sb.append("nothing matters\n");
        Files.write(d.resolve("DGM_X.log"), sb.toString().getBytes());
        wireLogPaths(d.toString(), Collections.<String>emptyList());

        LogServerPayload p = service.build("dgm", "DGM_X.log", "error", null, null);
        assertThat(p.getContent().getFilterLabel()).isEqualTo("Search Results");
        assertThat(p.getContent().getTotalMatch()).isEqualTo(700L);
        assertThat(p.getContent().getLines()).hasSize(LogServerService.SEARCH_LIMIT);
        assertThat(p.getContent().isTruncated()).isTrue();
    }

    @Test
    void timeFilter_inheritsRangeForUntimestampedLines(@TempDir Path tmp) throws IOException {
        Path d = tmp.resolve("dgm"); Files.createDirectories(d);
        String log =
                "[09:00:00.000 INFO] start\n" +
                "[10:00:00.000 ERROR] stack\n" +
                "  at Foo.bar\n" +
                "[11:00:00.000 INFO] ok\n" +
                "[12:00:00.000 INFO] done\n";
        Files.write(d.resolve("DGM_X.log"), log.getBytes());
        wireLogPaths(d.toString(), Collections.<String>emptyList());

        LogServerPayload p = service.build("dgm", "DGM_X.log", null, "09:30:00", "11:30:00");
        assertThat(p.getContent().getLines()).containsExactly(
                "[10:00:00.000 ERROR] stack",
                "  at Foo.bar",
                "[11:00:00.000 INFO] ok"
        );
    }

    @Test
    void unknownFile_returnsError(@TempDir Path tmp) throws IOException {
        Path d = tmp.resolve("dgm"); Files.createDirectories(d);
        wireLogPaths(d.toString(), Collections.<String>emptyList());
        LogServerPayload p = service.build("dgm", "missing.log", null, null, null);
        assertThat(p.getContent().getError()).isEqualTo("File not found");
    }
}
