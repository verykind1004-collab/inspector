#!/usr/bin/env bash
# MaxGauge Inspector Labs — customer-deployable packaging script (신 구조).
#
# 신 구조 기준:
#   - drivers/  가 Labs 직속 (공용)
#   - MaxSpace/ 가 tablespace 대시보드 (예전 Inspector/tablespace + Tablespace/ 통합 후 자리)
#   - PG / Oracle 양쪽 지원
#
# Usage:  ./package_inspector_labs.sh [SRC_LABS_DIR]
# Default SRC = /home/inspector/ORACLE/2407/Labs
# Output     = /home/inspector/release/MaxGauge_Inspector_Labs_YYYYMMDD_HHMMSS.tar.gz
# Side-effect = /home/inspector/INS_FILES/Labs/ 동기화

set -euo pipefail

SRC_LABS="${1:-/home/inspector/ORACLE/2407/Labs}"
REL_DIR="/home/inspector/release"
INS_DIR="/home/inspector/INS_FILES"
TS="$(date +%Y%m%d_%H%M%S)"
OUT_TGZ="${REL_DIR}/MaxGauge_Inspector_Labs_${TS}.tar.gz"

if [ ! -d "$SRC_LABS" ]; then
    echo "[pkg] source Labs not found: $SRC_LABS" >&2
    exit 1
fi
for need in config.yaml Inspector MaxSpace drivers; do
    if [ ! -e "$SRC_LABS/$need" ]; then
        echo "[pkg] source missing '$need' — expected new-structure Labs (drivers + MaxSpace 분리): $SRC_LABS" >&2
        exit 1
    fi
done

mkdir -p "$REL_DIR"

STAGE_ROOT="$(mktemp -d -t inspector_pkg_XXXXXX)"
STAGE="${STAGE_ROOT}/Labs"
trap 'rm -rf "$STAGE_ROOT"' EXIT

echo "[pkg] source : $SRC_LABS"
echo "[pkg] stage  : $STAGE"
echo "[pkg] output : $OUT_TGZ"

# ── 1) clone SRC → stage with runtime/backup exclusions ──────────────────────
rsync -a \
    --exclude='*.bak'   --exclude='*.bak_*'  --exclude='*.bak.*' \
    --exclude='*.backup' --exclude='*.orig'  --exclude='*.swp' \
    --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.pyo' \
    --exclude='.DS_Store' \
    --exclude='Inspector/gateway/nginx.conf' \
    --exclude='Inspector/gateway/log/***' \
    --exclude='Inspector/gateway/tmp/***' \
    --exclude='Inspector/gateway/ssl/server.crt' \
    --exclude='Inspector/gateway/ssl/server.key' \
    --exclude='Inspector/python-utils/log/***' \
    --exclude='Inspector/python-utils/server.log' \
    --exclude='Inspector/python-utils/server.pid' \
    --exclude='MaxSpace/log/***' \
    --exclude='MaxSpace/server.pid' \
    --exclude='MaxSpace/bin/__pycache__/' \
    --exclude='drivers/python3/lib/python3.*/__pycache__/' \
    --exclude='alarm_history_preview.html' \
    "$SRC_LABS/" "$STAGE/"

# ── 2) re-create empty runtime directories ───────────────────────────────────
mkdir -p "$STAGE/Inspector/gateway/log/access"
mkdir -p "$STAGE/Inspector/gateway/tmp/client_temp"
mkdir -p "$STAGE/Inspector/gateway/tmp/proxy_temp"
mkdir -p "$STAGE/Inspector/gateway/tmp/fastcgi_temp"
mkdir -p "$STAGE/Inspector/gateway/tmp/uwsgi_temp"
mkdir -p "$STAGE/Inspector/gateway/tmp/scgi_temp"
mkdir -p "$STAGE/Inspector/gateway/ssl"
mkdir -p "$STAGE/Inspector/python-utils/log/IH"
mkdir -p "$STAGE/MaxSpace/log"
touch "$STAGE/Inspector/gateway/log/access/.gitkeep"
touch "$STAGE/Inspector/gateway/ssl/.gitkeep"
touch "$STAGE/Inspector/python-utils/log/IH/.gitkeep"
touch "$STAGE/MaxSpace/log/.gitkeep"

# ── 3) reset Labs/config.yaml to template ────────────────────────────────────
cat > "$STAGE/config.yaml" << 'YAML'
# MaxGauge Inspector Labs — gateway + python-utils + MaxSpace configuration.
# 고객 환경에 맞춰 포트 / labs.dir 를 조정하세요. MaxGauge PJS 와 충돌하지 않도록.

gateway:
  port: 8080
  ssl_enabled: false
  ssl_port: 8443
  ssl_cert:
  ssl_key:

platformjs:
  port: 8081
  base_path: "/MAXGAUGE"

python_utils:
  port: 8082
  check_path: "/utils"

java:
  # Optional. 절대 경로 (예: /opt/jdk17/bin/java). 비워두면 bash login shell 의
  # JAVA_HOME / PATH 를 통해 자동 탐색합니다.
  path: ""

tablespace:
  port: 8083

# 이 Labs/ 디렉토리의 절대 경로. 설치 시 반드시 채워주세요.
# 예: /home/inspector/ORACLE/2407/Labs
labs:
  dir: ""
YAML

# ── 4) reset service_config.json (Repository / 서비스 경로 비움)
# 2026-05-18 부터 위치가 Labs/ 직속으로 변경됨. 옛 위치(Inspector/python-utils/)
# 파일이 staging 에 있으면 비밀이 노출될 수 있어 제거.
rm -f "$STAGE/Inspector/python-utils/service_config.json"
cat > "$STAGE/service_config.json" << 'JSON'
{
  "repository": {
    "db_type": "Oracle",
    "sid": "",
    "ip": "",
    "port": "",
    "user": "",
    "password": "",
    "pg_home": "",
    "pg_data_dir": ""
  },
  "services": {
    "platformjs": "",
    "dgserver_m": "",
    "dgserver_s": [""]
  },
  "log_paths": {
    "platformjs": "",
    "dgserver_m": "",
    "dgserver_s": [""]
  }
}
JSON

# ── 5) reset insp_config.json ────────────────────────────────────────────────
cat > "$STAGE/Inspector/python-utils/insp_config.json" << 'JSON'
{
  "enabled": false,
  "tables_initialized": false,
  "retention_days": 30,
  "log_retention_days": 10,
  "pg_db": {
    "ip": "",
    "port": "",
    "sid": "",
    "user": "",
    "password": ""
  },
  "pg_schema": "insp"
}
JSON

# ── 6) reset MaxSpace conf — service_config_path 와 db_name 비움 ─────────────
#  service_config_path "" 면 MaxSpace 가 자동으로 Labs/service_config.json 사용 (2026-05-18 위치 변경).
#  refresh_token 은 매 패키지마다 새로 생성 (Inspector ↔ MaxSpace reset hook 용 비밀).
NEW_TOKEN="$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 32)"
cat > "$STAGE/MaxSpace/conf/tablespace_config.json" << JSON
{
  "service_config_path": "",
  "port": 7083,
  "cache_ttl_min": 1440,
  "refresh_hour": 1,
  "refresh_minute": 5,

  "refresh_token":     "${NEW_TOKEN}",

  "___log_config___":  "=== Tablespace Log Config ===",
  "log_file":          "log/server.log",
  "log_max_bytes":     10485760,
  "log_backup_days":   30,
  "log_level":         "INFO"
}
JSON

# ── 7) install guide (Korean) ────────────────────────────────────────────────
cat > "$STAGE/INSTALL.md" << EOF
# MaxGauge Inspector Labs — 설치 가이드

빌드 일시: ${TS}
원본 기준: ORACLE/2407/Labs (Labs/drivers 공용, MaxSpace 통합 신 구조)

## 시스템 요구사항
- Linux x86_64 (RHEL/CentOS 7+, Ubuntu 20.04+, Rocky 등)
- MaxGauge 본 설치 (PJS / DGServer 가동 중)
- 디스크 여유: 300MB 이상
- 인터넷 접속 불필요 — bundled Python 3.11 + bundled nginx 1.26 + oracledb + psycopg2 동봉

## 설치 절차

### 1. 압축 해제
MaxGauge 환경 디렉토리 (예: \`/home/inspector/ORACLE/<sid>/\`) 아래에 풉니다.
\`\`\`bash
cd /home/inspector/ORACLE/<sid>/
tar xzf /path/to/MaxGauge_Inspector_Labs_*.tar.gz
ls Labs/
# config.yaml  drivers/  Inspector/  INSTALL.md  MaxSpace/  maxgauge-labs.html  start.sh  stop.sh
\`\`\`

### 2. \`Labs/config.yaml\` 편집
다음 항목을 환경에 맞게 채웁니다.
- **gateway.port**: Labs 포털 진입 포트
- **platformjs.port**: 실제 PJS 포트 (proxy 대상)
- **python_utils.port**: Inspector 백엔드 포트
- **tablespace.port**: MaxSpace 포트
- **labs.dir**: 이 \`Labs/\` 디렉토리의 **절대 경로** (필수)

SSL 사용 시:
\`\`\`bash
cd Labs/Inspector/gateway
bash gen_ssl_cert.sh   # self-signed 인증서 생성
\`\`\`
그 후 config.yaml 의 \`ssl_enabled: true\` 와 \`ssl_port\` 설정.

### 3. 기동
\`\`\`bash
cd Labs
bash start.sh
\`\`\`
gateway (nginx) → python-utils → MaxSpace 순으로 기동됩니다.
\`bash stop.sh\` 로 일괄 정지.

### 4. 첫 로그인 + Repository DB 설정
브라우저에서 \`http://<server>:<gateway_port>/MAXGAUGE/labs\` 접근.
- 기본 계정: **maxgauge** / 비밀번호는 별도 안내
- 로그인 후 우하단 톱니(설정) → Repository Database 입력 → Save
- MaxSpace 카드에서 tablespace 추이 확인

### 5. (선택) Inspector History 활성화 — INSP 스키마 / 테이블 생성
- 설정 모달 → Inspector History 섹션
- "스키마 생성" → "테이블 생성"
- 이후 30초 간격으로 자동 수집 시작

## 디렉토리 구조
\`\`\`
Labs/
├── config.yaml                  # 포트 / SSL / labs.dir
├── service_config.json          # Repository / 서비스 경로 (Labs UI 에서 편집, 모든 Labs 구성요소 공통 참조)
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
│       ├── insp_config.json
│       ├── pages/
│       └── log/IH/
└── MaxSpace/                    # Tablespace 모니터링 (PG / Oracle 양쪽 지원)
    ├── start.sh / stop.sh       # 단독 기동/정지 (insp_start 가 호출)
    ├── tablespace_dashboard.html
    ├── bin/tablespace_server.py
    ├── conf/tablespace_config.json
    └── log/
\`\`\`

## 동작 요약
- MaxSpace 는 service_config.json 의 Repository Database 정보를 그대로 사용 (별도 설정 불필요).
- Repository 정보 변경 시 자동 풀/캐시 invalidation (lazy + Inspector hook).
- db_type=PostgreSQL: 인스턴스별 schema 의 ora_tablespace_info 사용.
- db_type=Oracle: 접속 user 안의 ora_tablespace_info 사용.

## 문제 해결
- **포트 충돌**: \`ss -tlnp | grep :<port>\`. config.yaml 조정.
- **Java 못 찾음**: config.yaml \`java.path\` 명시. 또는 \`~/.bash_profile\` 의 \`JAVA_HOME\` / \`PATH\`.
- **로그**:
  - \`Labs/Inspector/gateway/log/nginx_error.log\`
  - \`Labs/Inspector/gateway/log/access/<date>_access.log\`
  - \`Labs/Inspector/python-utils/log/python_utils.log\`
  - \`Labs/Inspector/python-utils/log/IH/IH_<date>.log\`
  - \`Labs/MaxSpace/log/server.log\`
- **재기동**: \`bash stop.sh && bash start.sh\` (Labs/ 안에서)
- **Repository DB 접속 실패**: Configuration → Test Connection. 30초 타임아웃.

## 보안 안내
- 기본 계정 비밀번호는 SHA256 해시로 \`Labs/Inspector/python-utils/auth.py\` 에 박혀 있습니다. 변경 절차는 별도 안내.
- gateway 가 외부 노출되는 환경이면 SSL 필수.
- \`service_config.json\` 의 DB 비밀번호는 평문 → \`chmod 600\` 권장.
- \`MaxSpace/conf/tablespace_config.json\` 의 \`refresh_token\` 은 Inspector ↔ MaxSpace 내부 통신용 비밀이므로 외부 노출 금지.
EOF

# ── 8) safety sweep ──────────────────────────────────────────────────────────
find "$STAGE" \( \
        -name '*.bak'      -o -name '*.bak_*'  -o -name '*.bak.*' \
     -o -name '*.backup'   -o -name '*.orig'   -o -name '*.swp' \
     -o -name '__pycache__' -o -name '*.pyc'   -o -name '*.pyo' \
    \) -print -exec rm -rf {} + 2>/dev/null || true

# ── 9) sanity checks (신 구조) ────────────────────────────────────────────────
echo "[pkg] sanity checks..."
test -f "$STAGE/config.yaml"
test -f "$STAGE/start.sh"
test -f "$STAGE/stop.sh"
test -f "$STAGE/maxgauge-labs.html"
test -f "$STAGE/INSTALL.md"
test -d "$STAGE/drivers/python3"
test -x "$STAGE/drivers/python3/bin/python3"
test -f "$STAGE/Inspector/insp_start.sh"
test -f "$STAGE/Inspector/insp_stop.sh"
test -f "$STAGE/Inspector/gateway/nginx.conf.template"
test -x "$STAGE/Inspector/gateway/bin/nginx"
test ! -f "$STAGE/Inspector/gateway/nginx.conf"
test ! -f "$STAGE/Inspector/gateway/ssl/server.crt"
test ! -f "$STAGE/Inspector/gateway/ssl/server.key"
test -f "$STAGE/Inspector/python-utils/Inspector.py"
test -f "$STAGE/service_config.json"
# 옛 위치에 잔재가 남아 있으면 비밀 노출 사고 — 반드시 없어야 함
test ! -f "$STAGE/Inspector/python-utils/service_config.json"
test -f "$STAGE/Inspector/python-utils/insp_config.json"
test -f "$STAGE/MaxSpace/bin/tablespace_server.py"
test -f "$STAGE/MaxSpace/conf/tablespace_config.json"
test -f "$STAGE/MaxSpace/tablespace_dashboard.html"
test -f "$STAGE/MaxSpace/start.sh"
test -f "$STAGE/MaxSpace/stop.sh"
test ! -f "$STAGE/MaxSpace/server.pid"
# 옛 구조 잔재가 들어오면 안 됨
test ! -d "$STAGE/Inspector/tablespace"
test ! -d "$STAGE/Tablespace"
test ! -d "$STAGE/Inspector/python-utils/drivers"

# py_compile main modules
PY="$STAGE/drivers/python3/bin/python3"
"$PY" -m compileall -q "$STAGE/Inspector/python-utils" >/dev/null
"$PY" -m compileall -q "$STAGE/MaxSpace/bin" >/dev/null
echo "[pkg] py_compile OK"
find "$STAGE" -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "$STAGE" -name '*.pyc' -exec rm -f {} + 2>/dev/null || true

# ── 10) tarball ──────────────────────────────────────────────────────────────
tar czf "$OUT_TGZ" -C "$STAGE_ROOT" Labs
SZ="$(du -h "$OUT_TGZ" | awk '{print $1}')"
NFILES="$(tar tzf "$OUT_TGZ" | wc -l)"
SHA="$(sha256sum "$OUT_TGZ" | awk '{print $1}')"
echo "[pkg] tarball: $OUT_TGZ  ($SZ, $NFILES entries)"
echo "[pkg] sha256 : $SHA"

# ── 11) sync STAGE → INS_FILES/Labs ──────────────────────────────────────────
mkdir -p "$INS_DIR"
if [ -d "$INS_DIR/Labs" ]; then
    BAK="$INS_DIR/Labs.bak_${TS}"
    mv "$INS_DIR/Labs" "$BAK"
    echo "[pkg] previous INS_FILES/Labs moved to: $BAK"
fi
rsync -a "$STAGE/" "$INS_DIR/Labs/"
echo "[pkg] INS_FILES/Labs synced from stage."

echo "[pkg] done."
