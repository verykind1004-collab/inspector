package com.exem.inspector.screen.simple;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

import com.exem.inspector.common.db.RepositoryConfig;
import com.exem.inspector.common.web.screen.ColumnRole;
import com.exem.inspector.common.web.screen.ScreenResponse;
import com.exem.inspector.config.ServiceConfig;

class SimpleScreenServiceTest {

    @SuppressWarnings("unchecked")
    private SimpleScreenService serviceWith(SimpleScreenMapper mapper, String dbType) {
        ObjectProvider<SimpleScreenMapper> provider = mock(ObjectProvider.class);
        when(provider.getIfAvailable()).thenReturn(mapper);
        RepositoryConfig repo = mock(RepositoryConfig.class);
        when(repo.dbType()).thenReturn(dbType);
        ServiceConfig cfg = mock(ServiceConfig.class);
        when(cfg.repository()).thenReturn(repo);
        return new SimpleScreenService(provider, cfg);
    }

    private LinkedHashMap<String, Object> row(Object... kv) {
        LinkedHashMap<String, Object> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) m.put((String) kv[i], kv[i + 1]);
        return m;
    }

    @Test
    void license_컬럼_8개_및_행_정확히_매핑() {
        SimpleScreenMapper m = mock(SimpleScreenMapper.class);
        when(m.findLicense()).thenReturn(Arrays.asList(
                row("db_id", 1, "instance_name", "ORACLE19", "sid", "ORA19",
                    "rts_version", "5.3.2", "host_ip", "10.10.45.136",
                    "os_type", "Linux", "RTS PORT", 9601, "lsnr_port", 1521)));
        ScreenResponse res = serviceWith(m, "Oracle").find("license");
        assertThat(res.getColumns()).hasSize(8);
        assertThat(res.getColumns().get(1).getRole()).isEqualTo(ColumnRole.INSTANCE);
        assertThat(res.getRows().get(0))
                .containsEntry("db_id", 1)
                .containsEntry("instance_name", "ORACLE19")
                .containsEntry("RTS PORT", 9601);
    }

    @Test
    void capacity_Oracle과_PG_컬럼_메타_분리() {
        SimpleScreenMapper m = mock(SimpleScreenMapper.class);
        when(m.findCapacity()).thenReturn(Collections.emptyList());

        ScreenResponse ora = serviceWith(m, "Oracle").find("capacity");
        assertThat(ora.getColumns()).extracting(c -> c.getKey())
                .containsExactly("TABLESPACE_NAME", "Used", "Total", "PERCENT");

        ScreenResponse pg = serviceWith(m, "PostgreSQL").find("capacity");
        assertThat(pg.getColumns()).extracting(c -> c.getKey())
                .containsExactly("schema_name", "size_gb");
    }

    @Test
    void vacuum과_age는_PG_전용_Oracle은_거부() {
        SimpleScreenMapper m = mock(SimpleScreenMapper.class);
        SimpleScreenService oracleSvc = serviceWith(m, "Oracle");
        assertThatThrownBy(() -> oracleSvc.find("vacuum"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("지원하지 않는");
        assertThatThrownBy(() -> oracleSvc.find("age"))
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    void 미지원_화면_키는_IllegalArgument() {
        SimpleScreenService svc = serviceWith(mock(SimpleScreenMapper.class), "Oracle");
        assertThatThrownBy(() -> svc.find("does_not_exist"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void 리포지토리_미설정이면_IllegalState() {
        SimpleScreenService svc = serviceWith(null, "Oracle");
        assertThatThrownBy(() -> svc.find("license"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("리포지토리");
    }

    @Test
    void 등록된_화면키_목록_8개() {
        assertThat(SimpleScreenService.screenKeys())
                .containsExactlyInAnyOrder("capacity", "license", "alert", "query",
                                          "top_segment", "temp_table", "vacuum", "age");
    }

    @Test
    void query_컬럼_6개_status_텍스트_그대로_전달() {
        SimpleScreenMapper m = mock(SimpleScreenMapper.class);
        when(m.findQuery()).thenReturn(Arrays.asList(
                row("DB ID", 1, "instance_name", "ORACLE19",
                    "plan_status", "OK", "bind_status", "CHECK",
                    "tablespace_status", "OFF", "parameter_status", "OK")));
        ScreenResponse res = serviceWith(m, "Oracle").find("query");
        List<?> cols = res.getColumns();
        assertThat(cols).hasSize(6);
        assertThat(res.getRows().get(0))
                .containsEntry("plan_status", "OK")
                .containsEntry("bind_status", "CHECK")
                .containsEntry("tablespace_status", "OFF");
    }
}
