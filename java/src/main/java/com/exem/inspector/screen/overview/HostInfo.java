package com.exem.inspector.screen.overview;

import java.net.InetAddress;
import java.net.UnknownHostException;

import org.springframework.stereotype.Component;

/**
 * 호스트 식별 정보 제공자.
 *
 * <p>원본 {@code overview.py} 의 {@code socket.gethostname() / platform.system()
 * / platform.release()} 와 1:1 대응. JVM 표준 API 만 사용 → 테스트 가능.
 */
@Component
public class HostInfo {

    /** {@link InetAddress#getLocalHost} 호스트명. 실패 시 "-". */
    public String hostname() {
        try {
            return InetAddress.getLocalHost().getHostName();
        } catch (UnknownHostException e) {
            return "-";
        }
    }

    /** "Linux 5.10.0" 형태 — {@code os.name + " " + os.version}(원본 system + release). */
    public String osDisplay() {
        String name = System.getProperty("os.name", "-");
        String ver  = System.getProperty("os.version", "-");
        return name + " " + ver;
    }
}
