# MaxGauge Inspector Labs

MaxGauge 부가 모니터링 도구 모음 — Inspector (PJS/DGServer 진단·이력), MaxSpace (Tablespace 대시보드), gateway (통합 reverse proxy).

> 사내 코드 리뷰 / 보안 검토용 레포입니다. 실제 배포 산출물은 별도 채널의 tarball 을 통해 전달됩니다.

---

## 디렉토리 구조

```
Labs/
├── config.yaml                       # 포트 / SSL / labs.dir (환경별)
├── start.sh / stop.sh                # 전체 일괄 기동·정지
├── maxgauge-labs.html                # Labs 포털 진입 페이지
├── INSTALL.md                        # 고객사 설치 가이드
├── drivers/                          # 공용 Python 런타임 부트스트랩
│   ├── README.txt
│   └── install.sh                    # python-build-standalone 다운로드
├── Inspector/
│   ├── insp_start.sh / insp_stop.sh
│   ├── gateway/                      # nginx reverse proxy
│   │   ├── nginx.conf.template
│   │   ├── generate_conf.py          # config.yaml → nginx.conf 렌더
│   │   ├── gen_ssl_cert.sh
│   │   ├── reload.sh / start.sh
│   │   └── ssl/                      # 인증서 (사이트별, .gitignore)
│   └── python-utils/                 # FastAPI 백엔드 본체
│       ├── Inspector.py              # 진입점
│       ├── auth.py                   # 인증
│       ├── db_utils.py               # Oracle / PG 커넥션
│       ├── service_config.json       # Repository / 서비스 경로 (템플릿)
│       ├── insp_config.json          # Inspector History 설정 (템플릿)
│       └── pages/                    # 페이지별 라우터·렌더링
└── MaxSpace/                         # Tablespace 대시보드 (단독 HTTP 서버)
    ├── start.sh / stop.sh
    ├── bin/tablespace_server.py
    └── conf/tablespace_config.json   # refresh_token 등 (템플릿)
```

---

## 레포에 포함되지 않은 것

용량 / 라이선스 / 배포 채널 분리 사유로 다음은 트래킹하지 않습니다.

| 항목 | 위치 | 어떻게 채우나 |
|---|---|---|
| **Python 3.11 standalone** | `Labs/drivers/python3/` | `bash Labs/drivers/install.sh` (python-build-standalone 자동 다운로드 + oracledb/psycopg2 설치) |
| **nginx 바이너리 + libs** | `Labs/Inspector/gateway/bin/` | 사내 배포 tarball 또는 별도 빌드. 자체 빌드 시 `nginx-1.26.x` 정적 컴파일 |
| **SSL 인증서** | `Labs/Inspector/gateway/ssl/` | `bash Labs/Inspector/gateway/gen_ssl_cert.sh` (self-signed) 또는 사이트 CA |
| **로그 / PID / tmp** | `*/log/`, `*/tmp/`, `*.pid` | 런타임 자동 생성 |

`package_inspector_labs.sh` 가 위 항목을 포함한 **고객사 배포용 tarball (~49MB)** 을 빌드합니다.

---

## 환경 종속값

모든 환경별 값은 **템플릿에서 빈 문자열** 로 커밋되어 있습니다. 실 운영 값을 채워서 커밋하지 마세요.

| 파일 | 채워야 할 키 |
|---|---|
| `Labs/config.yaml` | `gateway.port`, `platformjs.port`, `python_utils.port`, `tablespace.port`, `labs.dir` |
| `Labs/Inspector/python-utils/service_config.json` | `repository.{ip,port,sid,user,password,db_type}`, `services.*`, `log_paths.*` |
| `Labs/Inspector/python-utils/insp_config.json` | `pg_db.{ip,port,sid,user,password}` (Inspector History 활성 시) |
| `Labs/MaxSpace/conf/tablespace_config.json` | `refresh_token` (빌드 스크립트가 매 빌드마다 새로 생성) |

> `service_config.json` / `insp_config.json` 의 DB 비밀번호는 **평문** 으로 저장됩니다. 운영 머신에서 `chmod 600` 권장. 차후 암호화 모듈 도입 예정.

---

## 로컬 개발 — 빠른 시작

```bash
git clone <this-repo>.git Labs-src
cd Labs-src/Labs

# 1) 공용 Python 부트스트랩 (~3분, 인터넷 필요)
bash drivers/install.sh

# 2) nginx 바이너리는 사내 배포 tarball 에서 복사
#    cp -r /path/to/Inspector_gateway_bin/ Inspector/gateway/bin/

# 3) 환경 설정
vi config.yaml                                          # 포트 + labs.dir
vi Inspector/python-utils/service_config.json           # Repository DB

# 4) 기동
bash start.sh
# → http://localhost:<gateway.port>/MAXGAUGE/labs
```

상세 절차는 [`Labs/INSTALL.md`](./Labs/INSTALL.md) 참고.

---

## 패키지 빌드 (사내 운영)

`package_inspector_labs.sh` 를 실행하면:

1. `/home/inspector/ORACLE/2407/Labs` 에서 staging 복사
2. 환경 종속값 / 시크릿 모두 빈 문자열로 리셋
3. `refresh_token` 새로 생성
4. `__pycache__`, `*.bak*`, `log/`, `*.pid`, SSL 사설키 제외
5. `py_compile` 문법 검증
6. `/home/inspector/release/MaxGauge_Inspector_Labs_<TS>.tar.gz` 생성
7. `/home/inspector/INS_FILES/Labs/` 동기화

```bash
bash package_inspector_labs.sh                                # 기본 (ORACLE/2407)
bash package_inspector_labs.sh /home/inspector/PG/2407/Labs   # 다른 source
```

---

## 보안 이슈 / 기여

- 보안 관련 이슈는 **Private Security Advisory** 로 제출
- 일반 버그 / 제안은 Issues 사용
- PR 전 `bash package_inspector_labs.sh` 가 통과하는지 확인 (py_compile + sanity check)

---

## 라이선스

사내용 — 외부 배포 / 공개 금지.
