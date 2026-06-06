package com.exem.inspector.screen.maxspace;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Date;

import javax.annotation.PostConstruct;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.scheduling.Trigger;
import org.springframework.scheduling.TriggerContext;
import org.springframework.stereotype.Component;

/**
 * MaxSpace 백그라운드 작업 — 원본 tablespace_server.py 의 warmup_trends + auto_refresh_loop 1:1.
 *
 * <p>실행 시점:
 * <ul>
 *   <li>startup ({@code @PostConstruct}): warmup 1 회 (async, build_data 실패 무시)</li>
 *   <li>매일 {@code refresh_hour:refresh_minute} (기본 01:05):
 *       캐시 invalidate → build_data → warmup → 다음 day 재등록</li>
 * </ul>
 *
 * <p>{@link Trigger} 의 nextExecutionTime 으로 config 변경 시 다음 회차부터 즉시 반영.
 * fixedDelay/cron 보다 동적 시간 처리 깔끔.
 */
@Component
public class MaxSpaceScheduler {

    private static final Logger log = LoggerFactory.getLogger(MaxSpaceScheduler.class);
    private static final DateTimeFormatter F_DTM = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    private final MaxSpaceService service;
    private final MaxSpaceConfig config;
    private final TaskScheduler scheduler;

    public MaxSpaceScheduler(MaxSpaceService service,
                             MaxSpaceConfig config,
                             @Qualifier("maxSpaceTaskScheduler") TaskScheduler scheduler) {
        this.service = service;
        this.config = config;
        this.scheduler = scheduler;
    }

    @PostConstruct
    public void init() {
        // 1) 비동기 warmup 1 회 — Repository 미구성 시 자동 skip.
        scheduler.schedule(this::warmupSilent, Instant.now().plusSeconds(2));

        // 2) auto_refresh_loop — refresh_hour:refresh_minute 마다 반복.
        scheduler.schedule(this::runAutoRefresh, new RefreshTrigger());
        log.info("[maxspace] 스케줄러 등록 완료");
    }

    private void warmupSilent() {
        try {
            service.warmupTrends();
        } catch (Exception e) {
            log.warn("[maxspace.warmup] startup warmup 실패 (Repository 미설정?): {}", e.toString());
        }
    }

    private void runAutoRefresh() {
        log.info("[maxspace.auto-refresh] 캐시 갱신 시작...");
        try {
            service.refresh();             // 캐시 invalidate + 재빌드
            service.warmupTrends();        // 모든 instance 트렌드 pre-warm
            log.info("[maxspace.auto-refresh] 완료");
        } catch (Exception e) {
            log.error("[maxspace.auto-refresh] 오류: {}", e.toString());
        }
    }

    /**
     * refresh_hour:refresh_minute 까지 대기하는 Trigger. config 변경 시 다음 회차부터 적용.
     */
    private final class RefreshTrigger implements Trigger {
        @Override
        public Date nextExecutionTime(TriggerContext ctx) {
            LocalDateTime now = LocalDateTime.now();
            LocalDateTime target = now.withHour(config.getRefreshHour())
                    .withMinute(config.getRefreshMinute()).withSecond(0).withNano(0);
            if (!now.isBefore(target)) {
                target = target.plusDays(1);
            }
            log.info("[maxspace.auto-refresh] 다음 갱신 예정: {}", target.format(F_DTM));
            return Date.from(target.atZone(ZoneId.systemDefault()).toInstant());
        }
    }
}
