package com.exem.inspector.screen.controlprocess;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/**
 * MxgrcParser 단위 테스트 — 원본 _parse_mxgrc 1:1 동등 검증.
 *
 * <p>대상: DG_NAME / DG_XMS / DG_XMX / MXG_HOME / OS_TYPE / JAVA_HOME 키.
 */
class MxgrcParserTest {

    private void writeRc(Path home, String content) throws IOException {
        Files.write(home.resolve(".mxgrc"), content.getBytes(StandardCharsets.UTF_8));
    }

    @Test
    void parsesAllKeys(@TempDir Path home) throws IOException {
        writeRc(home, String.join("\n",
                "# comment",
                "",
                "DG_NAME=DGServer_M",
                "DG_XMS=2048",
                "DG_XMX=4096",
                "MXG_HOME=/home/inspector/ORACLE/2604",
                "OS_TYPE=linux64",
                "JAVA_HOME=/usr/java/jdk1.8",
                "UNKNOWN_KEY=skipped",
                ""));

        Map<String, String> m = MxgrcParser.parse(home);
        assertThat(m)
                .containsEntry("DG_NAME", "DGServer_M")
                .containsEntry("DG_XMS", "2048")
                .containsEntry("DG_XMX", "4096")
                .containsEntry("MXG_HOME", "/home/inspector/ORACLE/2604")
                .containsEntry("OS_TYPE", "linux64")
                .containsEntry("JAVA_HOME", "/usr/java/jdk1.8")
                .doesNotContainKey("UNKNOWN_KEY");
    }

    @Test
    void stripsQuotesFromValues(@TempDir Path home) throws IOException {
        writeRc(home, "DG_NAME=\"DGServer_M\"\nDG_XMS='1024'\n");
        Map<String, String> m = MxgrcParser.parse(home);
        assertThat(m.get("DG_NAME")).isEqualTo("DGServer_M");
        assertThat(m.get("DG_XMS")).isEqualTo("1024");
    }

    @Test
    void skipsExportAndPathLines(@TempDir Path home) throws IOException {
        writeRc(home, String.join("\n",
                "export DG_NAME=Skip",
                "alias DG_XMS=Skip",
                "PATH=/x:/y",
                "DG_XMX=4096",
                ""));
        Map<String, String> m = MxgrcParser.parse(home);
        assertThat(m).hasSize(1).containsEntry("DG_XMX", "4096");
    }

    @Test
    void missingFile_returnsEmpty(@TempDir Path home) {
        Map<String, String> m = MxgrcParser.parse(home);
        assertThat(m).isEmpty();
    }

    @Test
    void nullHome_returnsEmpty() {
        Map<String, String> m = MxgrcParser.parse(null);
        assertThat(m).isEmpty();
    }
}
