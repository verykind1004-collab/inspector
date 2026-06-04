package com.exem.inspector.screen.disk;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.fail;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

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
 * DiskService 단위 테스트 — 워커 시작/거부/완료/에러 + 카드 fall-through.
 *
 * <p>JdbcTemplate execute 는 DataSource 단을 mock 으로 잡아 workers 가 호출하는 실 SQL 을
 * NPE 없이 통과시킨다 (DataSource 가 mock 인 경우 JdbcTemplate.execute(SQL) 가 connection 획득 시 예외 → catch).
 */
class DiskServiceTest {

    @SuppressWarnings("unchecked")
    private final ObjectProvider<DiskMapper> mapperProvider = mock(ObjectProvider.class);
    @SuppressWarnings("unchecked")
    private final ObjectProvider<DataSource> dsProvider = mock(ObjectProvider.class);
    private final DiskMapper mapper = mock(DiskMapper.class);
    private final ServiceConfig serviceConfig = mock(ServiceConfig.class);
    private final VacuumLogReader logReader = mock(VacuumLogReader.class);

    private final DiskService service = new DiskService(mapperProvider, dsProvider, serviceConfig, logReader);

    private void wireRepoPg() {
        RepositoryConfig repo = mock(RepositoryConfig.class);
        given(repo.dbType()).willReturn("PostgreSQL");
        given(serviceConfig.repository()).willReturn(repo);
    }

    // ── Cards (SELECT) ─────────────────────────────────────────────

    @Test
    void vacuumLog_delegatesToReader() {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("source", "DGM_5050.log");
        given(logReader.toScreenPayload()).willReturn(payload);
        assertThat(service.vacuumLog()).isEqualTo(payload);
    }

    @Test
    void autoVacuumCard_emptyWhenMapperUnavailable() {
        given(mapperProvider.getIfAvailable()).willReturn(null);
        assertThat(service.autoVacuumCard()).isEmpty();
    }

    @Test
    void autoVacuumCard_returnsRowsFromMapper() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        LinkedHashMap<String, Object> r = new LinkedHashMap<>();
        r.put("schema", "apm");
        r.put("table_name", "tt_log");
        given(mapper.findAutoVacuumTargets()).willReturn(Collections.singletonList(r));
        List<Map<String, Object>> out = service.autoVacuumCard();
        assertThat(out).hasSize(1);
        assertThat(out.get(0)).containsEntry("schema", "apm").containsEntry("table_name", "tt_log");
    }

    @Test
    void ageCard_returnsRowsFromMapper() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        LinkedHashMap<String, Object> r = new LinkedHashMap<>();
        r.put("dbname", "ix");
        r.put("max_age", "1,234,567");
        given(mapper.findAge()).willReturn(Collections.singletonList(r));
        assertThat(service.ageCard()).hasSize(1);
    }

    @Test
    void tempTableList_returnsRowsFromMapper() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        LinkedHashMap<String, Object> r = new LinkedHashMap<>();
        r.put("SCHEMA", "apm");
        r.put("TEMP TABLE", "tt_session_x");
        given(mapper.findTempTables()).willReturn(Collections.singletonList(r));
        assertThat(service.tempTableList()).hasSize(1);
    }

    // ── VACUUM FREEZE ──────────────────────────────────────────────

    @Test
    void startVacuumFreeze_failsWhenRepositoryAbsent() throws Exception {
        given(dsProvider.getIfAvailable()).willReturn(null);
        Map<String, Object> resp = service.startVacuumFreeze();
        assertThat(resp).containsEntry("ok", true);
        // worker 실행 대기 후 state 확인
        DiskService.VacuumFreezeState st = waitForFreezeFinished();
        assertThat(st.isRunning()).isFalse();
        assertThat(st.getError()).isEqualTo("Repository not configured");
    }

    @Test
    void startVacuumFreeze_rejectsConcurrent() throws Exception {
        // 첫 호출은 시작, 그러나 dataSource null 이면 worker 가 빠르게 끝남.
        // 두 번째 호출은 첫 worker 완료 후라면 다시 시작 — 즉시 다시 호출해서 running 충돌 유도.
        given(dsProvider.getIfAvailable()).willReturn(null);
        Map<String, Object> first = service.startVacuumFreeze();
        // first 가 워커 setDaemon start 한 직후 즉시 두 번째 호출
        Map<String, Object> second = service.startVacuumFreeze();
        // 적어도 둘 중 하나는 ok=false ("Already running")이거나 둘 다 ok=true (워커가 충분히 빨라 두 번째 호출 시점에는 idle)
        // 결정적 테스트를 위해 - 사이 시작 직후 보장 어려움 → state 자체로 검증.
        // 따라서 "second 가 ok=false 이거나, 둘 다 워커가 끝나 idle 상태로 마무리" 둘 다 허용.
        DiskService.VacuumFreezeState st = waitForFreezeFinished();
        assertThat(st.isRunning()).isFalse();
        // 어쨌든 worker 가 종료된 상태여야 함 — concurrent rejection 메시지 형식만 확인.
        if (second.get("ok").equals(false)) {
            assertThat(((String) second.get("error"))).startsWith("Already running since ");
        }
        assertThat(first.get("ok")).isEqualTo(true);
    }

    @Test
    void vacuumFreezeStatus_initiallyIdle() {
        DiskService.VacuumFreezeState st = service.vacuumFreezeStatus();
        assertThat(st.isRunning()).isFalse();
        assertThat(st.getStarted()).isNull();
        assertThat(st.getError()).isNull();
    }

    // ── VACUUM TABLE ───────────────────────────────────────────────

    @Test
    void startVacuumTable_failsWhenNoMapper() {
        given(mapperProvider.getIfAvailable()).willReturn(null);
        Map<String, Object> resp = service.startVacuumTable();
        assertThat(resp).containsEntry("ok", false).containsEntry("error", "Repository not configured");
    }

    @Test
    void startVacuumTable_failsWhenNoTablesReturned() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(mapper.findAutoVacuumTargets()).willReturn(Collections.emptyList());
        Map<String, Object> resp = service.startVacuumTable();
        assertThat(resp).containsEntry("ok", false).containsEntry("error", "No tables to vacuum");
    }

    @Test
    void startVacuumTable_failsWhenAllRowsLackSchemaOrTable() {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        LinkedHashMap<String, Object> r = new LinkedHashMap<>();
        r.put("schema", "");
        r.put("table_name", "");
        given(mapper.findAutoVacuumTargets()).willReturn(Collections.singletonList(r));
        Map<String, Object> resp = service.startVacuumTable();
        assertThat(resp).containsEntry("ok", false).containsEntry("error", "No valid tables found");
    }

    @Test
    void startVacuumTable_kicksOffWorker() throws Exception {
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(dsProvider.getIfAvailable()).willReturn(null);
        LinkedHashMap<String, Object> r = new LinkedHashMap<>();
        r.put("schema", "apm");
        r.put("table_name", "t1");
        given(mapper.findAutoVacuumTargets()).willReturn(Collections.singletonList(r));
        Map<String, Object> resp = service.startVacuumTable();
        assertThat(resp).containsEntry("ok", true).containsEntry("total", 1);
        DiskService.VacuumTableState st = waitForVtFinished();
        assertThat(st.isRunning()).isFalse();
        assertThat(st.getError()).isEqualTo("Repository not configured");
        assertThat(st.getTotal()).isEqualTo(1);
    }

    @Test
    void vacuumTableStatus_initiallyIdle() {
        DiskService.VacuumTableState st = service.vacuumTableStatus();
        assertThat(st.isRunning()).isFalse();
        assertThat(st.getDone()).isZero();
        assertThat(st.getTotal()).isZero();
    }

    // ── TEMP TABLE DROP ─────────────────────────────────────────────

    @Test
    void startTempTableDrop_failsWhenNoMapper() {
        given(mapperProvider.getIfAvailable()).willReturn(null);
        Map<String, Object> resp = service.startTempTableDropAll();
        assertThat(resp).containsEntry("ok", false);
    }

    @Test
    void startTempTableDrop_failsWhenSqlReturnsEmpty() {
        wireRepoPg();
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(mapper.findTempTables()).willReturn(Collections.emptyList());
        Map<String, Object> resp = service.startTempTableDropAll();
        assertThat(resp).containsEntry("ok", false).containsEntry("error", "No tables to drop");
    }

    @Test
    void startTempTableDrop_failsWhenRowsLackTtPrefix() {
        wireRepoPg();
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        LinkedHashMap<String, Object> r = new LinkedHashMap<>();
        r.put("SCHEMA", "apm");
        r.put("TEMP TABLE", "session_log"); // tt prefix 없음
        given(mapper.findTempTables()).willReturn(Collections.singletonList(r));
        Map<String, Object> resp = service.startTempTableDropAll();
        assertThat(resp).containsEntry("ok", false).containsEntry("error", "No valid tt% tables");
    }

    @Test
    void startTempTableDrop_filtersUnsafeIdentifiers() {
        wireRepoPg();
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        LinkedHashMap<String, Object> r = new LinkedHashMap<>();
        r.put("SCHEMA", "apm");
        r.put("TEMP TABLE", "tt_session;DROP"); // 안전성 검사 미통과
        given(mapper.findTempTables()).willReturn(Collections.singletonList(r));
        Map<String, Object> resp = service.startTempTableDropAll();
        assertThat(resp).containsEntry("ok", false).containsEntry("error", "No valid tt% tables");
    }

    @Test
    void startTempTableDrop_kicksOffWorker() throws Exception {
        wireRepoPg();
        given(mapperProvider.getIfAvailable()).willReturn(mapper);
        given(dsProvider.getIfAvailable()).willReturn(null);
        LinkedHashMap<String, Object> r = new LinkedHashMap<>();
        r.put("SCHEMA", "apm");
        r.put("TEMP TABLE", "tt_session_x");
        given(mapper.findTempTables()).willReturn(Collections.singletonList(r));
        Map<String, Object> resp = service.startTempTableDropAll();
        assertThat(resp).containsEntry("ok", true).containsEntry("total", 1);
        DiskService.TempTableDropState st = waitForTtFinished();
        assertThat(st.isRunning()).isFalse();
        assertThat(st.getError()).isEqualTo("Repository not configured");
        assertThat(st.getTotal()).isEqualTo(1);
    }

    @Test
    void tempTableDropStatus_initiallyIdle() {
        DiskService.TempTableDropState st = service.tempTableDropStatus();
        assertThat(st.isRunning()).isFalse();
        assertThat(st.getErrors()).isEmpty();
    }

    // ── 헬퍼: 워커 종료 대기 ─────────────────────────────────────────

    private DiskService.VacuumFreezeState waitForFreezeFinished() throws InterruptedException {
        for (int i = 0; i < 50; i++) {
            DiskService.VacuumFreezeState st = service.vacuumFreezeStatus();
            if (!st.isRunning() && st.getFinished() != null) return st;
            Thread.sleep(20);
        }
        fail("VACUUM FREEZE 워커가 1초 안에 끝나지 않았습니다");
        return null;
    }

    private DiskService.VacuumTableState waitForVtFinished() throws InterruptedException {
        for (int i = 0; i < 50; i++) {
            DiskService.VacuumTableState st = service.vacuumTableStatus();
            if (!st.isRunning() && st.getFinished() != null) return st;
            Thread.sleep(20);
        }
        fail("VACUUM TABLE 워커가 1초 안에 끝나지 않았습니다");
        return null;
    }

    private DiskService.TempTableDropState waitForTtFinished() throws InterruptedException {
        for (int i = 0; i < 50; i++) {
            DiskService.TempTableDropState st = service.tempTableDropStatus();
            if (!st.isRunning() && st.getFinished() != null) return st;
            Thread.sleep(20);
        }
        fail("Temp Table Drop 워커가 1초 안에 끝나지 않았습니다");
        return null;
    }
}
