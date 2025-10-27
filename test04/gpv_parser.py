import re, json
from typing import Iterable, Dict, Any, Optional

# Minimal tolerant parser: treat every line as TEXT, set txId if found, detect simple tags.
RX_TXID = re.compile(r"(?i)(transaction[_ ]?id)\s*[:=\[]\s*([A-Z]{2,}\d{14,}|[A-F0-9\-]{16,})")
def parse_lines(lines: Iterable[str]):
    tx = None
    for i, line in enumerate(lines, 1):
        m = RX_TXID.search(line)
        if m: tx = m.group(2)
        ev = {"line": i, "ts": None, "level": None, "thread": None, "logger": None,
              "txId": tx, "eventType": "TEXT", "actor": None, "payload": None, "durationMs": None,
              "raw": line.rstrip()}
        low = line.lower()
        if "[post]uri" in low: ev["eventType"] = "EXT_HTTP_REQ"
        if "api 실행 시간" in low: ev["eventType"] = "EXT_HTTP_RTT"; ev["durationMs"] = 0
        if "응답" in low: ev["eventType"] = "EXT_HTTP_RESP"
        if "mein" in low: ev["actor"] = "MEIN"
        if "ncrab" in low: ev["actor"] = "NCRAB"
        if "ucems" in low: ev["actor"] = "UCEMS"
        if "sourcesystem" in low and "[" in line: ev["sourceSystem"] = line.split("[",1)[-1].split("]",1)[0]
        if "interfaceid" in low and "[" in line: ev["interfaceId"] = line.split("[",1)[-1].split("]",1)[0]
        yield ev
