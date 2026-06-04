package com.exem.inspector.screen.simple;

import java.util.LinkedHashMap;
import java.util.Map;

import org.springframework.stereotype.Component;

import com.exem.inspector.common.web.screen.ColumnDef;
import com.exem.inspector.common.web.screen.ColumnRole;
import com.exem.inspector.common.web.screen.ColumnType;
import com.exem.inspector.common.web.screen.ScreenMeta;
import com.exem.inspector.common.web.screen.ScreenResponse;

/**
 * License (Instance List) 응답에 DGS PORT 컬럼 동적 추가 (B-1) — 원본 license.py 와 동등.
 *
 * <p>{@link DgsPortResolver} 가 산정한 {db_id → port} 매핑을 응답 row 마다 dgs_port 컬럼에 채움.
 * 매칭되지 않으면 "-".
 */
@Component
public class LicenseDgsPortEnricher {

    private static final ColumnDef DGS_PORT_COL =
            ColumnDef.of("dgs_port", "DGS Port", ColumnType.STRING, ColumnRole.PLAIN);

    private final DgsPortResolver resolver;

    public LicenseDgsPortEnricher(DgsPortResolver resolver) {
        this.resolver = resolver;
    }

    public ScreenResponse enrich(ScreenResponse src) {
        if (src == null) return null;
        Map<String, String> dgsMap = resolver.resolve();
        ScreenMeta meta = src.getMeta();
        ScreenResponse.Builder b = ScreenResponse.builder(meta.getScreen(), meta.getTitle(), meta.getDbType());
        for (ColumnDef c : src.getColumns()) b.column(c);
        b.column(DGS_PORT_COL);
        for (Map<String, Object> row : src.getRows()) {
            LinkedHashMap<String, Object> r = new LinkedHashMap<>(row);
            Object dbId = r.get("db_id");
            String key = dbId == null ? "" : String.valueOf(dbId);
            r.put("dgs_port", dgsMap.getOrDefault(key, "-"));
            b.rowFromMap(r);
        }
        return b.build();
    }
}
