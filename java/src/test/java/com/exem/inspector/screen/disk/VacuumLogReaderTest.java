package com.exem.inspector.screen.disk;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import com.exem.inspector.config.ServiceConfig;
import com.exem.inspector.config.ServicesBlock;
import com.exem.inspector.screen.overview.DgServerXmlReader;

/**
 * VacuumLogReader 단위 테스트 — 라인 파싱 / log 파일 fallback / 미설정 에러.
 */
class VacuumLogReaderTest {

    private final ServiceConfig serviceConfig = mock(ServiceConfig.class);
    private final DgServerXmlReader xmlReader = mock(DgServerXmlReader.class);
    private final VacuumLogReader reader = new VacuumLogReader(serviceConfig, xmlReader);

    // ── parseVacuumLines 단위 ─────────────────────────────────────────

    @Test
    void parseVacuumLines_matchesStartAndEndPairs() {
        List<String> lines = Arrays.asList(
                "[14:32:10.123] POSTGRESQL VACUUM start schema_name=apm",
                "[14:32:11.456] POSTGRESQL VACUUM end schema_name=apm el=1333ms",
                "[14:32:12.000] POSTGRESQL VACUUM start schema_name=cdb",
                "[14:32:13.500] POSTGRESQL VACUUM end schema_name=cdb el=1500ms"
        );
        List<VacuumLogReader.VacuumLogRow> rows = reader.parseVacuumLines(lines);
        assertThat(rows).hasSize(2);
        assertThat(rows.get(0).getSchema()).isEqualTo("apm");
        assertThat(rows.get(0).getStartTime()).isEqualTo("14:32:10.123");
        assertThat(rows.get(0).getEndTime()).isEqualTo("14:32:11.456");
        assertThat(rows.get(0).getDuration()).isEqualTo("1.333s");
        assertThat(rows.get(1).getSchema()).isEqualTo("cdb");
        assertThat(rows.get(1).getDuration()).isEqualTo("1.500s");
    }

    @Test
    void parseVacuumLines_skipsNonVacuumLines() {
        List<String> lines = Arrays.asList(
                "[14:32:10.000] INFO some other log",
                "[14:32:11.000] POSTGRESQL VACUUM start schema_name=apm",
                "[14:32:11.500] POSTGRESQL VACUUM end schema_name=apm el=500ms"
        );
        assertThat(reader.parseVacuumLines(lines)).hasSize(1);
    }

    @Test
    void parseVacuumLines_handlesEndWithoutStart() {
        List<String> lines = Collections.singletonList(
                "[14:32:11.000] POSTGRESQL VACUUM end schema_name=orphan el=200ms");
        List<VacuumLogReader.VacuumLogRow> rows = reader.parseVacuumLines(lines);
        assertThat(rows).hasSize(1);
        assertThat(rows.get(0).getStartTime()).isEqualTo("-");
        assertThat(rows.get(0).getDuration()).isEqualTo("0.200s");
    }

    @Test
    void parseVacuumLines_emptyOnNoMatch() {
        assertThat(reader.parseVacuumLines(Collections.emptyList())).isEmpty();
    }

    // ── read() — DGM 미설정 ────────────────────────────────────────────

    @Test
    void read_returnsError_whenDgmHomeEmpty() {
        ServicesBlock services = mock(ServicesBlock.class);
        given(services.dgserverM()).willReturn("");
        given(serviceConfig.services()).willReturn(services);

        VacuumLogReader.VacuumLogResult res = reader.read();
        assertThat(res.getError()).contains("DGServer_M 경로가 설정되지 않았습니다");
        assertThat(res.getRows()).isEmpty();
    }

    // ── read() — log 파일 fallback ─────────────────────────────────────

    @Test
    void read_parsesLogFileWhenZipMissing(@TempDir Path tempDir) throws Exception {
        Path dgmHome = tempDir.resolve("dgm");
        Files.createDirectories(dgmHome.resolve("log"));
        Files.createDirectories(dgmHome.resolve("conf"));
        Path logFile = dgmHome.resolve("log").resolve("DGM_5050.log");
        Files.write(logFile, Arrays.asList(
                "[10:00:00.000] POSTGRESQL VACUUM start schema_name=apm",
                "[10:00:00.500] POSTGRESQL VACUUM end schema_name=apm el=500ms"
        ));

        ServicesBlock services = mock(ServicesBlock.class);
        given(services.dgserverM()).willReturn(dgmHome.toString());
        given(serviceConfig.services()).willReturn(services);
        given(xmlReader.readTagValue(dgmHome.resolve("conf").resolve("DGServer.xml"), "gather_port"))
                .willReturn("5050");

        VacuumLogReader.VacuumLogResult res = reader.read();
        assertThat(res.getError()).isNull();
        assertThat(res.getSource()).isEqualTo("DGM_5050.log");
        assertThat(res.getRows()).hasSize(1);
        assertThat(res.getRows().get(0).getSchema()).isEqualTo("apm");
    }

    @Test
    void read_returnsErrorWhenLogFileAndZipBothMissing(@TempDir Path tempDir) {
        Path dgmHome = tempDir.resolve("dgm-empty");
        ServicesBlock services = mock(ServicesBlock.class);
        given(services.dgserverM()).willReturn(dgmHome.toString());
        given(serviceConfig.services()).willReturn(services);
        given(xmlReader.readTagValue(dgmHome.resolve("conf").resolve("DGServer.xml"), "gather_port"))
                .willReturn("5050");

        VacuumLogReader.VacuumLogResult res = reader.read();
        assertThat(res.getError()).startsWith("로그 파일을 찾을 수 없습니다");
    }

    // ── toScreenPayload — 100건 트리밍 + 형식 ─────────────────────────

    @Test
    void toScreenPayload_includesRowsAndSource(@TempDir Path tempDir) throws Exception {
        Path dgmHome = tempDir.resolve("dgm");
        Files.createDirectories(dgmHome.resolve("log"));
        Files.createDirectories(dgmHome.resolve("conf"));
        Path logFile = dgmHome.resolve("log").resolve("DGM_5050.log");
        Files.write(logFile, Arrays.asList(
                "[10:00:00.000] POSTGRESQL VACUUM start schema_name=apm",
                "[10:00:00.500] POSTGRESQL VACUUM end schema_name=apm el=500ms"
        ));
        ServicesBlock services = mock(ServicesBlock.class);
        given(services.dgserverM()).willReturn(dgmHome.toString());
        given(serviceConfig.services()).willReturn(services);
        given(xmlReader.readTagValue(dgmHome.resolve("conf").resolve("DGServer.xml"), "gather_port"))
                .willReturn("5050");

        java.util.Map<String, Object> payload = reader.toScreenPayload();
        assertThat(payload).containsEntry("source", "DGM_5050.log");
        assertThat(payload).containsEntry("error", null);
        @SuppressWarnings("unchecked")
        List<java.util.Map<String, Object>> rows = (List<java.util.Map<String, Object>>) payload.get("rows");
        assertThat(rows).hasSize(1);
        assertThat(rows.get(0)).containsEntry("schema", "apm");
        assertThat(rows.get(0)).containsEntry("duration", "0.500s");
    }
}
