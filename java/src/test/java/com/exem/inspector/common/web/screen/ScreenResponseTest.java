package com.exem.inspector.common.web.screen;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * 표준 표 응답(ScreenResponse) 직렬화 계약 검증.
 *
 * <p>2층 테이블 렌더러가 의존하는 JSON 형태(meta/columns/rows, hidden, role)를 고정한다.
 */
class ScreenResponseTest {

    private final ObjectMapper om = new ObjectMapper();

    @Test
    void 빌더는_컬럼_순서대로_행을_키매핑한다() {
        ScreenResponse res = ScreenResponse.builder("summary_10min", "10Min Summary Check", "ORACLE")
                .column(ColumnDef.of("dbId", "DB ID", ColumnType.NUMBER, ColumnRole.ID))
                .column(ColumnDef.of("status", "Status", ColumnType.STRING, ColumnRole.STATUS))
                .column(ColumnDef.hidden("delayInfo", "Delay", ColumnType.STRING, ColumnRole.DELAY))
                .row(7, "OK", null)
                .build();

        assertThat(res.getMeta().getRowCount()).isEqualTo(1);
        assertThat(res.getColumns()).hasSize(3);
        assertThat(res.getRows().get(0))
                .containsEntry("dbId", 7)
                .containsEntry("status", "OK")
                .containsKey("delayInfo");
    }

    @Test
    void 행_값_개수가_컬럼수와_다르면_거부한다() {
        ScreenResponse.Builder b = ScreenResponse.builder("x", "x", "ORACLE")
                .column(ColumnDef.of("a", "A", ColumnType.STRING, ColumnRole.PLAIN));
        assertThatThrownBy(() -> b.row("v1", "v2"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void JSON_직렬화_형태_고정() throws Exception {
        ScreenResponse res = ScreenResponse.builder("summary_10min", "10Min Summary Check", "ORACLE")
                .column(ColumnDef.of("instanceName", "Instance Name", ColumnType.STRING, ColumnRole.INSTANCE))
                .column(ColumnDef.of("status", "Status", ColumnType.STRING, ColumnRole.STATUS))
                .column(ColumnDef.hidden("delayInfo", "Delay", ColumnType.STRING, ColumnRole.DELAY))
                .row("ORA19", "WAITING", "+1h 30m")
                .build();

        JsonNode root = om.readTree(om.writeValueAsString(res));

        // meta
        assertThat(root.path("meta").path("screen").asText()).isEqualTo("summary_10min");
        assertThat(root.path("meta").path("dbType").asText()).isEqualTo("ORACLE");
        assertThat(root.path("meta").path("rowCount").asInt()).isEqualTo(1);
        assertThat(root.path("meta").path("generatedAt").asText()).isNotEmpty();

        // columns: role / hidden 노출
        JsonNode delayCol = root.path("columns").get(2);
        assertThat(delayCol.path("role").asText()).isEqualTo("DELAY");
        assertThat(delayCol.path("hidden").asBoolean()).isTrue();
        assertThat(root.path("columns").get(1).path("role").asText()).isEqualTo("STATUS");

        // rows: 키 기반 접근
        JsonNode row = root.path("rows").get(0);
        assertThat(row.path("instanceName").asText()).isEqualTo("ORA19");
        assertThat(row.path("status").asText()).isEqualTo("WAITING");
        assertThat(row.path("delayInfo").asText()).isEqualTo("+1h 30m");
    }
}
