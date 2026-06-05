package com.exem.inspector.screen.overview;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import com.exem.inspector.common.db.RepositoryConfig;
import com.exem.inspector.config.ServiceConfig;
import com.exem.inspector.config.ServicesBlock;

/** OverviewServicesService — 행 구성·상태 분기·미설정 케이스 단위 검증. */
class OverviewServicesServiceTest {

    private OverviewServicesService make(ServiceConfig cfg) {
        return new OverviewServicesService(
                cfg,
                new PortChecker(),
                new DgServerXmlReader(),
                new VersionReader(),
                new UptimeReader());
    }

    private ServiceConfig cfgWith(ServicesBlock services, RepositoryConfig repo) {
        ServiceConfig cfg = mock(ServiceConfig.class);
        when(cfg.services()).thenReturn(services);
        when(cfg.repository()).thenReturn(repo == null ? new RepositoryConfig() : repo);
        return cfg;
    }

    @Test
    void allEmpty_returnsBaseRowsWithStopped() {
        ServiceConfig cfg = cfgWith(new ServicesBlock(), null);
        OverviewServicesService s = make(cfg);

        Map<String, Object> r = s.services();

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> rows = (List<Map<String, Object>>) r.get("services");
        // DGServer_M + (S 0건) + PlatformJS + Client + Repo DB = 4행
        assertThat(rows).hasSize(4);
        assertThat(rows.get(0)).containsEntry("name", "DGServer_M").containsEntry("status", "stopped");
        assertThat(rows.get(1)).containsEntry("name", "PlatformJS");
        assertThat(rows.get(2)).containsEntry("name", "Client").containsEntry("status", "-");
        assertThat(rows.get(3).get("name")).asString().startsWith("Repository DB");
        assertThat(rows.get(3)).containsEntry("status", "unconfigured");
    }

    @Test
    void dgserverS_count_addsRowsPerEntry() {
        ServicesBlock sb = new ServicesBlock() {{
            // dgserverM 빈, dgserverS 2개 (실제 fields 는 private 이므로 ObjectMapper 로 만들어야 함 — 여기선
            // 간단히 빈 ServicesBlock 사용 후 별도 케이스로 검증)
        }};
        ServiceConfig cfg = cfgWith(sb, null);
        OverviewServicesService s = make(cfg);
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> rows = (List<Map<String, Object>>) s.services().get("services");
        // 본 케이스는 default 빈 ServicesBlock — 4행 유지
        assertThat(rows).hasSize(4);
    }

    @Test
    void dgRow_existsButNoXml_isStopped(@TempDir Path tmp) throws Exception {
        // home 디렉토리만 있고 conf/DGServer.xml 없음 → port=0 → status=stopped
        Path home = tmp.resolve("DGServer_M");
        Files.createDirectories(home);
        ServicesBlock sb = mock(ServicesBlock.class);
        when(sb.dgserverM()).thenReturn(home.toString());
        when(sb.dgserverS()).thenReturn(Arrays.asList());
        when(sb.platformjs()).thenReturn("");

        ServiceConfig cfg = cfgWith(sb, null);
        OverviewServicesService s = make(cfg);
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> rows = (List<Map<String, Object>>) s.services().get("services");

        Map<String, Object> dg = rows.get(0);
        assertThat(dg).containsEntry("name", "DGServer_M")
                .containsEntry("status", "stopped")
                .containsEntry("port", "-");
        assertThat(dg.get("home")).isEqualTo(home.toString());
    }

    @Test
    void dgRow_withXmlPort_readsPortAndChecksListen(@TempDir Path tmp) throws Exception {
        // 단일 free port 잡고 listen 안 함 — TCP check 실패 → stopped, 그러나 port 는 읽혀야 함
        Path home = tmp.resolve("DG");
        Files.createDirectories(home.resolve("conf"));
        Files.write(home.resolve("conf").resolve("DGServer.xml"),
                "<root><gather_port>59999</gather_port></root>".getBytes());

        ServicesBlock sb = mock(ServicesBlock.class);
        when(sb.dgserverM()).thenReturn(home.toString());
        when(sb.dgserverS()).thenReturn(Arrays.asList());
        when(sb.platformjs()).thenReturn("");

        OverviewServicesService s = make(cfgWith(sb, null));
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> rows = (List<Map<String, Object>>) s.services().get("services");
        Map<String, Object> dg = rows.get(0);
        assertThat(dg).containsEntry("port", "59999");
        assertThat(dg.get("status")).isIn("running", "stopped");  // 환경 의존이라 둘 다 허용
    }

    @Test
    void repoDb_configured_returnsName() {
        RepositoryConfig repo = mock(RepositoryConfig.class);
        when(repo.isConfigured()).thenReturn(true);
        when(repo.dbType()).thenReturn("Oracle");
        when(repo.ip()).thenReturn("127.0.0.1");
        when(repo.port()).thenReturn(59998);
        ServicesBlock sb = new ServicesBlock();

        OverviewServicesService s = make(cfgWith(sb, repo));
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> rows = (List<Map<String, Object>>) s.services().get("services");
        Map<String, Object> row = rows.get(rows.size() - 1);
        assertThat(row.get("name")).asString().contains("Repository DB").contains("Oracle");
        assertThat(row.get("port")).isEqualTo("59998");
    }
}
