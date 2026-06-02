package com.exem.inspector.screen.overview;

/**
 * Oracle Tablespace overview SQL 의 한 행.
 *
 * <p>원본 _SQL_ORACLE_TABLESPACE_OVERVIEW 결과 컬럼:
 * {@code TABLESPACE_NAME / USED_GB / TOTAL_GB / FREE_GB / PCT} 와 1:1.
 */
public class TablespaceRow {

    private String name;
    private Double usedGb;
    private Double totalGb;
    private Double freeGb;
    private Double percent;

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public Double getUsedGb() { return usedGb; }
    public void setUsedGb(Double usedGb) { this.usedGb = usedGb; }
    public Double getTotalGb() { return totalGb; }
    public void setTotalGb(Double totalGb) { this.totalGb = totalGb; }
    public Double getFreeGb() { return freeGb; }
    public void setFreeGb(Double freeGb) { this.freeGb = freeGb; }
    public Double getPercent() { return percent; }
    public void setPercent(Double percent) { this.percent = percent; }
}
