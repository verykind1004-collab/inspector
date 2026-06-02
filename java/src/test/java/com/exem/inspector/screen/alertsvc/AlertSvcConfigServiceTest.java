package com.exem.inspector.screen.alertsvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Collections;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import com.exem.inspector.config.ServiceConfig;
import com.exem.inspector.config.ServicesBlock;

class AlertSvcConfigServiceTest {

    /** JDK 8 호환: Files.readString 대용. */
    private static String readStr(Path p) throws IOException {
        return new String(Files.readAllBytes(p), StandardCharsets.UTF_8);
    }

    private AlertSvcConfigService svcWith(Path... dgserverDirs) {
        ServicesBlock services = mock(ServicesBlock.class);
        when(services.dgserverS()).thenReturn(
                Arrays.stream(dgserverDirs).map(Path::toString).collect(java.util.stream.Collectors.toList()));
        ServiceConfig cfg = mock(ServiceConfig.class);
        when(cfg.services()).thenReturn(services);
        return new AlertSvcConfigService(cfg);
    }

    /** {@code <dgserver>/svc} 디렉토리를 만들고 그 안에 (옵션) xml 두 종을 둔다. */
    private Path mkDgServer(Path root, String name, String activeXml, String sampleXml) throws IOException {
        Path dg = root.resolve(name);
        Path svc = dg.resolve("svc");
        Files.createDirectories(svc);
        if (activeXml != null) Files.write(svc.resolve("sms.xml"), activeXml.getBytes(StandardCharsets.UTF_8));
        if (sampleXml != null) Files.write(svc.resolve("sample_sms.xml"), sampleXml.getBytes(StandardCharsets.UTF_8));
        return dg;
    }

    @Test
    void read_여러_dgserver_순회_active와_inactive_혼합(@TempDir Path tmp) throws Exception {
        Path s1 = mkDgServer(tmp, "S1", "<active/>", "<sample/>");          // active
        Path s2 = mkDgServer(tmp, "S2", null, "<sample-only/>");             // inactive

        AlertSvcReadResult r = svcWith(s1, s2).read(AlertSvcKind.SMS);
        assertThat(r.getKind()).isEqualTo("sms");
        assertThat(r.getResults()).hasSize(2);
        assertThat(r.getResults().get(0).getDgserver()).isEqualTo("DGServer_S1");
        assertThat(r.getResults().get(0).isActive()).isTrue();
        assertThat(r.getResults().get(0).getRaw()).contains("active");
        assertThat(r.getResults().get(1).getDgserver()).isEqualTo("DGServer_S2");
        assertThat(r.getResults().get(1).isActive()).isFalse();
        assertThat(r.getResults().get(1).getRaw()).contains("sample-only");
    }

    @Test
    void read_dgserver_미설정시_IllegalState(@TempDir Path tmp) {
        AlertSvcConfigService svc = svcWith();
        assertThatThrownBy(() -> svc.read(AlertSvcKind.SMS))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("No DGServer_S configured");
    }

    @Test
    void read_kind_null_차단() {
        AlertSvcConfigService svc = svcWith();
        assertThatThrownBy(() -> svc.read(null))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void save_active_상태에서_rawXml_저장하면_active_파일_덮어쓰고_백업_생성(@TempDir Path tmp) throws Exception {
        Path s1 = mkDgServer(tmp, "S1", "<old-active/>", "<sample/>");
        AlertSvcConfigService svc = svcWith(s1);

        AlertSvcSaveRequest req = new AlertSvcSaveRequest();
        req.setKind("sms");
        req.setSvcDir(s1.resolve("svc").toString());
        req.setRawXml("<new-active/>");

        AlertSvcSaveResult res = svc.save(req);
        assertThat(res.getResults()).anyMatch(s -> s.startsWith("Backup:"));
        assertThat(res.getResults()).anyMatch(s -> s.contains("XML saved: sms.xml"));
        assertThat(readStr(s1.resolve("svc/sms.xml"))).isEqualTo("<new-active/>");
        // 백업 1건 이상 존재.
        assertThat(Files.list(s1.resolve("svc"))
                .anyMatch(p -> p.getFileName().toString().startsWith("sms.xml.bak_"))).isTrue();
    }

    @Test
    void save_inactive_상태에서_activate_true_면_sample을_active로_복사(@TempDir Path tmp) throws Exception {
        Path s1 = mkDgServer(tmp, "S1", null, "<sample/>");
        Path svc1 = s1.resolve("svc");
        // .jar / .unit 도 sample_ 형태로 존재 시 activate 시 같이 복사되는지 검증.
        Files.write(svc1.resolve("sample_sms.jar"), "j".getBytes());
        Files.write(svc1.resolve("sample_sms.unit"), "u".getBytes());

        AlertSvcConfigService svc = svcWith(s1);
        AlertSvcSaveRequest req = new AlertSvcSaveRequest();
        req.setKind("sms");
        req.setSvcDir(svc1.toString());
        req.setActivate(true);

        AlertSvcSaveResult res = svc.save(req);
        assertThat(Files.exists(svc1.resolve("sms.xml"))).isTrue();
        assertThat(Files.exists(svc1.resolve("sms.jar"))).isTrue();
        assertThat(Files.exists(svc1.resolve("sms.unit"))).isTrue();
        assertThat(res.getResults()).anyMatch(s -> s.contains("activated"));
    }

    @Test
    void save_active_상태에서_activate_false_면_active_파일들_삭제하고_sample은_유지(@TempDir Path tmp) throws Exception {
        Path s1 = mkDgServer(tmp, "S1", "<active/>", "<sample/>");
        Path svc1 = s1.resolve("svc");
        Files.write(svc1.resolve("sms.jar"), "j".getBytes());
        Files.write(svc1.resolve("sms.unit"), "u".getBytes());

        AlertSvcConfigService svc = svcWith(s1);
        AlertSvcSaveRequest req = new AlertSvcSaveRequest();
        req.setKind("sms");
        req.setSvcDir(svc1.toString());
        req.setActivate(false);

        svc.save(req);
        assertThat(Files.exists(svc1.resolve("sms.xml"))).isFalse();
        assertThat(Files.exists(svc1.resolve("sms.jar"))).isFalse();
        assertThat(Files.exists(svc1.resolve("sms.unit"))).isFalse();
        assertThat(Files.exists(svc1.resolve("sample_sms.xml"))).isTrue();
    }

    @Test
    void save_미존재_디렉토리_IllegalArgument(@TempDir Path tmp) {
        AlertSvcConfigService svc = svcWith();
        AlertSvcSaveRequest req = new AlertSvcSaveRequest();
        req.setKind("sms");
        req.setSvcDir(tmp.resolve("nope/svc").toString());
        req.setRawXml("<x/>");
        assertThatThrownBy(() -> svc.save(req))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("svc dir not found");
    }

    @Test
    void copy_여러_타겟에_일괄_복사_백업포함(@TempDir Path tmp) throws Exception {
        Path t1 = mkDgServer(tmp, "T1", "<old/>", "<sample/>");
        Path t2 = mkDgServer(tmp, "T2", null, "<sample2/>");
        AlertSvcConfigService svc = svcWith();

        AlertSvcCopyRequest req = new AlertSvcCopyRequest();
        req.setKind("sms");
        req.setRawXml("<new/>");
        req.setTargetSvcDirs(Arrays.asList(t1.resolve("svc").toString(), t2.resolve("svc").toString()));
        req.setActivate(null);

        AlertSvcCopyResult r = svc.copy(req);
        assertThat(r.isAllOk()).isTrue();
        assertThat(r.getResults()).hasSize(2);
        assertThat(readStr(t1.resolve("svc/sms.xml"))).isEqualTo("<new/>");        // active 였으니 active 갱신
        assertThat(readStr(t2.resolve("svc/sample_sms.xml"))).isEqualTo("<new/>"); // inactive 였으니 sample 갱신
    }

    @Test
    void copy_빈_타겟_또는_빈_XML_차단() {
        AlertSvcConfigService svc = svcWith();

        AlertSvcCopyRequest a = new AlertSvcCopyRequest();
        a.setKind("sms");
        a.setRawXml("");
        a.setTargetSvcDirs(Collections.singletonList("/x"));
        assertThatThrownBy(() -> svc.copy(a)).isInstanceOf(IllegalArgumentException.class);

        AlertSvcCopyRequest b = new AlertSvcCopyRequest();
        b.setKind("sms");
        b.setRawXml("<x/>");
        b.setTargetSvcDirs(Collections.emptyList());
        assertThatThrownBy(() -> svc.copy(b)).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void copy_미존재_target_단건은_error_status(@TempDir Path tmp) {
        AlertSvcConfigService svc = svcWith();
        AlertSvcCopyRequest req = new AlertSvcCopyRequest();
        req.setKind("sms");
        req.setRawXml("<x/>");
        req.setTargetSvcDirs(Collections.singletonList(tmp.resolve("nope/svc").toString()));

        AlertSvcCopyResult r = svc.copy(req);
        assertThat(r.isAllOk()).isFalse();
        assertThat(r.getResults()).hasSize(1);
        assertThat(r.getResults().get(0).getStatus()).isEqualTo("error");
        assertThat(r.getResults().get(0).getMessage()).contains("not found");
    }
}
