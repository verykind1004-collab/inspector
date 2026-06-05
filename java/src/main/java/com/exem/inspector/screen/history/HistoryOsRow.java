package com.exem.inspector.screen.history;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * /labs/api/history-os 응답의 단일 row.
 *
 * <p>원본 history_views.py::api_history_os 의 row 1:1 (ts, cpu_pct, cpu_user, cpu_sys, cpu_io,
 * mem_total, mem_used, mem_free, mem_pct). null 허용(_safe 와 동일).
 */
public class HistoryOsRow {

    private final String ts;
    private final Double cpuPct;
    private final Double cpuUser;
    private final Double cpuSys;
    private final Double cpuIo;
    private final Double memTotal;
    private final Double memUsed;
    private final Double memFree;
    private final Double memPct;

    public HistoryOsRow(String ts,
                        Double cpuPct, Double cpuUser, Double cpuSys, Double cpuIo,
                        Double memTotal, Double memUsed, Double memFree, Double memPct) {
        this.ts = ts;
        this.cpuPct = cpuPct;
        this.cpuUser = cpuUser;
        this.cpuSys = cpuSys;
        this.cpuIo = cpuIo;
        this.memTotal = memTotal;
        this.memUsed = memUsed;
        this.memFree = memFree;
        this.memPct = memPct;
    }

    @JsonProperty("ts")        public String getTs()       { return ts; }
    @JsonProperty("cpu_pct")   public Double getCpuPct()   { return cpuPct;  }
    @JsonProperty("cpu_user")  public Double getCpuUser()  { return cpuUser; }
    @JsonProperty("cpu_sys")   public Double getCpuSys()   { return cpuSys;  }
    @JsonProperty("cpu_io")    public Double getCpuIo()    { return cpuIo;   }
    @JsonProperty("mem_total") public Double getMemTotal() { return memTotal;}
    @JsonProperty("mem_used")  public Double getMemUsed()  { return memUsed; }
    @JsonProperty("mem_free")  public Double getMemFree()  { return memFree; }
    @JsonProperty("mem_pct")   public Double getMemPct()   { return memPct;  }
}
