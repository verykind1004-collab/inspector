package com.exem.inspector.screen.history;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Set;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

import com.exem.inspector.common.db.RepositoryConfig;
import com.exem.inspector.common.web.screen.ScreenResponse;
import com.exem.inspector.config.ServiceConfig;

/**
 * HistoryService 단위 테스트 — 6 view (Session 2: heap 추가) + 파라미터 정규화 + Unknown view.
 */
class HistoryServiceTest {

    @SuppressWarnings("unchecked")
    private final ObjectProvider<HistoryMapper> mapperProvider = mock(ObjectProvider.class);
    private final HistoryMapper mapper = mock(HistoryMapper.class);
    private final ServiceConfig serviceConfig = mock(ServiceConfig.class);
    private final HistoryService service = new HistoryService(mapperProvider, serviceConfig);

    private void wireRepoOracle() {
        RepositoryConfig repo = mock(RepositoryConfig.class);
        given(repo.dbType()).willReturn("Oracle");
        given(serviceConfig.repository()).willReturn(repo);
    }

    private void wireMapper() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
    }

    private LinkedHashMap<String, Object> heapRow(String at, String svc, int used, int alloc, int max) {
        LinkedHashMap<String, Object> r = new LinkedHashMap<>();
        r.put("collected_at", at);
        r.put("service_name", svc);
        r.put("heap_used_mb", used);
        r.put("heap_alloc_mb", alloc);
        r.put("heap_max_mb", max);
        return r;
    }

    // ── views() — 6 종 (Session 2: heap 추가) ──────────────────────────
    @Test
    void views_includesHeap() {
        Set<String> v = HistoryService.views();
        assertThat(v).hasSize(6).containsExactly("os", "tbs", "service", "heap", "qcnt", "summary");
    }

    // ── heap view 응답 — INSP_HEAP_HISTORY 5 컬럼 + 다중 인스턴스 분리 ──
    @Test
    void heap_returnsRows_withServiceNameForInstanceSplit() {
        wireMapper();
        wireRepoOracle();
        given(mapper.findHeapHistory(anyInt(), anyInt())).willReturn(Arrays.asList(
                heapRow("2026-06-04 09:00:00", "DGServer_M",  300, 500, 1024),
                heapRow("2026-06-04 09:00:00", "DGServer_S1", 280, 500, 1024),
                heapRow("2026-06-04 09:00:00", "PlatformJS",  450, 800, 2048)));

        ScreenResponse r = service.find("heap", 7, 500);

        assertThat(r.getColumns()).extracting(c -> c.getKey())
                .containsExactly("collected_at", "service_name",
                        "heap_used_mb", "heap_alloc_mb", "heap_max_mb");
        assertThat(r.getRows()).hasSize(3);
    }

    @Test
    void heap_emptyRows_ifMapperReturnsEmpty() {
        wireMapper();
        wireRepoOracle();
        given(mapper.findHeapHistory(anyInt(), anyInt())).willReturn(new ArrayList<>());
        ScreenResponse r = service.find("heap", 7, 500);
        assertThat(r.getRows()).isEmpty();
        assertThat(r.getColumns()).hasSize(5);
    }

    // ── 파라미터 정규화 ─────────────────────────────────────────────
    @Test
    void invalidDays_normalizedTo7() {
        wireMapper();
        wireRepoOracle();
        given(mapper.findOsHistory(anyInt(), anyInt())).willReturn(new ArrayList<>());

        service.find("os", 0, 500);
        verify(mapper).findOsHistory(7, 500);

        service.find("os", -5, 500);
        verify(mapper, org.mockito.Mockito.times(2)).findOsHistory(7, 500);
    }

    @Test
    void daysOverMax_cappedAt365() {
        wireMapper();
        wireRepoOracle();
        given(mapper.findOsHistory(anyInt(), anyInt())).willReturn(new ArrayList<>());
        service.find("os", 9999, 500);
        verify(mapper).findOsHistory(365, 500);
    }

    @Test
    void limitOverMax_cappedAt5000() {
        wireMapper();
        wireRepoOracle();
        given(mapper.findOsHistory(anyInt(), anyInt())).willReturn(new ArrayList<>());
        service.find("os", 7, 99999);
        verify(mapper).findOsHistory(7, 5000);
    }

    @Test
    void invalidLimit_normalizedTo500() {
        wireMapper();
        wireRepoOracle();
        given(mapper.findOsHistory(anyInt(), anyInt())).willReturn(new ArrayList<>());
        service.find("os", 7, 0);
        verify(mapper).findOsHistory(7, 500);
    }

    // ── Unknown view ──────────────────────────────────────────────────
    @Test
    void unknownView_throws() {
        wireMapper();
        wireRepoOracle();
        assertThatThrownBy(() -> service.find("nope", 7, 500))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Unknown view");
    }

    // ── No mapper — 빈 rows, 컬럼 메타는 그대로 ───────────────────
    @Test
    void noMapper_emptyRows_columnsPreserved() {
        given(mapperProvider.getIfAvailable()).willReturn(null);
        wireRepoOracle();
        ScreenResponse r = service.find("heap", 7, 500);
        assertThat(r.getRows()).isEmpty();
        assertThat(r.getColumns()).hasSize(5);
    }

    // ── Os view 컬럼 8개 검증 ──────────────────────────────────────────
    @Test
    void os_8columns() {
        wireMapper();
        wireRepoOracle();
        given(mapper.findOsHistory(anyInt(), anyInt())).willReturn(Collections.emptyList());
        ScreenResponse r = service.find("os", 7, 500);
        assertThat(r.getColumns()).hasSize(8);
    }
}
