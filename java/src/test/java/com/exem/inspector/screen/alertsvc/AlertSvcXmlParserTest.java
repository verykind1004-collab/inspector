package com.exem.inspector.screen.alertsvc;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class AlertSvcXmlParserTest {

    private Path writeXml(Path dir, String body) throws IOException {
        Path p = dir.resolve("sample_sms.xml");
        Files.write(p, body.getBytes(StandardCharsets.UTF_8));
        return p;
    }

    @Test
    void 미존재_파일은_빈_결과() {
        AlertSvcXmlParser.Parsed p = AlertSvcXmlParser.parse(Paths.get("/nonexistent/x.xml"));
        assertThat(p.config).isEmpty();
        assertThat(p.binds).isEmpty();
        assertThat(p.headers).isEmpty();
        assertThat(p.raw).isEmpty();
        assertThat(p.error).isNull();
    }

    @Test
    void 평면_태그_추출(@TempDir Path tmp) throws Exception {
        Path xml = writeXml(tmp,
                "<root>\n" +
                "  <sms_user_id>alice</sms_user_id>\n" +
                "  <sms_send_count>3</sms_send_count>\n" +
                "</root>");
        AlertSvcXmlParser.Parsed p = AlertSvcXmlParser.parse(xml);
        assertThat(p.config).containsEntry("sms_user_id", "alice");
        assertThat(p.config).containsEntry("sms_send_count", "3");
        assertThat(p.raw).contains("sms_user_id");
    }

    @Test
    void bind_파라미터_h와_b_각각_매핑(@TempDir Path tmp) throws Exception {
        Path xml = writeXml(tmp,
                "<root>\n" +
                "  <b0>:alert_type</b0>\n" +
                "  <b1>:resource_name</b1>\n" +
                "  <h0>Content-Type: application/json</h0>\n" +
                "  <h1>Authorization: Bearer X</h1>\n" +
                "</root>");
        AlertSvcXmlParser.Parsed p = AlertSvcXmlParser.parse(xml);
        assertThat(p.binds).containsEntry("b0", ":alert_type");
        assertThat(p.binds).containsEntry("b1", ":resource_name");
        assertThat(p.headers).containsKeys("h0", "h1");
    }

    @Test
    void 다중라인_블록_SUBJECT_DATA_QUERY_CONTENT_추출(@TempDir Path tmp) throws Exception {
        Path xml = writeXml(tmp,
                "<root>\n" +
                "<SUBJECT>알림 [p$alert_type$]</SUBJECT>\n" +
                "<DATA>line1\nline2</DATA>\n" +
                "<CONTENT>a\nb\nc</CONTENT>\n" +
                "<SMS_INSERT_QUERY>INSERT INTO t (a)\nVALUES (:1)</SMS_INSERT_QUERY>\n" +
                "</root>");
        AlertSvcXmlParser.Parsed p = AlertSvcXmlParser.parse(xml);
        assertThat(p.config).containsEntry("SUBJECT", "알림 [p$alert_type$]");
        assertThat(p.config).containsEntry("DATA", "line1\nline2");
        assertThat(p.config).containsEntry("CONTENT", "a\nb\nc");
        assertThat(p.config.get("SMS_INSERT_QUERY")).asString().contains("INSERT INTO t");
    }

    @Test
    void Node_와_sms_database_sid_service_속성(@TempDir Path tmp) throws Exception {
        Path xml = writeXml(tmp,
                "<root>\n" +
                "  <Node>node1</Node>\n" +
                "  <sms_database_sid service=\"ORCL\">orcl</sms_database_sid>\n" +
                "</root>");
        AlertSvcXmlParser.Parsed p = AlertSvcXmlParser.parse(xml);
        assertThat(p.config).containsEntry("rac_node", "node1");
        assertThat(p.config).containsEntry("sms_database_sid_service", "ORCL");
    }

    @Test
    void 자기닫는_태그_속성은_attrs_키로(@TempDir Path tmp) throws Exception {
        Path xml = writeXml(tmp,
                "<root><server host=\"127.0.0.1\" port=\"25\"/></root>");
        AlertSvcXmlParser.Parsed p = AlertSvcXmlParser.parse(xml);
        Object attrs = p.config.get("server_attrs");
        assertThat(attrs).isInstanceOf(Map.class);
        @SuppressWarnings("unchecked")
        Map<String, String> a = (Map<String, String>) attrs;
        assertThat(a).containsEntry("host", "127.0.0.1").containsEntry("port", "25");
    }
}
