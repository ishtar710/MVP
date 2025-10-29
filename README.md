# PICASO-Trace2UML
MS AI 과제

> 트랜잭션ID/코릴레이션ID 기반 호출 로그/트레이스에서 단계·시스템 라벨을 자동 추출하여 PlantUML/Mermaid 시퀀스 다이어그램을 생성하고, 실패 지점/대안흐름(재시도·타임아웃 등)을 시각화한다. 실서비스 연동 없이 샘플/추출 로그만으로 동작하는 파일럿이다.
> - 시스템 호출 로그 기반 시퀀스다이어그램 자동생성   
> - 온보딩/분석 가시성 제고   

---

## 서비스 범위

* 범위 : Skylife/HCN 가입·조회 플로우 중 1~2개 대표 시나리오.   
API GW/WAS 로그(또는 OpenTelemetry 추출본) 업로드 → 단일 페이지 UI에서 다이어그램 생성/내보내기.
* 비범위 : 실시간 스트리밍, 전체 모니터링 대체, 모든 시스템 포괄 자동화.

---

## 문제정의
| 문제 | 상세 설명 |
|------|-----------|
|복잡한 서비스 흐름|서비스 가입의 경우 kt 미디어플랫폼 시스템의 주요 시스템 6종을 연동하여 하나의 결과값을 리턴하는 것으로, 프로비저닝까지 하고 있어 전체적인 서비스 흐름은 한 눈에 파악하기 어려움|
|현행화 괸리|잦은 변화에 따른...|

---

## 아키텍처
```plaintext
[사용자] ──(브라우저)──> [Trace2UML Web UI]
                            └── 업로드: ZIP(logs) / JSON(trace)
                                │
                                ▼
                        [FastAPI 백엔드]
                ┌────────────┬───────────────┬─────────────┐
                │ Parser     │ Correlator    │ Enricher    │
                └─────┬──────┴─────┬─────────┴─────┬───────┘
                      ▼            ▼               ▼
                [Event Bus] → [Step Builder] → [LLM Labeler]
                                             │      │
                                             │      └→ [RAG KB]
                                             ▼
                                    [Diagram Builder]
                            (PlantUML/Mermaid 템플릿)
                                             ▼
                                    [Renderer/Exporter]
                            (PNG/SVG/MD, Confluence Export)

```

---

### 구성요소
| 구성 요소 | 역할 |
|-----------|------|
| **LLM** | 로그의 의미 해석, API 호출 간 관계 추론, 시퀀스 다이어그램 텍스트 생성 (예: PlantUML) |
| **RAG** | 시스템 구조 문서, API 명세서, 연동 흐름 문서 등과 연계하여 정확도 향상 |
| **Embedding** | 로그 벡터화 → 유사 흐름 군집화, 이상 흐름 탐지, 추천 흐름 제공 |


---

## 입력데이터 & 마스킹
### 입력 포맷(샘플 허용)
* API GW Access Log: NGINX/Envoy 포맷(+ X-Correlation-Id)   
* WAS App Log (JSON): timestamp, level, transactionid, spanId, service, endpoint, status, latencyMs, error   
* OpenTelemetry(선택): traceId, spanId, parentSpanId, attributes{peer.service, http.method, http.route, status}
### 마스킹 규칙(파일럿)
~~* 주민/전화/계약ID: 포맷보존 토큰화(FPE) 또는 해시+솔트(sha256(id+salt)[:10]).~~   
~~* 주소: 시/군/구까지 유지, 상세주소 토큰화.   
Payload: 바디 전체 저장 금지, 필드명·길이·타입 메타만 유지.~~

---
## 처리파이프라인
* Parsing: 포맷 감지(정규식/JSON), 필드 추출, 시간 파싱+타임스큐 보정.   
* Correlation: corr_id|trace_id 기준 그룹핑, 누락 시 휴리스틱(동일 TCP/5초 창·IP·UA)을 보조.   
* Normalization: 상기 스키마로 맵핑, 내부/파트너 명칭 매핑 테이블 적용.   
* Patterning: 리트라이/백오프(지수 간격), 타임아웃(504/TimeoutException), Circuit Open, Partial Success 감지.   
* Step Builder: 동일 Actor→Target, 동일 엔드포인트 호출을 단일 Step으로 압축(요약: 평균·P95 지연, 시도 횟수).   
* LLM Labeling: Step 요약문/의도 라벨(예: "가입자 정보 검증", "주소 정합성 체크") 생성.   
* Diagram Builder: 템플릿에 Actor/Step/노트/P95 지연 삽입.   
Render/Export: PlantUML/Mermaid → PNG/SVG, MD/Confluence 내보내기.

---
## RAG 지식베이스(??)
- **콘텐츠 소스(샘플)**: 내부 시스템 설명 1p 요약, 엔드포인트 정의표, 에러코드 사전, 용어집.
- **백엔드**: **Azure AI Search** 벡터 인덱스(예: `kb-trace2uml`), HNSW 기반, cosine 유사도.
- **스키마(제안)**: `id, chunk, embedding, system, endpoint, error_code, version, source_ref`
- **임베딩 단위**: 300~600 토큰 청크, 메타(`system, endpoint, error_code`).
- **질의 유형**:
  - "`/address/validate` 는 무슨 역할?" → **라벨링 근거**
  - "`E-104` 에러는?" → **실패 노트 텍스트**

---
## LLM 프롬프트(요약)
### Step 요약/라벨링 프롬프트 (KOR)
```
당신은 API 호출 로그를 읽고, 각 호출 묶음을 1줄 요약과 행위 라벨로 분류합니다.
입력: {actor, target, endpoint, method, count, p50, p95, status_dist, error_top}
RAG 참고: {endpoint 설명, 용어집, 에러코드 설명}
출력 JSON 스키마:
{
  "label": "주소 정합성 검증",
  "summary": "AddressSvc에 주소 검증 요청. 2회 재시도, 최종 성공",
  "annotations": ["retry:2","p95:420ms","err:E-104"]
}
규칙: 제품명/사내약어는 용어집 표기 준수, 모호하면 RAG 근거 인용.
```

### 다이어그램 생성 프롬프트 (KOR)
```
다음 Step 배열을 PlantUML 시퀀스로 변환하세요. 배우자 이름은 매핑테이블을 우선.
입력: [{actor, target, summary, label, p95, retries, error_note, raw_refs[]}]
출력: PlantUML 코드. 실패/재시도는 note 또는 rect로 강조. 각 Step에 p95를 표기.
```

---

## API 설계(파일럿)
- `POST /api/upload` : ZIP/JSON 업로드 → `dataset_id` (Streamlit에서 `st.file_uploader`로 업로드 후 백엔드 호출)
- `GET /api/correlations?dataset_id=...` : 코릴레이션 목록
- `POST /api/diagram` : {dataset_id, corr_id, format: "plantuml|mermaid", options{ showAlt:true }} → 코드
- `POST /api/render` : {format:"plantuml|mermaid", code} → {png/svg}
- `GET /api/source?ref=...` : 원본 로그 라인 반환(마스킹 적용)

**Streamlit 연동 포인트**
- 업로드 → 세션 상태에 `dataset_id` 저장 → 선택 UI → `/api/diagram` 호출 → 코드/PNG 표시
- [Export] 버튼에서 Blob 업로드 및 Confluence 내보내기 호출(사내 정책에 맞춘 토큰/웹훅)

---

## UI/UX 초안 (streamlit)
- 상단: `st.file_uploader`로 파일 업로드 → 데이터셋 선택(Selectbox)
- 좌측: 코릴레이션ID 리스트(`st.dataframe`/검색 필터)
- 중앙: 다이어그램 미리보기(`st.image` PNG or `st.code` PlantUML/Mermaid)
- 우측: Step 패널(라벨·요약·p95·재시도·근거 링크)
* 하단: [Export PNG] [Export SVG] [Copy PlantUML]

### 부록 A. 샘플 로그 (축약)
```
2025-10-20T13:45:12Z gw INFO cid=8f3c... method=POST path=/subscriptions status=200 t=120ms
{"ts":"2025-10-20T13:45:12.200Z","traceId":"a1b2","spanId":"01","service":"orchestrator","endpoint":"/address/validate","status":504,"latencyMs":800,"error":"TimeoutException"}
```

### 부록 B. 평가 체크리스트 (발췌)
- [ ] 배우자/대상 라벨 매핑 정확
- [ ] Step 경계 타당
- [ ] 실패 원인 설명이 에러코드 사전과 일치
- [ ] p95 지연 표기 적절
- [ ] 라운드트립 링크 동작


### 부록 C. 로그 파일 구조 및 파싱 규칙(상세)
- 트랜잭션 구분은 **transactionId** 기반이며, 배너 Start/End와 헤더/바디/메시지 내 키를 종합해 식별한다.
- 이벤트 유형 태그: HTTP_REQUEST_HEADER / HTTP_REQUEST_BODY / DECRYPTED_BODY / CODE_MAPPING / EXT_API_PATH / EXT_HTTP_REQ_* / EXT_HTTP_RTT / EXT_HTTP_RESP / SOAP_XML_REQ/RESP / SYS_ERROR / META.
- 추가 정규화 필드: txId, interfaceId(GPV010x), route(JOIN|STOP), actor(API-GW|GPV|MEIN|UCEMS|NCRAB), payloadRef(blob uri).
- 민감정보 마스킹 원칙: 이름 마지막 1–2자 마스킹, 주소는 시/군/구까지만, Authorization은 접두사만 보존, 다양한 *_id 값은 토큰화.
- 키 정규화 예시: transactionid→transactionId, x-ghubpv-rst-cd→rstCode.

### 부록 D. 샘플 파서 사용법(요약)
- 입력: 샘플 로그(.log/.txt). 형식 A/B(컨테이너 기본 패턴, GPV 커스텀 패턴) 모두 지원.
- 처리: 라인별 파싱 → transactionId 추출/그룹핑 → 이벤트 유형 태깅 → 민감정보 마스킹 → 정규화 이벤트(JSON) 출력.
- 출력: JSON Lines(`parsed_events.jsonl`) + 요약(`transactions_summary.json`).
- 사용 흐름: 업로드된 로그 → 파서 실행 → 정규화 산출물 업로드(Blob) → Trace2UML 파이프라인으로 전달.

### 🎯 기대 효과 정리

- 📉 **장애 분석 속도 향상**: 장애 발생 시 흐름 자동 시각화로 원인 파악 시간 단축
- 🧩 **신규 기능 설계 지원**: 기존 흐름과 유사한 시퀀스 추천으로 설계 효율화
- 🤝 **운영-개발 커뮤니케이션 개선**: 시각화된 흐름으로 협업 용이
- 🧠 **지식 자산화**: 로그 기반 흐름을 문서화하여 조직 내 기술 자산 축적

---

### 🌱 확장 아이디어

- 🔍 **이상 흐름 탐지**: 정상 시퀀스와 다른 흐름 자동 탐지 및 알림
- 🧪 **테스트 시나리오 자동 생성**: 시퀀스 기반 테스트 케이스 추출
- 🧭 **API 호출 시뮬레이터**: 시퀀스 다이어그램 기반 API 호출 시뮬레이션
