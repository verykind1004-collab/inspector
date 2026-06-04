package com.exem.inspector.screen.dgxml;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import com.exem.inspector.config.ServiceConfig;
import com.exem.inspector.config.ServicesBlock;

/**
 * DgxmlService 단위 테스트 — XML 파싱 + 검색 + 저장 (백업/comment 토글/value 변경).
 */
class DgxmlServiceTest {

    private final ServiceConfig serviceConfig = mock(ServiceConfig.class);
    private final DgxmlService service = new DgxmlService(serviceConfig);

    private void wireServices(String dgm, List<String> dgs) {
        ServicesBlock sb = mock(ServicesBlock.class);
        given(sb.dgserverM()).willReturn(dgm == null ? "" : dgm);
        given(sb.dgserverS()).willReturn(dgs == null ? Collections.emptyList() : dgs);
        given(serviceConfig.services()).willReturn(sb);
    }

    private Path writeXml(Path home, String content) throws IOException {
        Path conf = home.resolve("conf");
        Files.createDirectories(conf);
        Path xml = conf.resolve("DGServer.xml");
        Files.write(xml, content.getBytes(StandardCharsets.UTF_8));
        return xml;
    }

    // ── parseAll — DGServer.xml 파싱 ─────────────────────────────────
    @Test
    void parseAll_extractsEnabledAndDisabled(@TempDir Path tmp) throws IOException {
        Path home = tmp.resolve("dgm");
        writeXml(home, String.join("\n",
                "<root>",
                "  <gather_port>3000</gather_port>",
                "  <!-- <database_sid>old_sid</database_sid> -->",
                "  <database_sid service=\"false\">PGN</database_sid>",
                "</root>"));
        wireServices(home.toString(), Collections.emptyList());

        List<DgxmlService.DgxmlFile> files = service.parseAll();
        assertThat(files).hasSize(1);
        DgxmlService.DgxmlFile f = files.get(0);
        assertThat(f.dgserver).isEqualTo("DGServer_M");
        assertThat(f.error).isNull();
        assertThat(f.params).extracting(DgxmlService.DgxmlParam::getKey)
                .contains("gather_port", "database_sid");
        // gather_port = enabled, database_sid (commented) = disabled, database_sid (enabled)
        long disabled = f.params.stream().filter(DgxmlService.DgxmlParam::getIsDisabled).count();
        assertThat(disabled).isGreaterThanOrEqualTo(1);
    }

    @Test
    void parseAll_missingFile_recordsError(@TempDir Path tmp) {
        wireServices(tmp.resolve("nope").toString(), Collections.emptyList());
        List<DgxmlService.DgxmlFile> files = service.parseAll();
        assertThat(files).hasSize(1);
        assertThat(files.get(0).error).isEqualTo("File not found");
    }

    @Test
    void parseAll_multipleHomes(@TempDir Path tmp) throws IOException {
        Path m = tmp.resolve("m");
        Path s1 = tmp.resolve("s1");
        writeXml(m, "<root><a>1</a></root>");
        writeXml(s1, "<root><b>2</b></root>");
        wireServices(m.toString(), Arrays.asList(s1.toString()));

        List<DgxmlService.DgxmlFile> files = service.parseAll();
        assertThat(files).hasSize(2);
        assertThat(files).extracting(DgxmlService.DgxmlFile::getDgserver)
                .containsExactly("DGServer_M", "DGServer_S1");
    }

    // ── search ───────────────────────────────────────────────────────
    @Test
    void search_emptyParam_returnsError() {
        DgxmlService.SearchResult r = service.search("");
        assertThat(r.isOk()).isFalse();
        assertThat(r.getError()).isEqualTo("Empty parameter name");
    }

    @Test
    void search_noDgServers_returnsError() {
        wireServices("", Collections.emptyList());
        DgxmlService.SearchResult r = service.search("gather_port");
        assertThat(r.isOk()).isFalse();
        assertThat(r.getError()).isEqualTo("No DGServer configured");
    }

    @Test
    void search_found_enable(@TempDir Path tmp) throws IOException {
        Path home = tmp.resolve("dgm");
        writeXml(home, "<root><gather_port>4521</gather_port></root>");
        wireServices(home.toString(), Collections.emptyList());

        DgxmlService.SearchResult r = service.search("gather_port");
        assertThat(r.isOk()).isTrue();
        assertThat(r.getResults()).hasSize(1);
        assertThat(r.getResults().get(0).getStatus()).isEqualTo("Enable");
        assertThat(r.getResults().get(0).getValue()).isEqualTo("4521");
    }

    @Test
    void search_notFound(@TempDir Path tmp) throws IOException {
        Path home = tmp.resolve("dgm");
        writeXml(home, "<root><gather_port>4521</gather_port></root>");
        wireServices(home.toString(), Collections.emptyList());

        DgxmlService.SearchResult r = service.search("missing_param");
        assertThat(r.isOk()).isTrue();
        assertThat(r.getResults().get(0).getStatus()).isEqualTo("Not Found");
        assertThat(r.getResults().get(0).getValue()).isEqualTo("-");
    }

    // ── save — value 변경 + 백업 ────────────────────────────────────
    @Test
    void save_value_modifies_and_backups(@TempDir Path tmp) throws IOException {
        Path home = tmp.resolve("dgm");
        Path xml = writeXml(home, "<root>\n  <gather_port>3000</gather_port>\n</root>\n");
        wireServices(home.toString(), Collections.emptyList());

        DgxmlService.SaveRequest req = new DgxmlService.SaveRequest();
        DgxmlService.ChangeItem ci = new DgxmlService.ChangeItem();
        ci.setXmlfile(xml.toString());
        ci.setParam("gather_port");
        ci.setValue("5000");
        req.setChanges(Collections.singletonList(ci));

        DgxmlService.SaveResult r = service.save(req);
        assertThat(r.isOk()).isTrue();
        assertThat(r.getResults()).hasSize(1);
        assertThat(r.getResults().get(0).getStatus()).isEqualTo("ok");
        assertThat(r.getResults().get(0).getBackup()).startsWith("DGServer.xml.bak_");

        String updated = new String(Files.readAllBytes(xml), StandardCharsets.UTF_8);
        assertThat(updated).contains("<gather_port>5000</gather_port>");
    }

    @Test
    void save_disable_wrapsComment(@TempDir Path tmp) throws IOException {
        Path home = tmp.resolve("dgm");
        Path xml = writeXml(home, "<root>\n  <feature>on</feature>\n</root>\n");
        wireServices(home.toString(), Collections.emptyList());

        DgxmlService.SaveRequest req = new DgxmlService.SaveRequest();
        DgxmlService.ChangeItem ci = new DgxmlService.ChangeItem();
        ci.setXmlfile(xml.toString());
        ci.setParam("feature");
        ci.setStatus("Disable");
        req.setChanges(Collections.singletonList(ci));

        DgxmlService.SaveResult r = service.save(req);
        assertThat(r.getResults().get(0).getStatus()).isEqualTo("ok");
        String updated = new String(Files.readAllBytes(xml), StandardCharsets.UTF_8);
        assertThat(updated).contains("<!--<feature>on</feature>-->");
    }

    @Test
    void save_emptyChanges_returnsError() {
        DgxmlService.SaveRequest req = new DgxmlService.SaveRequest();
        req.setChanges(Collections.emptyList());
        DgxmlService.SaveResult r = service.save(req);
        assertThat(r.isOk()).isFalse();
        assertThat(r.getError()).isEqualTo("No changes provided");
    }

    @Test
    void save_nullRequest_returnsError() {
        DgxmlService.SaveResult r = service.save(null);
        assertThat(r.isOk()).isFalse();
    }

    @Test
    void save_missingFile_recordsError(@TempDir Path tmp) {
        DgxmlService.SaveRequest req = new DgxmlService.SaveRequest();
        DgxmlService.ChangeItem ci = new DgxmlService.ChangeItem();
        ci.setXmlfile(tmp.resolve("nope.xml").toString());
        ci.setParam("x");
        ci.setValue("1");
        req.setChanges(Collections.singletonList(ci));
        DgxmlService.SaveResult r = service.save(req);
        assertThat(r.isOk()).isTrue();
        assertThat(r.getResults().get(0).getStatus()).isEqualTo("error");
        assertThat(r.getResults().get(0).getMessage()).contains("File not found");
    }

    @Test
    void save_noChangeFields_returnsNoChange(@TempDir Path tmp) throws IOException {
        Path home = tmp.resolve("dgm");
        Path xml = writeXml(home, "<root><x>1</x></root>");
        DgxmlService.SaveRequest req = new DgxmlService.SaveRequest();
        DgxmlService.ChangeItem ci = new DgxmlService.ChangeItem();
        ci.setXmlfile(xml.toString());
        ci.setParam("x");
        // no status, no value, no action
        req.setChanges(Collections.singletonList(ci));
        DgxmlService.SaveResult r = service.save(req);
        assertThat(r.getResults().get(0).getStatus()).isEqualTo("no_change");
    }
}
