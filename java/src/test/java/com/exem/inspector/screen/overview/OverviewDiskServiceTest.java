package com.exem.inspector.screen.overview;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

import com.exem.inspector.common.db.RepositoryConfig;
import com.exem.inspector.config.ServiceConfig;

/** OverviewDiskService — Oracle/PG 분기 + 상태 분류 단위 검증. */
class OverviewDiskServiceTest {

    @SuppressWarnings("unchecked")
    private OverviewDiskService serviceWith(OverviewDiskMapper mapper, String dbType, String pgDataDir) {
        ObjectProvider<OverviewDiskMapper> provider = mock(ObjectProvider.class);
        when(provider.getIfAvailable()).thenReturn(mapper);

        RepositoryConfig repo = mock(RepositoryConfig.class);
        when(repo.dbType()).thenReturn(dbType);
        when(repo.pgDataDir()).thenReturn(pgDataDir);
        ServiceConfig cfg = mock(ServiceConfig.class);
        when(cfg.repository()).thenReturn(repo);

        return new OverviewDiskService(provider, cfg);
    }

    private TablespaceRow row(String name, double used, double total, double free, double pct) {
        TablespaceRow r = new TablespaceRow();
        r.setName(name); r.setUsedGb(used); r.setTotalGb(total); r.setFreeGb(free); r.setPercent(pct);
        return r;
    }

    @Test
    void oracle_assemblesTablespaceItemsWithStatus() {
        OverviewDiskMapper mapper = mock(OverviewDiskMapper.class);
        when(mapper.findOracleTablespaces()).thenReturn(Arrays.asList(
                row("USERS", 50.0, 100.0, 50.0, 50.0),  // ok
                row("DATA",  85.0, 100.0, 15.0, 85.0)   // warning
        ));
        OverviewDiskService s = serviceWith(mapper, "ORACLE", "");

        Map<String, Object> r = s.disk();

        assertThat(r).containsEntry("type", "tablespace");
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> items = (List<Map<String, Object>>) r.get("items");
        assertThat(items).hasSize(2);
        assertThat(items.get(0)).containsEntry("name", "USERS").containsEntry("status", "ok");
        assertThat(items.get(1)).containsEntry("name", "DATA").containsEntry("status", "warning");
        // overall = worse — warning
        assertThat(r).containsEntry("overall", "warning");
    }

    @Test
    void oracle_emptyList_returnsErrorOverall() {
        OverviewDiskMapper mapper = mock(OverviewDiskMapper.class);
        when(mapper.findOracleTablespaces()).thenReturn(Collections.emptyList());
        OverviewDiskService s = serviceWith(mapper, "ORACLE", "");

        Map<String, Object> r = s.disk();

        assertThat(r).containsEntry("type", "tablespace");
        assertThat(r.get("error")).asString().contains("No tablespace data");
    }

    @Test
    void oracle_noMapper_returnsConfigError() {
        OverviewDiskService s = serviceWith(null, "ORACLE", "");

        Map<String, Object> r = s.disk();

        assertThat(r).containsEntry("type", "tablespace");
        assertThat(r.get("error")).asString().contains("리포지토리가 설정");
    }

    @Test
    void pg_readsRootDisk_returnsTypeDisk() {
        // pg_data_dir 미설정 → "/" 사용. 실 /파일 시스템 stat 호출이라 정확값 단언은 피하고
        // 키 + 타입 + 상태 분류 유효성만 검증.
        OverviewDiskService s = serviceWith(null, "POSTGRESQL", "");

        Map<String, Object> r = s.disk();

        assertThat(r).containsEntry("type", "disk");
        assertThat(r).containsKey("total_gb").containsKey("used_gb")
                .containsKey("free_gb").containsKey("percent").containsKey("status");
        assertThat(r.get("status")).isIn("ok", "warning", "critical");
    }

    @Test
    void pg_invalidPath_returnsZerosWithError() {
        OverviewDiskService s = serviceWith(null, "POSTGRESQL", "/__nonexistent__path__");

        Map<String, Object> r = s.disk();

        assertThat(r).containsEntry("type", "disk");
        assertThat(r).containsEntry("total_gb", 0.0).containsEntry("status", "ok");
        assertThat(r).containsKey("error");
    }
}
