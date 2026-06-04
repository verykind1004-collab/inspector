package com.exem.inspector.config;

import java.util.ArrayList;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * service_config.json 의 log_paths 블록 매핑.
 *
 * <p>원본 Python 의 {@code svc.get("log_paths", {})}: DGServer 의 log 디렉토리 경로.
 * services 의 home 디렉토리와 분리된다 — Gather 탭의 DGM/DGS 로그 뷰가 사용.
 * 미설정 키는 빈 값으로 둔다.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public class LogPathsBlock {

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
