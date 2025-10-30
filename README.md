# 📡 PICASO 로그 기반 시퀀스 다이어그램 자동 생성 시스템

## 1. 개요

- **목적**: PICASO 시스템의 로그 데이터를 기반으로 트랜잭션 흐름을 자동 분석하고 시퀀스 다이어그램으로 시각화
- **활용 사례**:
  - 장애 분석 시 호출 흐름 파악
  - 외부 연동 구조 이해
  - 테스트/QA 단계에서 트랜잭션 검증

---

## 2. 아키텍처 구성

```plaintext
[사용자]
   │
   ▼
[Streamlit UI]
   │
   ▼
[로그 업로드 및 트랜잭션 선택]
   │
   ▼
[LLM 기반 분석 파이프라인]
   ├─ Parse 단계 (로그 → 추론된 step JSON)
   └─ Generate 단계 (step JSON → PlantUML 코드)
   │
   ▼
[PlantUML 서버 렌더링]
   │
   ▼
[시퀀스 다이어그램 시각화]
```

---

## 3. 주요 컴포넌트 설명

### 🖥️ Streamlit UI

- 사용자 인터페이스
- 로그 파일 업로드 및 트랜잭션 선택
- 결과 시각화 및 PlantUML 링크 제공

### 🧠 LLM 기반 분석 파이프라인

#### 1. Parse 단계

- 로그를 기반으로 트랜잭션 흐름 추론
- IN-REQ, OUT-REQ, OUT-RES, IN-RES 단계 구성
- 누락된 단계는 `"MISSING"`으로 보완

#### 2. Generate 단계

- 추론된 step을 기반으로 PlantUML 시퀀스 다이어그램 생성
- latency, status, actor/target 정보 포함

### 🔗 Azure OpenAI API

- Azure 기반 GPT 모델 활용
- 시스템 프롬프트를 통해 출력 형식 강제 (JSON / PlantUML)

### 🖼️ PlantUML 서버

- 생성된 PlantUML 코드를 SVG로 렌더링
- 외부 링크로 시퀀스 다이어그램 확인 가능

---

## 4. 기술 스택

| 구성 요소     | 기술/도구                     |
|--------------|-------------------------------|
| UI           | Streamlit                     |
| LLM          | Azure OpenAI (GPT 기반)       |
| 시각화       | PlantUML (SVG 렌더링 서버)    |
| 환경 설정    | dotenv (.env)                 |
| 데이터 처리  | Python (json, base64 등)      |

---

## 5. End-to-End 실행 흐름

1. 사용자 로그 업로드
2. 트랜잭션 선택
3. Parse 프롬프트 생성 → LLM 호출 → step JSON 추출
4. Generate 프롬프트 생성 → LLM 호출 → PlantUML 코드 생성
5. PlantUML 서버로 렌더링 → 시퀀스 다이어그램 시각화

---

## 6. 출력 예시

```plantuml
@startuml
actor "Skylife-API"
participant "PICASO-GW"
Skylife-API -> PICASO-GW : POST /subscribe\n120ms
@enduml
```

---

## 7. 시스템의 장점

- ✅ **자동화**: 복잡한 로그 분석을 LLM이 자동 수행
- ✅ **표준화**: 일관된 시퀀스 다이어그램 포맷 유지
- ✅ **확장성**: 다양한 로그 포맷에 적용 가능
- ✅ **가시성 향상**: 호출 흐름을 시각적으로 표현하여 이해도 향상

---

## 8. 향후 발전 방향

- 🧠 LLM fine-tuning 통한 정확도 향상 
  - RAG 통한 Refine 기능 추가 (API 매핑 정확도 향상, 계약ID기반 흐름 추적)
- 📦 다양한 로그 포맷 지원 (Kafka, DB 트레이스 등)
- 🧩 다중 트랜잭션 병렬 분석 기능
- 📊 시각화 UI 고도화 (다이어그램 내 필터링, 인터랙션)

---

<!--
## 부록

### Refine 기능 
-->
