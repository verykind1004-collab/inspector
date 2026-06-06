package com.exem.inspector.screen.maxspace;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;

/**
 * MaxSpace 전용 스케줄러 구성 — auto_refresh_loop 의 Spring 대응.
 *
 * <p>{@code @EnableScheduling} 으로 어플리케이션 전체에 스케줄러 활성화 + MaxSpace 전용
 * {@link ThreadPoolTaskScheduler} 빈 등록. pool 2 — refresh 1 + warmup 1.
 */
@Configuration
@EnableScheduling
public class MaxSpaceScheduleConfig {

    @Bean(name = "maxSpaceTaskScheduler")
    public ThreadPoolTaskScheduler maxSpaceTaskScheduler() {
        ThreadPoolTaskScheduler scheduler = new ThreadPoolTaskScheduler();
        scheduler.setPoolSize(2);
        scheduler.setThreadNamePrefix("maxspace-");
        scheduler.setDaemon(true);
        scheduler.setWaitForTasksToCompleteOnShutdown(false);
        scheduler.initialize();
        return scheduler;
    }
}
