package com.exem.inspector.screen.process;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Collections;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import com.exem.inspector.config.ServiceConfig;
import com.exem.inspector.config.ServicesBlock;

/**
 * ObsdService 단위 테스트 — 원본 _gather_obsd_html 1:1 검증.
 */
class ObsdServiceTest {

    private final ServiceConfig serviceConfig = mock(ServiceConfig.class);
    private final ObsdService service = new ObsdService(serviceConfig);

    private void wireServices(String dgm, java.util.List<String> dgs) {
        ServicesBlock svc = mock(ServicesBlock.class);
        given(svc.dgserverM()).willReturn(dgm == null ? "" : dgm);
        given(svc.dgserverS()).willReturn(dgs);
        given(serviceConfig.services()).willReturn(svc);
    }

    @Test
    void noPaths_configError() {
        wireServices("", Collections.<String>emptyList());
        ObsdPayload p = service.listProcs();
        assertThat(p.getProcs()).isEmpty();
        assertThat(p.getConfigError()).contains("설정되지 않았습니다");
    }

    @Test
    void dgm_only_returnsOneProc(@TempDir Path tmp) throws IOException {
        Path home = tmp.resolve("dgm");
        Path logDir = home.resolve("log").resolve("maxgauge");
        Files.createDirectories(logDir);
        Files.write(logDir.resolve("obsd1.log"),    "x".getBytes());
        Files.write(logDir.resolve("obsd2.log.zip"), "y".getBytes());
        Files.write(logDir.resolve("other.log"),     "z".getBytes()); // 패턴 미일치 — 제외
        wireServices(home.toString(), Collections.<String>emptyList());

        ObsdPayload p = service.listProcs();
        assertThat(p.getProcs()).hasSize(1);
        ObsdPayload.Proc proc = p.getProcs().get(0);
        assertThat(proc.getId()).isEqualTo("dgm");
        assertThat(proc.getName()).isEqualTo("DGServer_M");
        assertThat(proc.getFiles()).extracting(ObsdPayload.File::getName)
                .containsExactlyInAnyOrder("obsd1.log", "obsd2.log.zip");
        assertThat(proc.getError()).isNull();
    }

    @Test
    void dgsList_namedSequentially(@TempDir Path tmp) throws IOException {
        Path s1 = tmp.resolve("s1"); Files.createDirectories(s1.resolve("log/maxgauge"));
        Path s2 = tmp.resolve("s2"); Files.createDirectories(s2.resolve("log/maxgauge"));
        wireServices("", Arrays.asList(s1.toString(), "", s2.toString()));
        // 빈 문자열 dgs[1] 은 스킵되지만 (i+1) 인덱싱 규칙은 유지(원본도 i 기반)

        ObsdPayload p = service.listProcs();
        assertThat(p.getProcs()).extracting(ObsdPayload.Proc::getId)
                .containsExactly("dgs1", "dgs3");
    }

    @Test
    void noLogDir_filesEmpty_noError(@TempDir Path tmp) {
        // home 은 있지만 log/maxgauge 디렉토리 없음
        Path home = tmp.resolve("dgm");
        wireServices(home.toString(), Collections.<String>emptyList());

        ObsdPayload p = service.listProcs();
        assertThat(p.getProcs()).hasSize(1);
        assertThat(p.getProcs().get(0).getFiles()).isEmpty();
        assertThat(p.getProcs().get(0).getError()).isNull();
    }

    @Test
    void filesSortedByMtimeDesc(@TempDir Path tmp) throws IOException, InterruptedException {
        Path home = tmp.resolve("dgm");
        Path logDir = home.resolve("log").resolve("maxgauge");
        Files.createDirectories(logDir);
        Files.write(logDir.resolve("obsd1.log"), "a".getBytes());
        Thread.sleep(5);
        Files.write(logDir.resolve("obsd2.log"), "b".getBytes());
        wireServices(home.toString(), Collections.<String>emptyList());

        ObsdPayload p = service.listProcs();
        assertThat(p.getProcs().get(0).getFiles())
                .extracting(ObsdPayload.File::getName)
                .containsExactly("obsd2.log", "obsd1.log");
    }
}
