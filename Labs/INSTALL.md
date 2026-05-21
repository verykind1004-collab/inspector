# MaxGauge Inspector Labs — 설치 가이드

빌드 일시: 20260514_134439
원본 기준: ORACLE/2407/Labs (Labs/drivers 공용, MaxSpace 통합 신 구조)

## 시스템 요구사항
- Linux x86_64 (RHEL/CentOS 7+, Ubuntu 20.04+, Rocky 등)
- MaxGauge 본 설치 (PJS / DGServer 가동 중)
- 디스크 여유: 300MB 이상
- 인터넷 접속 불필요 — bundled Python 3.11 + bundled nginx 1.26 + oracledb + psycopg2 동봉

## 설치 절차

### 1. 압축 해제
MaxGauge 환경 디렉토리 (예: `/home/inspector/ORACLE/<sid>/`) 아래에 풉니다.
```bash
cd /home/inspector/ORACLE/<sid>/
tar xzf /path/to/MaxGauge_Inspector_Labs_*.tar.gz
ls Labs/
# config.yaml  drivers/  Inspector/  INSTALL.md  MaxSpace/  maxgauge-labs.html  start.sh  stop.sh
```

### 2. `Labs/config.yaml` 편집
다음 항목을 환경에 맞게 채웁니다.
- **gateway.port**: Labs 포털 진입 포트
- **platformjs.port**: 실제 PJS 포트 (proxy 대상)
- **python_utils.port**: Inspector 백엔드 포트
- **tablespace.port**: MaxSpace 포트
- **labs.dir**: 이 `Labs/` 디렉토리의 **절대 경로** (필수)

SSL 사용 시:
```bash
cd Labs/Inspector/gateway
bash gen_ssl_cert.sh   # self-signed 인증서 생성
```
그 후 config.yaml 의 `ssl_enabled: true` 와 `ssl_port` 설정.

### 3. 기동
```bash
cd Labs
bash start.sh
```
gateway (nginx) → python-utils → MaxSpace 순으로 기동됩니다.
`bash stop.sh` 로 일괄 정지.

### 4. 첫 로그인 + Repository DB 설정
브라우저에서 `http://<server>:<gateway_port>/MAXGAUGE/labs` 접근.
- 기본 계정: **maxgauge** / 비밀번호는 별도 안내
- 로그인 후 우하단 톱니(설정) → Repository Database 입력 → Save
- MaxSpace 카드에서 tablespace 추이 확인

### 5. (선택) Inspector History 활성화 — INSP 스키마 / 테이블 생성
- 설정 모달 → Inspector History 섹션
- "스키마 생성" → "테이블 생성"
- 이후 30초 간격으로 자동 수집 시작

## 디렉토리 구조
```
Labs/
├── config.yaml                  # 포트 / SSL / labs.dir
├── start.sh / stop.sh           # 전체 일괄 기동/정지
├── maxgauge-labs.html           # Labs 포털 (로그인 + 카드)
├── INSTALL.md                   # 이 문서
├── drivers/                     # Labs 공용 bundled Python 3.11 + oracledb + psycopg2
│   └── python3/
├── Inspector/
│   ├── insp_start.sh / insp_stop.sh
│   ├── gateway/                 # bundled nginx 1.26
│   │   ├── bin/nginx, bin/lib/
│   │   ├── nginx.conf.template
│   │   ├── generate_conf.py
│   │   ├── gen_ssl_cert.sh
│   │   ├── ssl/                 # 인증서 위치 (비어있음)
│   │   └── log/access/          # 일별 rotate
│   └── python-utils/            # Inspector 본체
│       ├── Inspector.py
│       ├── service_config.json  # Repository / 서비스 경로 (Labs UI 에서 편집)
│       ├── insp_config.json
│       ├── pages/
│       └── log/IH/
└── MaxSpace/                    # Tablespace 모니터링 (PG / Oracle 양쪽 지원)
    ├── start.sh / stop.sh       # 단독 기동/정지 (insp_start 가 호출)
    ├── tablespace_dashboard.html
    ├── bin/tablespace_server.py
    ├── conf/tablespace_config.json
    └── log/
```

## 동작 요약
- MaxSpace 는 service_config.json 의 Repository Database 정보를 그대로 사용 (별도 설정 불필요).
- Repository 정보 변경 시 자동 풀/캐시 invalidation (lazy + Inspector hook).
- db_type=PostgreSQL: 인스턴스별 schema 의 ora_tablespace_info 사용.
- db_type=Oracle: 접속 user 안의 ora_tablespace_info 사용.

## 문제 해결
- **포트 충돌**: `ss -tlnp | grep :<port>`. config.yaml 조정.
- **Java 못 찾음**: config.yaml `java.path` 명시. 또는 `~/.bash_profile` 의 `JAVA_HOME` / `PATH`.
- **로그**:
  - `Labs/Inspector/gateway/log/nginx_error.log`
  - `Labs/Inspector/gateway/log/access/<date>_access.log`
  - `Labs/Inspector/python-utils/log/python_utils.log`
  - `Labs/Inspector/python-utils/log/IH/IH_<date>.log`
  - `Labs/MaxSpace/log/server.log`
- **재기동**: `bash stop.sh && bash start.sh` (Labs/ 안에서)
- **Repository DB 접속 실패**: Configuration → Test Connection. 30초 타임아웃.

## 보안 안내
- 기본 계정 비밀번호는 SHA256 해시로 `Labs/Inspector/python-utils/auth.py` 에 박혀 있습니다. 변경 절차는 별도 안내.
- gateway 가 외부 노출되는 환경이면 SSL 필수.
- `service_config.json` 의 DB 비밀번호는 평문 → `chmod 600` 권장.
- `MaxSpace/conf/tablespace_config.json` 의 `refresh_token` 은 Inspector ↔ MaxSpace 내부 통신용 비밀이므로 외부 노출 금지.
