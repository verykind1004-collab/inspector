package com.exem.inspector.screen.summary;

import java.util.List;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

import com.exem.inspector.common.db.DbType;
import com.exem.inspector.common.web.screen.ColumnDef;
import com.exem.inspector.common.web.screen.ColumnRole;
import com.exem.inspector.common.web.screen.ColumnType;
import com.exem.inspector.common.web.screen.ScreenResponse;
import com.exem.inspector.config.ServiceConfig;

/**
 * Summary Check 화면 서비스. 매퍼 결과를 표준 표 응답으로 변환한다.
 *
 * <p>I절 규약: 화면이 SQL/커넥션을 직접 다루지 않고, 컬럼 메타(렌더러 계약)는 화면이 고정한다.
 * 리포지토리 미설정 시 SummaryMapper 빈이 없을 수 있어 ObjectProvider 로 선택 주입하고,
 * 미설정이면 명확한 예외로 알린다(Controller 가 ApiResponse.error 로 변환).
 */
@Service
public class SummaryService {

    private final ObjectProvider<SummaryMapper> mapperProvider;
    private final ServiceConfig serviceConfig;

    public SummaryService(ObjectProvider<SummaryMapper> mapperProvider, ServiceConfig serviceConfig) {
        this.mapperProvider = mapperProvider;
        this.serviceConfig = serviceConfig;
    }

    public ScreenResponse summary10Min() {
        return toScreen("summary_10min", "10Min Summary Check", mapper().findSummary10Min());
    }

    public ScreenResponse summary1Hour() {
        return toScreen("summary_1hour", "1Hour Summary Check", mapper().findSummary1Hour());
    }

    private SummaryMapper mapper() {
        SummaryMapper m = mapperProvider.getIfAvailable();
        if (m == null) {
            throw new IllegalStateException("리포지토리가 설정되지 않았습니다(service_config.json 확인).");
        }
        return m;
    }

    private String dbTypeName() {
        return DbType.fromConfigValue(serviceConfig.repository().dbType()).name();
    }

    /** 매퍼 행 목록 → 표준 표 응답. 컬럼 메타는 화면 고정(2층 렌더러 계약). */
    private ScreenResponse toScreen(String screen, String title, List<SummaryRow> rows) {
        ScreenResponse.Builder b = ScreenResponse.builder(screen, title, dbTypeName())
                .column(ColumnDef.of("dbId", "DB ID", ColumnType.NUMBER, ColumnRole.ID))
                .column(ColumnDef.of("instanceName", "Instance Name", ColumnType.STRING, ColumnRole.INSTANCE))
                .column(ColumnDef.of("summaryType", "Summary Type", ColumnType.STRING, ColumnRole.GROUP))
                .column(ColumnDef.of("lastSummary", "Last Summary", ColumnType.DATETIME, ColumnRole.PLAIN))
                .column(ColumnDef.of("status", "Status", ColumnType.STRING, ColumnRole.STATUS))
                .column(ColumnDef.hidden("delayInfo", "Delay", ColumnType.STRING, ColumnRole.DELAY));
        for (SummaryRow r : rows) {
            b.row(r.getDbId(), r.getInstanceName(), r.getSummaryType(),
                    r.getLastSummary(), r.getStatus(), r.getDelayInfo());
        }
        return b.build();
    }
}
