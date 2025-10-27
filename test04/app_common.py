
import os, json, subprocess, tempfile
from typing import List, Dict, Any
import streamlit as st
import gpv_parser

PLANTUML_JAR = os.environ.get("PLANTUML_JAR", "/app/plantuml.jar")
DEFAULT_PARTICIPANTS = ["SCIS", "GPV", "MEIN", "UCEMS", "NCRAB"]

def build_plantuml(tx_id: str, steps: List[Dict[str, Any]]) -> str:
    participants = list(dict.fromkeys(DEFAULT_PARTICIPANTS))
    for s in steps:
        if s["from"] not in participants: participants.append(s["from"])
        if s["to"] not in participants: participants.append(s["to"])
    lines = ["@startuml", f"title Transaction: {tx_id}"]
    for p in participants:
        lines.append(f'participant "{p}" as {p}')
    lines.append("")
    for s in steps:
        frm, to, label, p95, note = s["from"], s["to"], s["label"], s["p95"], s["note"]
        label2 = label if p95 is None else f"{label} (t≈{p95}ms)"
        lines.append(f"{frm} -> {to}: {label2}")
        if note:
            note_txt = (note or "").replace("\\n"," ")[:180]
            lines.append(f"note right of {to}"); lines.append(f"  {note_txt}"); lines.append("end note")
    lines.append("@enduml"); return "\n".join(lines)

def try_render_plantuml_png(code: str) -> bytes:
    if not os.path.exists(PLANTUML_JAR):
        raise FileNotFoundError(f"PlantUML JAR not found at {PLANTUML_JAR}")
    with tempfile.NamedTemporaryFile("w", suffix=".puml", delete=False, encoding="utf-8") as f:
        f.write(code); path = f.name
    proc = subprocess.run(["java","-jar",PLANTUML_JAR,"-tpng",path], capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="ignore"))
    png_path = path.replace(".puml",".png")
    with open(png_path,"rb") as fp: return fp.read()
