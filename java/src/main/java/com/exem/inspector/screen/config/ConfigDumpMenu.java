package com.exem.inspector.screen.config;

import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Config Dump 메뉴 정의 — 원본 config_dump.py 의 MENU_DEFS 1:1.
 *
 * <p>5 메뉴 × N tables/sequences. 각 메뉴는 key/label/tables/sequences 4 속성.
 */
public final class ConfigDumpMenu {

    private final String key;
    private final String label;
    private final List<String> tables;
    private final List<String> sequences;

    public ConfigDumpMenu(String key, String label, List<String> tables, List<String> sequences) {
        this.key = key;
        this.label = label;
        this.tables = tables;
        this.sequences = sequences;
    }

    public String getKey() { return key; }
    public String getLabel() { return label; }
    public List<String> getTables() { return tables; }
    public List<String> getSequences() { return sequences; }

    /** 원본 MENU_DEFS 1:1. 키 순서 보존(LinkedHashMap). */
    public static Map<String, ConfigDumpMenu> defaults() {
        Map<String, ConfigDumpMenu> m = new LinkedHashMap<>();
        m.put("instance", new ConfigDumpMenu("instance", "Instance Management",
                Arrays.asList(
                        "ora_service_name", "apm_db_info", "ora_service_info",
                        "ora_lc_config", "ora_rac_group_name", "ora_exa_info",
                        "ora_rule_base_config", "apm_license_db_info", "apm_license_trial_db"),
                Arrays.asList("apm_db_seq", "ora_service_name_seq")));
        m.put("account", new ConfigDumpMenu("account", "Account Management",
                Arrays.asList(
                        "apm_user_list", "apm_users_db_list", "apm_users_ip_list",
                        "apm_web_env", "ora_user_pwd_policy"),
                Collections.<String>emptyList()));
        m.put("alert", new ConfigDumpMenu("alert", "Alert Management",
                Arrays.asList(
                        "apm_alert_server_set", "apm_alert_server_tag_value",
                        "apm_custom_alert_value", "apm_cell_alert_set",
                        "apm_cell_alert_tag_value", "apm_health_set",
                        "apm_health_tag_value", "apm_smart_alert_server_set",
                        "apm_alert_user_sql", "apm_alert_user_script", "ora_alertlog_info"),
                Arrays.asList("apm_alert_user_sql_seq", "apm_alert_user_script_seq")));
        m.put("sms", new ConfigDumpMenu("sms", "SMS Management",
                Arrays.asList(
                        "sms_group_name", "sms_group_info", "sms_user_info",
                        "sms_group_alert_list", "sms_cell_group_alert_list",
                        "apm_alert_sms_schedule", "apm_smart_alert_schedule"),
                Collections.<String>emptyList()));
        m.put("repository", new ConfigDumpMenu("repository", "Repository Configuration",
                Arrays.asList(
                        "apm_partition_manage", "apm_string_data_use_list",
                        "apm_string_data", "ora_app_call_tree_info", "apm_product_option"),
                Collections.<String>emptyList()));
        return Collections.unmodifiableMap(m);
    }
}
