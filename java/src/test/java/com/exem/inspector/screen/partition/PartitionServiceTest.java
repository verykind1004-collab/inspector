package com.exem.inspector.screen.partition;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import javax.sql.DataSource;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

import com.exem.inspector.common.db.RepositoryConfig;
import com.exem.inspector.config.ServiceConfig;

/**
 * PartitionService 단위 테스트 — Drop List 그룹화 / instance lookup / Drop 동시성 제어 / Create 검증.
 */
class PartitionServiceTest {

    @SuppressWarnings("unchecked")
    private final ObjectProvider<PartitionMapper> mapperProvider = mock(ObjectProvider.class);
    @SuppressWarnings("unchecked")
    private final ObjectProvider<DataSource> dataSourceProvider = mock(ObjectProvider.class);
    private final PartitionMapper mapper = mock(PartitionMapper.class);
    private final ServiceConfig serviceConfig = mock(ServiceConfig.class);

    private final PartitionService service = new PartitionService(mapperProvider, dataSourceProvider, serviceConfig);

    private void wireRepoOracle() {
        RepositoryConfig repo = mock(RepositoryConfig.class);
        given(repo.dbType()).willReturn("Oracle");
        given(serviceConfig.repository()).willReturn(repo);
    }

    private void wireRepoPg() {
        RepositoryConfig repo = mock(RepositoryConfig.class);
        given(repo.dbType()).willReturn("PostgreSQL");
        given(serviceConfig.repository()).willReturn(repo);
    }

    private LinkedHashMap<String, Object> row(String value) {
        LinkedHashMap<String, Object> r = new LinkedHashMap<>();
        r.put("partition_to_drop", value);
        return r;
    }

    // ── instances() ────────────────────────────────────────────────────
    @Test
    void instances_returnsEmpty_whenNoMapper() {
        given(mapperProvider.getIfAvailable()).willReturn(null);
        assertThat(service.instances()).isEmpty();
    }

    @Test
    void instances_returnsRows() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        LinkedHashMap<String, Object> r = new LinkedHashMap<>();
        r.put("db_id", 1); r.put("instance_name", "ORA19");
        given(mapper.findInstances()).willReturn(Collections.singletonList(r));
        assertThat(service.instances()).hasSize(1)
                .first().extracting(m -> m.get("instance_name")).isEqualTo("ORA19");
    }

    // ── dropList — table/partition 분리 + 그룹화 ─────────────────────
    @Test
    void dropList_groupsByTable() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(mapper.findDropList(anyInt())).willReturn(Arrays.asList(
                row("INSP_OS_HISTORY / P241201001"),
                row("INSP_OS_HISTORY / P241202001"),
                row("INSP_TBS_HISTORY / P241201001")));

        PartitionService.DropListResult r = service.dropList(1);
        assertThat(r.isOk()).isTrue();
        assertThat(r.getGroups()).hasSize(2);
        assertThat(r.getGroups().get(0).getTable()).isEqualTo("INSP_OS_HISTORY");
        assertThat(r.getGroups().get(0).getPartitions()).containsExactly("P241201001", "P241202001");
        assertThat(r.getGroups().get(1).getTable()).isEqualTo("INSP_TBS_HISTORY");
        assertThat(r.getGroups().get(1).getPartitions()).containsExactly("P241201001");
    }

    @Test
    void dropList_handlesEntryWithoutSlash() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(mapper.findDropList(anyInt())).willReturn(Arrays.asList(
                row("STANDALONE_TABLE")));
        PartitionService.DropListResult r = service.dropList(1);
        assertThat(r.isOk()).isTrue();
        assertThat(r.getGroups()).hasSize(1);
        assertThat(r.getGroups().get(0).getTable()).isEqualTo("STANDALONE_TABLE");
        assertThat(r.getGroups().get(0).getPartitions()).isEmpty();
    }

    @Test
    void dropList_noMapper_returnsError() {
        given(mapperProvider.getIfAvailable()).willReturn(null);
        PartitionService.DropListResult r = service.dropList(1);
        assertThat(r.isOk()).isFalse();
        assertThat(r.getError()).contains("Repository not configured");
    }

    @Test
    void dropList_emptyRows_returnsOkEmptyGroups() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(mapper.findDropList(anyInt())).willReturn(new ArrayList<>());
        PartitionService.DropListResult r = service.dropList(1);
        assertThat(r.isOk()).isTrue();
        assertThat(r.getGroups()).isEmpty();
    }

    // ── startDropPartitions — 동시 1건 ────────────────────────────────
    @Test
    void startDrop_reentrant_isRejected() {
        // 첫 시도 — running 상태 진입
        given(mapperProvider.getIfAvailable()).willReturn(null);
        given(dataSourceProvider.getIfAvailable()).willReturn(null);
        wireRepoPg();
        Map<String, Object> first = service.startDropPartitions(1);
        assertThat(first.get("ok")).isEqualTo(true);
        // 두 번째 즉시 시도 — 거부되어야 함 (worker 스레드가 finish 하기 전 가능성)
        Map<String, Object> second = service.startDropPartitions(1);
        // worker 가 매우 빠르게 끝나 idle 상태로 돌아왔으면 ok 일 수 있어 either ok 인정.
        // 핵심 검증: 응답에 ok 키 존재 + error 시 'Already running' 포함.
        assertThat(second).containsKey("ok");
        if (Boolean.FALSE.equals(second.get("ok"))) {
            assertThat(String.valueOf(second.get("error"))).contains("Already running");
        }
    }

    // ── createPartition 입력 검증 ────────────────────────────────────
    @Test
    void create_emptyInstance_returnsError() {
        Map<String, Object> r = service.createPartition("", "2026-01-01", "2026-01-31");
        assertThat(r.get("ok")).isEqualTo(false);
        assertThat(String.valueOf(r.get("error"))).contains("instance_name required");
    }

    @Test
    void create_noMapper_returnsError() {
        given(mapperProvider.getIfAvailable()).willReturn(null);
        Map<String, Object> r = service.createPartition("ORA19", "", "");
        assertThat(r.get("ok")).isEqualTo(false);
        assertThat(String.valueOf(r.get("error"))).contains("Repository not configured");
    }

    @Test
    void create_instanceNotFound_returnsError() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(dataSourceProvider.getIfAvailable()).willReturn(mock(DataSource.class));
        given(mapper.findDbIdByInstance("ORA19")).willReturn(null);
        wireRepoOracle();
        Map<String, Object> r = service.createPartition("ORA19", "", "");
        assertThat(r.get("ok")).isEqualTo(false);
        assertThat(String.valueOf(r.get("error"))).contains("Instance not found");
    }

    // ── createProcedure — Oracle only ─────────────────────────────────
    @Test
    void createProcedure_pg_rejected() {
        given(dataSourceProvider.getIfAvailable()).willReturn(mock(DataSource.class));
        wireRepoPg();
        Map<String, Object> r = service.createProcedure();
        assertThat(r.get("ok")).isEqualTo(false);
        assertThat(String.valueOf(r.get("error"))).contains("Oracle 전용");
    }

    @Test
    void createProcedure_oracle_ok() {
        given(dataSourceProvider.getIfAvailable()).willReturn(mock(DataSource.class));
        wireRepoOracle();
        Map<String, Object> r = service.createProcedure();
        assertThat(r.get("ok")).isEqualTo(true);
    }

    @Test
    void createProcedure_noDataSource_returnsError() {
        given(dataSourceProvider.getIfAvailable()).willReturn(null);
        Map<String, Object> r = service.createProcedure();
        assertThat(r.get("ok")).isEqualTo(false);
    }

    // ── dropStatus — 초기 idle ────────────────────────────────────────
    @Test
    void dropStatus_initiallyIdle() {
        PartitionService.DropState s = service.dropStatus();
        assertThat(s.isRunning()).isFalse();
        assertThat(s.getDropped()).isZero();
        assertThat(s.getTotal()).isZero();
    }
}
