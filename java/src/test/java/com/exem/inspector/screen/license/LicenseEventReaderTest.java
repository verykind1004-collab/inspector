package com.exem.inspector.screen.license;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class LicenseEventReaderTest {

    @Test
    void 시간_패턴_없으면_null() {
        assertThat(LicenseEventReader.parseLine("LICENSE check OK", "2026-06-02")).isNull();
    }

    @Test
    void valid_1과_VALID_와_true_모두_VALID로_정규화() {
        LicenseEventRow a = LicenseEventReader.parseLine("[10:00:01.123] [LICENSE CHECK] server_id=1 valid=1 desc=OK", "2026-06-02");
        LicenseEventRow b = LicenseEventReader.parseLine("[10:00:02.000] [LICENSE] server_id=2 valid=true", "2026-06-02");
        LicenseEventRow c = LicenseEventReader.parseLine("[10:00:03.000] [LICENSE] server_id=3 valid=VALID", "2026-06-02");
        assertThat(a.getResult()).isEqualTo("VALID");
        assertThat(b.getResult()).isEqualTo("VALID");
        assertThat(c.getResult()).isEqualTo("VALID");
        assertThat(a.getTs()).isEqualTo("2026-06-02 10:00:01");
        assertThat(a.getInstance()).isEqualTo("1");
        assertThat(a.getEvent()).isEqualTo("LICENSE CHECK");
        assertThat(a.getDesc()).isEqualTo("OK");
    }

    @Test
    void valid_0과_false와_INVALID_모두_INVALID로_정규화() {
        assertThat(LicenseEventReader.parseLine("[09:00:00.000] [LICENSE] server_id=1 valid=0", "2026-06-02")
                .getResult()).isEqualTo("INVALID");
        assertThat(LicenseEventReader.parseLine("[09:00:00.000] [LICENSE] server_id=1 valid=false", "2026-06-02")
                .getResult()).isEqualTo("INVALID");
        assertThat(LicenseEventReader.parseLine("[09:00:00.000] [LICENSE] server_id=1 valid=INVALID", "2026-06-02")
                .getResult()).isEqualTo("INVALID");
    }

    @Test
    void server_id_없으면_instance는_dash() {
        LicenseEventRow r = LicenseEventReader.parseLine("[10:00:01.000] [LICENSE]", "2026-06-02");
        assertThat(r.getInstance()).isEqualTo("-");
    }

    @Test
    void desc_없으면_마지막_대괄호_뒤_텍스트가_detail() {
        LicenseEventRow r = LicenseEventReader.parseLine("[10:00:01.000] [LICENSE] tail text here", "2026-06-02");
        assertThat(r.getDesc()).isEqualTo("tail text here");
    }
}
