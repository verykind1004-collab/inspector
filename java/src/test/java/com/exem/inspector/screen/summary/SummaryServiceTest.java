package com.exem.inspector.screen.summary;

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

/**
 * SummaryService 변환 로직 검증 — 매퍼 행 → 표준 표 응답, 미설정 시 예외.
 */
class SummaryServiceTest {

    @SuppressWarnings("unchecked")
    private SummaryService serviceWith(SummaryMapper mapper, String dbType) {
        ObjectProvider<SummaryMapper> provider = mock(ObjectProvider.class);
        when(provider.getIfAvailable()).thenReturn(mapper);

        RepositoryConfig repo = mock(RepositoryConfig.class);
        when(repo.dbType()).thenReturn(dbType);
        ServiceConfig cfg = mock(ServiceConfig.class);
        when(cfg.repository()).thenReturn(repo);

        return new SummaryService(provider, cfg);
    }

    private SummaryRow row(Integer id, String inst, String type, String last, String status, String delay) {
        SummaryRow r = new SummaryRow();
        r.setDbId(id);
        r.setInstanceName(inst);
        r.setSummaryType(type);
        r.setLastSummary(last);
        r.setStatus(status);
        r.setDelayInfo(delay);
        return r;
    }

    @Test
    void 매퍼행을_표준표응답으로_변환한다() {
        SummaryMapper mapper = mock(SummaryMapper.class);
        when(mapper.findSummary10Min()).thenReturn(Arrays.asList(
                row(1, "ORA19", "10Min Summary", "2026-05-22 09:50:00", "OK", null),
                row(2, "ORA21", "10Min Summary", "2026-05-22 09:30:00", "WAITING", "+0h 20m")));

        ScreenResponse res = serviceWith(mapper, "Oracle").summary10Min();

        assertThat(res.getMeta().getScreen()).isEqualTo("summary_10min");
        assertThat(res.getMeta().getDbType()).isEqualTo("ORACLE");
        assertThat(res.getMeta().getRowCount()).isEqualTo(2);

        // 컬럼 계약: 6개, 마지막 delay 는 hidden + DELAY, status 는 STATUS
        assertThat(res.getColumns()).hasSize(6);
        assertThat(res.getColumns().get(5).isHidden()).isTrue();
        assertThat(res.getColumns().get(5).getRole()).isEqualTo(ColumnRole.DELAY);
        assertThat(res.getColumns().get(4).getRole()).isEqualTo(ColumnRole.STATUS);

        // 행 키매핑
        assertThat(res.getRows().get(1))
                .containsEntry("dbId", 2)
                .containsEntry("instanceName", "ORA21")
                .containsEntry("status", "WAITING")
                .containsEntry("delayInfo", "+0h 20m");
    }

    @Test
    void 리포지토리_미설정이면_예외() {
        SummaryService svc = serviceWith(null, "Oracle"); // 매퍼 미가용
        assertThatThrownBy(svc::summary10Min)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("리포지토리");
    }

    @Test
    void 빈_결과도_정상_응답() {
        SummaryMapper mapper = mock(SummaryMapper.class);
        when(mapper.findSummary1Hour()).thenReturn(Collections.emptyList());

        ScreenResponse res = serviceWith(mapper, "Oracle").summary1Hour();

        assertThat(res.getMeta().getScreen()).isEqualTo("summary_1hour");
        assertThat(res.getMeta().getRowCount()).isZero();
        assertThat(res.getRows()).isEmpty();
        assertThat(res.getColumns()).hasSize(6);
    }
}
