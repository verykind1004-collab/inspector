package com.exem.inspector.screen.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

import javax.sql.DataSource;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

import com.exem.inspector.config.ServiceConfig;

/**
 * ConfigRestoreService 단위 테스트 — 유효성 검사 + DataSource 미설정 처리.
 *
 * <p>실 DB 동작(Phase1/2 트랜잭션)은 통합 테스트에서 다룬다.
 */
class ConfigRestoreServiceTest {

    @SuppressWarnings("unchecked")
    private final ObjectProvider<DataSource> dataSourceProvider = mock(ObjectProvider.class);
    private final ServiceConfig serviceConfig = mock(ServiceConfig.class);
    private final ConfigRestoreService service =
            new ConfigRestoreService(dataSourceProvider, serviceConfig);

    private Map<String, Object> validDump() {
        Map<String, Object> root = new LinkedHashMap<>();
        Map<String, Object> info = new LinkedHashMap<>();
        info.put("source_db", "10.10.45.68:1521/ORA19 (Oracle)");
        info.put("db_type", "oracle");
        root.put("dump_info", info);
        root.put("tables", Collections.<String, Object>emptyMap());
        root.put("sequences", Collections.<String, Object>emptyMap());
        return root;
    }

    @Test
    void restore_missingTables_throwsIllegalArgument() {
        Map<String, Object> bad = new LinkedHashMap<>();
        bad.put("dump_info", Collections.singletonMap("source_db", "x"));
        assertThatThrownBy(() -> service.restore(bad))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Invalid dump format");
    }

    @Test
    void restore_missingDumpInfo_throwsIllegalArgument() {
        Map<String, Object> bad = new LinkedHashMap<>();
        bad.put("tables", Collections.emptyMap());
        assertThatThrownBy(() -> service.restore(bad))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Invalid dump format");
    }

    @Test
    void restore_nullPayload_throwsIllegalArgument() {
        assertThatThrownBy(() -> service.restore(null))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void restore_noDataSource_throwsIllegalState() {
        given(dataSourceProvider.getIfAvailable()).willReturn(null);
        assertThatThrownBy(() -> service.restore(validDump()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("DB connection failed");
    }

    @Test
    void restoreResult_emptyDumpFields_constructWithoutError() {
        // RestoreResult 자체 구조 — 빈 응답 객체 생성 가능 확인.
        RestoreResult r = new RestoreResult(0,
                Collections.<RestoreTableResult>emptyList(),
                Collections.<Map<String, Object>>emptyList(),
                "src");
        assertThat(r.getTotalInserted()).isZero();
        assertThat(r.getTables()).isEmpty();
        assertThat(r.getSequences()).isEmpty();
        assertThat(r.getSource()).isEqualTo("src");
    }

    @Test
    void restoreTableResult_skipShape() {
        RestoreTableResult t = new RestoreTableResult("apm_db_info", "skip", 0,
                null, null, "no rows", null, null);
        assertThat(t.getStatus()).isEqualTo("skip");
        assertThat(t.getInserted()).isZero();
        assertThat(t.getReason()).isEqualTo("no rows");
        assertThat(t.getColumns()).isNull();
    }
}
