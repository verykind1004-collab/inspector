package com.exem.inspector.screen.maxspace.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * 트렌드 1 데이터 포인트 — (ts_name, snap_day) 단위의 used / total / pct.
 * 원본 tablespace_server.py::get_trend 의 row 1:1 (raw row, 서비스에서 ts_name 기준 grouping).
 */
public class TrendPoint {

    @JsonProperty("ts_name")
    private String tsName;

    @JsonProperty("snap_day")
    private String snapDay;

    @JsonProperty("total_gb")
    private Double totalGb;

    @JsonProperty("used_gb")
    private Double usedGb;

    public String getTsName() { return tsName; }
    public void setTsName(String tsName) { this.tsName = tsName; }

    public String getSnapDay() { return snapDay; }
    public void setSnapDay(String snapDay) { this.snapDay = snapDay; }

    public Double getTotalGb() { return totalGb; }
    public void setTotalGb(Double totalGb) { this.totalGb = totalGb; }

    public Double getUsedGb() { return usedGb; }
    public void setUsedGb(Double usedGb) { this.usedGb = usedGb; }
}
