import streamlit as st
import json, requests, re
from typing import List, Dict, Any
from openai import AzureOpenAI
from dotenv import load_dotenv
import os
import plantuml

# .env 파일에서 환경변수 로드
load_dotenv()
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_DEPLOYMENT_MODEL = os.getenv("AZURE_DEPLOYMENT_MODEL")

# Azure Search 설정
SEARCH_ENDPOINT = os.getenv("SEARCH_ENDPOINT")
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY")
SEARCH_INDEX = os.getenv("SEARCH_INDEX")


# OpenAI 클라이언트 초기화 
try:
    # Initialize the OpenAI client
    openai_client = AzureOpenAI(
        api_version="2024-12-01-preview",
        api_key=AZURE_OPENAI_API_KEY,
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )
except Exception as e:
    st.error(f"OpenAI 클라이언트 초기화 오류: {e}")
    st.stop()

# 함수: Parse 프롬프트 생성
def build_parse_prompt(trace_logs: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    LLM Parse 단계에 넣을 프롬프트 메시지 생성
    - 반드시 JSON만 반환하도록 지시
    """
    return [
        {
            "role": "system",
            "content": (
                "당신은 PICASO 로그를 시퀀스 다이어그램 step으로 변환하는 분석기입니다.\n"
                "출력은 반드시 JSON만 반환해야 하며, 다른 설명이나 텍스트를 포함하지 마십시오.\n"
                "JSON 이외의 텍스트(예: 설명, 주석)는 절대 출력하지 마십시오. ``` 으로 시작하는 코드 블록도 포함하지 마십시오."
            )
        },
        {
            "role": "user",
            "content": f"""
아래는 동일 transactionId에 속하는 로그 항목들입니다.
이를 기반으로 IN-REQ → OUT-REQ → OUT-RES → IN-RES step을 추론하여 JSON으로 반환하시오.

규칙:
1. 각 트랜잭션은 반드시 IN-REQ → OUT-REQ → OUT-RES → IN-RES 순서로 구성된다.
   - IN-REQ/IN-RES는 각각 하나만 존재한다.
   - OUT-REQ/OUT-RES는 여러 개 존재할 수 있다.
   - 중간 step이 누락될 수 있으며, 이 경우 "MISSING" step으로 채운다.

2. 로그에는 REQ가 기록되지 않고 RES 로그만 남는다.
   - logType=IN_RES → IN-REQ + IN-RES를 추론해야 한다.
   - logType=OUT_RES → OUT-REQ + OUT-RES를 추론해야 한다.

3. 매핑 규칙:
   - IN-REQ의 actor는 caller(외부 시스템), target은 PICASO.
   - OUT-REQ의 actor는 PICASO, target은 OUT-RES의 destination.
   - OUT-RES의 actor는 OUT-REQ의 target(즉, 외부 시스템), target은 PICASO.
   - IN-RES의 actor는 PICASO, target은 IN-REQ의 actor(즉, caller).
   - caller 정보는 최초 요청(IN-REQ)부터 IN-RES까지 동일하게 연결된다.
   - IN-RES의 destination과 OUT-REQ의 호출자는 항상 PICASO로 고정한다.

4. status와 latency_ms:
   - status는 response.code를 사용한다. 없으면 response.type으로 유추(E→500, I→200).
   - latency_ms는 response.duration을 정수로 변환한다. 없으면 -1.

출력 스키마:
{{
  "trace_id": "트랜잭션ID",
  "steps": [
    {{
      "step_no": 1,
      "type": "IN-REQ",
      "actor": "...",
      "action": "...",
      "target": "...",
      "status": "...",
      "latency_ms": 123
    }},
    ...
  ]
}}

입력 로그:
{json.dumps(trace_logs, ensure_ascii=False, indent=2)}
"""
        }
    ]


def get_embedding(text):
    url = f"{AZURE_OPENAI_ENDPOINT}openai/deployments/dev-text-embedding-ada-002/embeddings?api-version=2023-05-15"
    headers = {
        "api-key": AZURE_OPENAI_API_KEY,
        "Content-Type": "application/json"
    }
    body = {
        "input": text
    }
    # print("==== get_embedding 호출 ====")
    # print(url, headers, body)
    response = requests.post(url, headers=headers, json=body)
    # print("==== get_embedding 응답 ====")
    # print(response.text)
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]

def search_description_by_embedding(embedding):
    url = f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}/docs/search?api-version=2023-10-01-Preview"
    headers = {
        "api-key": SEARCH_API_KEY,
        "Content-Type": "application/json"
    }
    body = {
        "vectorQueries": [
            {
                "kind": "vector",
                "vector": embedding,
                "fields": "text_vector",
                "k": 1
            }
        ],
        "select": "chunk,title"
    }
    # print("==== search_description_by_embedding 호출 ====")
    # print(url, headers, body)
    response = requests.post(url, headers=headers, json=body)
    # print("==== search_description_by_embedding 응답 ====")
    # print(response.text)
    response.raise_for_status()
    # print("==== search_description_by_embedding 완료 ====")
    results = response.json()["value"]
    if results:
        return results[0]["chunk"]
    return "설명을 찾을 수 없습니다."

def summarize_description(text):
    if not text or len(text) < 30:
        return text  # 짧은 설명은 그대로 유지

    # 1. 오류 코드 추출
    error_codes = re.findall(r'GPV\d{4}', text)
    unique_codes = sorted(set(error_codes))

    # 2. 시스템 이름 추출
    systems = re.findall(r'(MRSS|UCEMS|NCRAB|MEIN|GTBS|BATCH|SICS|GHUB)', text)
    unique_systems = sorted(set(systems))

    # 3. 요약 문장 생성
    summary_parts = []
    if unique_codes:
        summary_parts.append(f"{len(unique_codes)}개 오류코드 감지됨 ({', '.join(unique_codes[:3])}...)")
    if unique_systems:
        summary_parts.append(f"연동 시스템: {', '.join(unique_systems)}")

    return " / ".join(summary_parts) if summary_parts else "오류 목록 포함"

def refine_descriptions(refined_json):
    for step in refined_json.get("steps", []):
        original = step.get("description", "")
        step["description"] = summarize_description(original)
    return refined_json

def refine_api_descriptions(parsed_json):
    for step in parsed_json.get("steps", []):
        action = step.get("action")
        if action:
            embedding = get_embedding(action)
            raw_description = search_description_by_embedding(embedding)
            summarized = summarize_description(raw_description)
            step["description"] = summarized
    # print("==== refine_api_descriptions 완료 ====")
    # print(parsed_json)
    return parsed_json


# 함수: PlantUML 생성 프롬프트 (수정본: PlantUML 코드만 반환 강제)
def build_generate_prompt(refined_steps: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    LLM Generate 단계에 넣을 프롬프트 메시지 생성
    - 반드시 PlantUML 코드 블록만 반환하도록 강제
    """
    return [
        {
            "role": "system",
            "content": (
                "당신은 시퀀스 다이어그램(PlantUML) 생성기입니다.\n"
                "출력은 반드시 PlantUML 코드(@startuml ... @enduml)만 반환해야 하며, "
                "설명이나 주석, JSON, ``` 코드블록 등 다른 텍스트를 포함하지 마십시오."
            )
        },
        {
            "role": "user",
            "content": f"""
아래 refined_steps를 기반으로 시퀀스 다이어그램을 PlantUML 코드로 변환하시오.

규칙:
- 각 고유 actor/participant는 actor 또는 participant로 선언
- 각 화살표 라벨에 latency_ms 포함 (예: "POST /subscribe\\n120ms")
- status가 4xx/5xx인 step은 해당 화살표 뒤에 #red 색상 주석 추가
- confidence 같은 메타 정보는 PlantUML 주석("' ...")으로만 표시
- IN-REQ, OUT-REQ는 화살표 -> , IN-RES, OUT-RES는 화살표 --> 사용.
- 출력은 반드시 @startuml ... @enduml 블록만 반환

입력:
{json.dumps(refined_steps, ensure_ascii=False, indent=2)}

출력 예시:
@startuml
actor "Skylife-API"
participant "PICASO-GW"
Skylife-API -> PICASO-GW : POST /subscribe\\n120ms
@enduml
"""
        }
    ]

# 함수: OpenAI 호출 
def call_openai(messages):
 
    response = openai_client.chat.completions.create(
        model=AZURE_DEPLOYMENT_MODEL,
        messages=messages,
        temperature=1.0,
        max_tokens=1500
    )
    # print(response.choices[0].message.content)
    return response.choices[0].message.content

def logs_to_plantuml(trace_logs: List[Dict[str, Any]]) -> str:
    """
    단일 트랜잭션 로그(trace_logs)를 입력받아
    1) Parse 단계(JSON) → 2) Generate 단계(PlantUML)까지 실행 후 PlantUML 코드 반환
    """
    # 1단계: Parse
    parse_prompt = build_parse_prompt(trace_logs)
    parsed_output = call_openai(parse_prompt)
    parsed_json = json.loads(parsed_output)
    # print("==== parsed_json ====")
    # print(parsed_json)

    # 1.5단계: Refine (API 설명 보완) => 보완필요로 연결 제거
    # refined_json = refine_api_descriptions(parsed_json)
    # print("==== refined_json ====")
    # print(refined_json)

    # 2단계: Generate
    generate_prompt = build_generate_prompt(parsed_json)
    # generate_prompt = build_generate_prompt(refined_json)
    plantuml_code = call_openai(generate_prompt)

    return plantuml_code

# Streamlit UI
st.set_page_config(layout="wide",page_title="시퀀스다이어그램 생성", page_icon="🎇")
st.title("📡 PICASO 로그 기반 시퀀스다이어그램 생성")

uploaded_file = st.file_uploader("로그 파일 업로드", type=["json","log","txt"])
if uploaded_file:
    try:
        raw = json.load(uploaded_file)
        # 실제 로그 리스트 추출
        hits = raw.get("hits", {}).get("hits", [])
        logs = [h["_source"] for h in hits if "_source" in h]

        # st.subheader("📂 전처리된 로그 미리보기")
        # st.json(logs[:3])  # 앞 3개만 확인

        # 트랜잭션 ID 목록 추출
        trace_ids = list(set([log.get("transactionId") for log in logs if isinstance(log, dict)]))

        # 좌/우 레이아웃
        col1, col2 = st.columns([1, 1])
        with col1:
            st.subheader("🔍 선택된 로그")
            # 항상 두 입력 UI를 모두 보여줌
            manual_trace = st.text_input("직접 트랜잭션 ID 입력", "")
            selected_from_list = st.selectbox("분석할 트랜잭션 선택", trace_ids)

            # 최종 선택 로직
            if manual_trace.strip():
                if manual_trace.strip() in trace_ids:
                    selected_trace = manual_trace.strip()
                else:
                    st.warning("⚠️ 입력한 트랜잭션 ID가 목록에 없습니다. 셀렉트 박스에서 선택한 값이 적용됩니다.")
                    selected_trace = selected_from_list
            else:
                selected_trace = selected_from_list

            # 선택된 트랜잭션 로그만 필터링
            trace_logs = [log for log in logs if log.get("transactionId") == selected_trace]

            st.write(f"현재 선택된 트랜잭션 ID: **{selected_trace}**")
            st.json(trace_logs)

        with col2:
            st.subheader("⚙️ 시퀀스다이어그램 생성")
            if st.button("🚀 End-to-End 실행"):
                with st.spinner("LLM 분석 및 다이어그램 생성 중..."):
                    try:
                        plantuml_code = logs_to_plantuml(trace_logs)

                        st.subheader("📈 시퀀스 다이어그램 코드 (PlantUML)")
                        st.code(plantuml_code, language="plantuml")

                        # PlantUML 서버 렌더링 링크
                        encoded = plantuml.encode_plantuml(plantuml_code)
                        uml_url = f"http://www.plantuml.com/plantuml/svg/{encoded}"
                        st.image(uml_url)
                        st.markdown(f"[🖼️ 새창에서 보기]({uml_url})")

                    except Exception as e:
                        st.error(f"End-to-End 실행 오류: {e}")

    except Exception as e:
        st.error(f"파일 파싱 오류: {e}")
        st.stop()


