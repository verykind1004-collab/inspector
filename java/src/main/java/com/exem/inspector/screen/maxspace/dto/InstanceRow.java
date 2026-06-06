package com.exem.inspector.screen.maxspace.dto;

/**
 * apm_db_info 1 행 — db_id / instance_name / business_name.
 * 원본 tablespace_server.py::get_instances 1:1.
 */
public class InstanceRow {

    private Integer dbId;
    private String instanceName;
    private String businessName;

    public Integer getDbId() { return dbId; }
    public void setDbId(Integer dbId) { this.dbId = dbId; }

    public String getInstanceName() { return instanceName; }
    public void setInstanceName(String instanceName) { this.instanceName = instanceName; }

    public String getBusinessName() { return businessName; }
    public void setBusinessName(String businessName) { this.businessName = businessName; }
}
