# ADR 0001 — 프론트 React SPA 확정 · 풀스택 범위 · UI 공통화 2층

- 상태: 확정 (2026-05-22)
- 관련: CLAUDE.md 0·C·D·G·I절, PROGRESS

## 맥락

핵심 목표(I절)는 "다양한 DB 성능분석 화면을 통일된 UI로 계속 추가하는 확장 플랫폼"이다.
기존 Python의 실패 지점은 공통화 미강제(html_helpers를 안 거쳐 화면마다 UI 제각각)였다.
따라서 "통일된 화면 확장"을 위해 **UI 컴포넌트 공통화 전략이 스택 결정의 핵심**이며, 백엔드만의 문제가 아니다.

프론트엔드 SSR/SPA 결정이 그동안 보류였고, MaxGauge VI 프론트 표준(ClickUp 공유 + 디자인시스템 온보딩 자료)이 수신되어 확정 가능해졌다.

## 결정

1. **프론트 = React SPA** (MaxGauge VI 표준과 통일). 별도 레포(폴리레포).
   - 스택: Vite · TypeScript · TanStack Router/Query · Zustand · Tailwind · Radix UI · FSD · Storybook · Vitest/Playwright · MSW · pnpm.
2. **프로젝트 범위 = 풀스택**. 백엔드(Java/Spring REST API)와 프론트(React SPA)를 **모두 우리가 구축**한다.
3. **UI 공통화 2층**:
   - 1층 = EXEM UI Design System(`@exem-fe/*` npm). 범용 토큰·기본 컴포넌트, 그대로 소비.
   - 2층 = Inspector 전용 공통 컴포넌트. **프론트 레포의 FSD `shared`/`entities` 레이어**에 둔다(DB 테이블 렌더러·인스턴스 필터·사이드바·도움말·FAB·영한 제목).
   - 화면(feature)은 1·2층을 조합만 한다.
4. **백엔드 공통화** = 표준 JSON 응답 스키마(컬럼 메타 + 행 + STATUS/DELAY 도메인 필드). 2층 테이블 렌더러가 일관 소비.

## 근거

- SPA + 디자인시스템(토큰·컴포넌트) + Inspector 2층 + 백엔드 표준 스키마의 조합이, 화면 추가 시 UI/구조 일관성을 구조적으로 강제한다(기존 실패 방지).
- 2층을 프론트 레포 `shared`에 두는 이유: Inspector 도메인에 국한된 자산(범용성 낮음)이라 EXEM 디자인시스템 모노레포에 올리면 결합도·운영 부담 증가. 범용성이 입증되면 그때 1층으로 승격.

## 영향 (폐기/변경)

- 백엔드는 화면(HTML)을 그리지 않는다 → **Thymeleaf/SSR/fragment 계획 폐기**.
- `java/src/main/resources/templates/` **제거**(서버 렌더 템플릿 불요).
- 분석문서 04의 `html_helpers → Thymeleaf 디자인시스템 이식` 계획 폐기. 그 공통요소는 프론트 2층(React)으로 이관.
- 백엔드 인증(2-B에서 구현한 JSON 로그인 + 쿠키 세션 + check-auth)은 SPA와 호환되어 유지. 추가로 CORS 정책 확정 필요.

## 미정 (후속)

- 프론트 레포 위치/원격(TBD).
- 표준 JSON 응답 스키마 상세 설계(첫 화면 실증 시 확정).
- 세션 절대만료, CSRF(SPA 토큰 방식), 쿠키 Secure 등 보안 강화(2-B TODO 연계).
