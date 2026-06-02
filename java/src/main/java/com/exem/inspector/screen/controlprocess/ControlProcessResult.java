package com.exem.inspector.screen.controlprocess;

/** 액션 결과 — ok + 사람이 읽을 메시지(원본 (bool, str) 튜플과 동등). */
public class ControlProcessResult {
    private final boolean ok;
    private final String message;
    public ControlProcessResult(boolean ok, String message) {
        this.ok = ok;
        this.message = message;
    }
    public boolean isOk() { return ok; }
    public String getMessage() { return message; }
}
