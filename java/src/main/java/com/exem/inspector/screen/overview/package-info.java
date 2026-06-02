/**
 * Overview 화면 백엔드 패키지.
 *
 * <p>기존 Python {@code pages/overview.py} 를 1:1 동등 포팅한다(원본 = 정식 2604 라인).
 * 단순 표 화면과 달리 시스템 정보·CPU/Mem/Disk·서비스 상태·테이블스페이스 등
 * 카드형 대시보드라 표준 표 응답(ScreenResponse) 대신 카드별 JSON 페이로드를 반환한다.
 *
 * <p>엔드포인트 (모두 {@code GET /labs/api/overview/...}, ApiResponse 봉투):
 * <ul>
 *   <li>{@code /system} : Hostname·OS·Uptime·Cores (정적 시스템 정보)</li>
 *   <li>{@code /vitals} : CPU + Memory (3초 폴링 대상, 원본 api_vitals 대응)</li>
 *   <li>{@code /disk}   : PG 면 OS 디스크, Oracle 이면 Tablespace 카드 데이터</li>
 *   <li>{@code /services} : 서비스 목록 (DGServer_M/S, PlatformJS, Client, Repo DB)</li>
 * </ul>
 *
 * <p>임계치 UI(WARN/CRIT) 는 프런트 localStorage 책임이며, 백엔드는 status 분류를
 * 기본값(CPU 60/80 · Mem 80/90 · Disk 80/90) 으로 계산해 제공한다(원본 동작).
 *
 * <p>플랫폼 의존 데이터는 {@code ProcReader}(/proc 파일) 와 {@code ShellRunner}
 * (ps/ss 호출) 로 격리한다. Linux 환경 전용이며 미존재 시 안전한 폴백 값 반환.
 */
package com.exem.inspector.screen.overview;
