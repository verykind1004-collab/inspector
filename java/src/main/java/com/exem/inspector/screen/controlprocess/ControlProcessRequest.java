package com.exem.inspector.screen.controlprocess;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

/** Start/Stop/Restart 요청 본문. */
@JsonIgnoreProperties(ignoreUnknown = true)
public class ControlProcessRequest {
    private String name;   // e.g. "DGServer_S1" / "DGServer_M" / "PlatformJS"
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
}
