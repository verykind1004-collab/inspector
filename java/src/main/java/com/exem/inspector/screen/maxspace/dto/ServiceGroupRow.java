package com.exem.inspector.screen.maxspace.dto;

/**
 * ora_service_name × ora_service_info × apm_db_info join 1 행.
 * Service 단에서 service_id 기준 grouping → ServiceGroupView 로 변환.
 * 원본 tablespace_server.py::get_service_groups 의 row 단위 1:1.
 */
public class ServiceGroupRow {

    private Integer serviceId;
    private String serviceName;
    private Integer dbId;
    private String instanceName;

    public Integer getServiceId() { return serviceId; }
    public void setServiceId(Integer serviceId) { this.serviceId = serviceId; }

    public String getServiceName() { return serviceName; }
    public void setServiceName(String serviceName) { this.serviceName = serviceName; }

    public Integer getDbId() { return dbId; }
    public void setDbId(Integer dbId) { this.dbId = dbId; }

    public String getInstanceName() { return instanceName; }
    public void setInstanceName(String instanceName) { this.instanceName = instanceName; }
}
