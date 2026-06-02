package com.exem.inspector.screen.alarmhistory;

import java.util.LinkedHashMap;
import java.util.List;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface AlarmHistoryMapper {

    /**
     * 원본 _SQL_ORACLE_ALARM_SEND / _SQL_PG_ALARM_SEND 와 1:1 동등.
     * sel_date 의 sms_flag='1' 알람 — 인스턴스/시간/epoch_ms/유형/이름/값.
     */
    List<LinkedHashMap<String, Object>> findAlarms(@Param("selDate") String selDate);
}
