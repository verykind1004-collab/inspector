package com.exem.inspector.screen.overview;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Socket;

import org.springframework.stereotype.Component;

/**
 * TCP 포트 listen 여부 점검(원본 system_utils._port_is_listening / _check_tcp 와 동등).
 *
 * <p>localhost / 임의 host 대상 timeout connect. 권한 없이도 동작(ss/netstat 보다 안정적).
 */
@Component
public class PortChecker {

    private static final int DEFAULT_TIMEOUT_MS = 300;

    /** localhost:port. timeout 안에 connect 성공 시 true. */
    public boolean isListening(int port) {
        return isListening("127.0.0.1", port, DEFAULT_TIMEOUT_MS);
    }

    /** 주어진 host:port. */
    public boolean isListening(String host, int port, int timeoutMs) {
        if (port <= 0) return false;
        try (Socket s = new Socket()) {
            s.connect(new InetSocketAddress(host, port), timeoutMs);
            return true;
        } catch (IOException e) {
            return false;
        }
    }
}
