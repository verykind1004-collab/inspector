package com.exem.inspector.screen.session;

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
 * Session Check 화면 서비스. 매퍼 결과를 표준 표 응답으로 변환한다(I절).
 *
 * <p>컬럼 메타는 화면 고정(2층 렌더러 계약). STATUS/DELAY 없는 단순 표.
 */
@Service
public class SessionService {

    private final ObjectProvider<SessionMapper> mapperProvider;
    private final ServiceConfig serviceConfig;

    public SessionService(ObjectProvider<SessionMapper> mapperProvider, ServiceConfig serviceConfig) {
        this.mapperProvider = mapperProvider;
        this.serviceConfig = serviceConfig;
    }

    public ScreenResponse find() {
        SessionMapper mapper = mapperProvider.getIfAvailable();
        if (mapper == null) {
            throw new IllegalStateException("리포지토리가 설정되지 않았습니다(service_config.json 확인).");
        }
        List<SessionRow> rows = mapper.findSession();

        ScreenResponse.Builder b = ScreenResponse.builder("session", "Session Check", dbTypeName())
                .column(ColumnDef.of("dbId", "DB ID", ColumnType.NUMBER, ColumnRole.ID))
                .column(ColumnDef.of("instanceName", "Instance Name", ColumnType.STRING, ColumnRole.INSTANCE))
                .column(ColumnDef.of("lastTime", "Last Time", ColumnType.DATETIME, ColumnRole.PLAIN));
        for (SessionRow r : rows) {
            b.row(r.getDbId(), r.getInstanceName(), r.getLastTime());
        }
        return b.build();
    }

    private String dbTypeName() {
        return DbType.fromConfigValue(serviceConfig.repository().dbType()).name();
    }
}
