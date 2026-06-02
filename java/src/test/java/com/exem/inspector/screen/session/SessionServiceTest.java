package com.exem.inspector.screen.session;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.util.Arrays;
import java.util.Collections;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

import com.exem.inspector.common.db.RepositoryConfig;
import com.exem.inspector.common.web.screen.ColumnRole;
import com.exem.inspector.common.web.screen.ScreenResponse;
import com.exem.inspector.config.ServiceConfig;

class SessionServiceTest {

    @SuppressWarnings("unchecked")
    private SessionService serviceWith(SessionMapper mapper, String dbType) {
        ObjectProvider<SessionMapper> provider = mock(ObjectProvider.class);
        when(provider.getIfAvailable()).thenReturn(mapper);

        RepositoryConfig repo = mock(RepositoryConfig.class);
        when(repo.dbType()).thenReturn(dbType);
        ServiceConfig cfg = mock(ServiceConfig.class);
        when(cfg.repository()).thenReturn(repo);

        return new SessionService(provider, cfg);
    }

    private SessionRow row(Integer id, String inst, String last) {
        SessionRow r = new SessionRow();
        r.setDbId(id); r.setInstanceName(inst); r.setLastTime(last);
        return r;
    }

    @Test
    void 매퍼행을_표준응답으로_변환_3컬럼() {
        SessionMapper mapper = mock(SessionMapper.class);
        when(mapper.findSession()).thenReturn(Arrays.asList(
                row(1, "ORACLE19", "2026-06-02 10:50:00"),
                row(2, "ORA21C",   "2026-06-02 10:30:00")));

        ScreenResponse res = serviceWith(mapper, "Oracle").find();

        assertThat(res.getMeta().getScreen()).isEqualTo("session");
        assertThat(res.getMeta().getDbType()).isEqualTo("ORACLE");
        assertThat(res.getMeta().getRowCount()).isEqualTo(2);
        assertThat(res.getColumns()).hasSize(3);
        assertThat(res.getColumns().get(1).getRole()).isEqualTo(ColumnRole.INSTANCE);
        assertThat(res.getRows().get(0))
                .containsEntry("dbId", 1)
                .containsEntry("instanceName", "ORACLE19")
                .containsEntry("lastTime", "2026-06-02 10:50:00");
    }

    @Test
    void 미설정이면_예외() {
        SessionService svc = serviceWith(null, "Oracle");
        assertThatThrownBy(svc::find).isInstanceOf(IllegalStateException.class);
    }

    @Test
    void 빈_결과도_정상() {
        SessionMapper mapper = mock(SessionMapper.class);
        when(mapper.findSession()).thenReturn(Collections.emptyList());
        ScreenResponse res = serviceWith(mapper, "Oracle").find();
        assertThat(res.getRows()).isEmpty();
        assertThat(res.getColumns()).hasSize(3);
    }
}
