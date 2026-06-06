package com.exem.inspector.screen.maxspace.dto;

/**
 * ora_tablespace_info latest snapshot + 1주/1개월 사용률 1 행.
 * 원본 tablespace_server.py::get_ts_data 결과 row 1:1.
 *
 * <p>JSON 직렬화 시 snake_case (원본 응답과 정확히 동일). Jackson 의 PropertyNamingStrategies
 * 가 컨트롤러 단에서 적용되지 않으면 @JsonProperty 로 명시.
 */
import com.fasterxml.jackson.annotation.JsonProperty;

public class TablespaceRow {

    @JsonProperty("ts_name")
    private String tsName;

    @JsonProperty("total_gb")
    private Double totalGb;

    @JsonProperty("used_gb")
    private Double usedGb;

    @JsonProperty("used_pct_1w")
    private Double usedPct1w;

    @JsonProperty("used_pct_1m")
    private Double usedPct1m;

    public String getTsName() { return tsName; }
    public void setTsName(String tsName) { this.tsName = tsName; }

    public Double getTotalGb() { return totalGb; }
    public void setTotalGb(Double totalGb) { this.totalGb = totalGb; }

    public Double getUsedGb() { return usedGb; }
    public void setUsedGb(Double usedGb) { this.usedGb = usedGb; }

    public Double getUsedPct1w() { return usedPct1w; }
    public void setUsedPct1w(Double usedPct1w) { this.usedPct1w = usedPct1w; }

    public Double getUsedPct1m() { return usedPct1m; }
    public void setUsedPct1m(Double usedPct1m) { this.usedPct1m = usedPct1m; }
}
