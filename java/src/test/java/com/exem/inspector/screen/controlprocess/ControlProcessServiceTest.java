package com.exem.inspector.screen.controlprocess;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import org.junit.jupiter.api.Test;

import com.exem.inspector.config.ServiceConfig;
import com.exem.inspector.config.ServicesBlock;

/**
 * ControlProcessService 라우팅 검증 — resolve(name) 화이트리스트 + Unknown 케이스.
 *
 * <p>실제 start/stop 은 ProcessBuilder 직접 호출이라 통합 테스트로 검증.
 * 본 테스트는 라우팅 + supportedNames 만.
 */
class ControlProcessServiceTest {

    private final ServiceConfig serviceConfig = mock(ServiceConfig.class);
    private final ObsdHelper obsdHelper = mock(ObsdHelper.class);
    private final ControlProcessService service = new ControlProcessService(serviceConfig, obsdHelper);

    private void wireServices(String dgM, List<String> dgS, String pjs) {
        ServicesBlock sb = mock(ServicesBlock.class);
        given(sb.dgserverM()).willReturn(dgM == null ? "" : dgM);
        given(sb.dgserverS()).willReturn(dgS == null ? Collections.emptyList() : dgS);
        given(sb.platformjs()).willReturn(pjs == null ? "" : pjs);
        given(serviceConfig.services()).willReturn(sb);
    }

    @Test
    void unknownName_returnsError() {
        wireServices("/tmp/dgm", Arrays.asList("/tmp/dgs1"), "/tmp/pjs");
        assertThat(service.start("Unknown").isOk()).isFalse();
        assertThat(service.stop("Unknown").getMessage()).contains("Unknown service");
    }

    @Test
    void dgServerS_outOfRange_returnsUnknown() {
        wireServices("/tmp/dgm", Arrays.asList("/tmp/dgs1"), "/tmp/pjs");
        // S2 = idx 1, 리스트 1개라 idx 1 없음
        assertThat(service.start("DGServer_S2").getMessage()).contains("Unknown service");
    }

    @Test
    void supportedNames_includesAll4() {
        List<String> names = ControlProcessService.supportedNames();
        assertThat(names).containsExactlyInAnyOrder(
                "DGServer_M", "DGServer_S1", "DGServer_S2", "PlatformJS");
    }

    @Test
    void emptyHome_returnsUnknown() {
        wireServices("", Collections.emptyList(), "");
        assertThat(service.start("DGServer_M").getMessage()).contains("Unknown service");
        assertThat(service.start("PlatformJS").getMessage()).contains("Unknown service");
    }

    @Test
    void dgServerS_badIndex_returnsNull() {
        wireServices("/tmp/dgm", Arrays.asList("/tmp/dgs1"), "/tmp/pjs");
        assertThat(service.start("DGServer_SX").getMessage()).contains("Unknown service");
    }
}
