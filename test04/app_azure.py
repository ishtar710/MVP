
# Azure extended variant will reuse the same build_steps logic.
import os, json
from typing import List, Dict, Any
import streamlit as st
import gpv_parser
from app_common import build_plantuml, DEFAULT_PARTICIPANTS  # type: ignore

st.set_page_config(page_title="Trace2UML Azure (No-dup RTT)", layout="wide")
st.title("Trace2UML Azure (No-dup RTT)")

def build_steps(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    steps: List[Dict[str, Any]] = []
    partner = "SCIS"
    for ev in events[:30]:
        if ev.get("sourceSystem"):
            partner = ev["sourceSystem"]; break
    ifid = None
    for ev in events[:50]:
        if ev.get("interfaceId"):
            ifid = ev["interfaceId"]; break
    steps.append({"from": partner, "to": "GPV", "label": f"{partner}→GPV {ifid or ''}".strip(), "note": None, "p95": None})

    last_out_idx: Dict[str, int] = {}
    for ev in events:
        et = ev.get("eventType"); actor = (ev.get("actor") or "").upper()
        if et in ("HTTP_REQUEST_HEADER","HTTP_REQUEST_BODY","DECRYPTED_BODY"): continue
        if et == "EXT_HTTP_REQ" and actor:
            idx = len(steps); steps.append({"from":"GPV","to":actor,"label":f"{actor} call","note":None,"p95":None}); last_out_idx[actor]=idx; continue
        if et == "EXT_HTTP_RTT" and actor:
            if actor in last_out_idx: steps[last_out_idx[actor]]["p95"]=ev.get("durationMs")
            else:
                idx = len(steps); steps.append({"from":"GPV","to":actor,"label":f"{actor} call","note":None,"p95":ev.get("durationMs")}); last_out_idx[actor]=idx
            continue
        if et == "EXT_HTTP_RESP" and actor:
            steps.append({"from":actor,"to":"GPV","label":"response","note":None,"p95":None})
            if actor in last_out_idx: del last_out_idx[actor]
            continue
        if et == "SYS_ERROR":
            steps.append({"from":"GPV","to":"GPV","label":"ERROR","note":(ev.get("raw","")[:200] or None),"p95":None}); continue
    return steps

up = st.file_uploader("로그 업로드(.log/.txt)", type=["log","txt"])
if up and st.button("파싱 실행"):
    content = up.getvalue().decode("utf-8","ignore").splitlines()
    events = list(gpv_parser.parse_lines(content)); st.session_state["events"] = events

if "events" in st.session_state:
    events = st.session_state["events"]
    by_tx: Dict[str, List[Dict[str, Any]]] = {}
    for ev in events:
        tx = ev.get("txId") or "NO_TX"; by_tx.setdefault(tx, []).append(ev)
    tx_ids = sorted(by_tx.keys())
    tx_choice = st.selectbox("transactionId", options=tx_ids, index=0)
    cur_events = by_tx[tx_choice]
    steps = build_steps(cur_events)
    puml = build_plantuml(tx_choice, steps)
    st.subheader("PlantUML 코드"); st.code(puml, language="plantuml")
