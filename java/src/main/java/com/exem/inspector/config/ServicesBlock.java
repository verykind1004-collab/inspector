package com.exem.inspector.config;

import java.util.ArrayList;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * service_config.json 의 services 블록 매핑.
 *
 * <p>원본 Python overview.py 의 svc.get("services", {}) 구조와 동일:
 * {@code dgserver_m: str, dgserver_s: List<str>, platformjs: str}.
 * 미설정 키는 빈 값으로 둔다 — overview Services 카드가 graceful 처리.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public class ServicesBlock {

    @JsonProperty("dgserver_m")
    private String dgserverM = "";

    @JsonProperty("dgserver_s")
    private List<String> dgserverS = new ArrayList<>();

    @JsonProperty("platformjs")
    private String platformjs = "";

    public String dgserverM() { return dgserverM == null ? "" : dgserverM; }
    public List<String> dgserverS() { return dgserverS == null ? new ArrayList<>() : dgserverS; }
    public String platformjs() { return platformjs == null ? "" : platformjs; }
}
