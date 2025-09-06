# FILE: llm/orchestrator.py
from __future__ import annotations
import os, json, re
from typing import Dict, Any, List, Optional
from llm.model import generate_response

PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")
KINDS = ["table", "list", "formatting", "flow_chart"]

def _read(name: str) -> str:
    with open(os.path.join(PROMPT_DIR, f"{name}.txt"), encoding="utf-8") as f:
        return f.read()

def _parse_json_loose(text: str):
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.findall(r"\{[\s\S]*\}", text)
    for chunk in reversed(m):
        try:
            return json.loads(chunk)
        except Exception:
            continue
    return None

def _ask(system_prompt: str, user_text: str) -> str:
    return generate_response(user_text, system_prompt=system_prompt)

# ---------------- Guardrail ----------------
def guardrail(user_input: str) -> Dict[str, Any]:
    sys = _read("guardrail")
    raw = _ask(sys, user_input)
    j = _parse_json_loose(raw) or {}
    if "allowed" not in j or "reason" not in j:
        return {"allowed": False, "reason": "Guardrail did not return strict JSON"}
    return j

# ---------------- Planner (LLM + fallback) ----------------
def planner_llm(user_input: str) -> Optional[Dict[str, Any]]:
    sys = _read("planner")
    raw = _ask(sys, user_input)
    j = _parse_json_loose(raw)
    if not j or "tasks" not in j or not isinstance(j["tasks"], list):
        return None
    j["tasks"] = [t for t in j["tasks"] if t.get("kind") in KINDS]
    return j

def planner_fallback(user_input: str) -> Dict[str, Any]:
    text = user_input.lower()
    tasks: List[Dict[str, Any]] = []
    tid = 1
    def _add(kind: str, params: Dict[str, Any]):
        nonlocal tid
        tasks.append({"id": f"task_{tid}", "kind": kind, "params": params})
        tid += 1

    m = re.search(r"(\d+)\s*(?:x|×|by)\s*(\d+)", text)
    if "table" in text or "grid" in text:
        rows, cols = (int(m.group(1)), int(m.group(2))) if m else (3, 3)
        mt = re.search(r"(?:titled|title[d]?)\s+([a-z0-9 \-_/]+)", text)
        title = (mt.group(1).strip().rstrip(".")) if mt else ""
        _add("table", {"rows": rows, "cols": cols, "title": title})

    if any(w in text for w in ["list", "bullets", "bullet", "points"]):
        ordered = bool(re.search(r"ordered|numbered|1\.", text))
        m2 = re.search(r"(\d+)\s+(?:items|points|bullets|risks|tasks)", text)
        count = int(m2.group(1)) if m2 else 5
        mt = re.search(r"list(?: of| titled)?\s+(.*?)(?:\.|,|;|$)", text)
        topic = (mt.group(1).strip()) if mt else ""
        _add("list", {"ordered": ordered, "count": count, "topic": topic})

    if any(k in text for k in ["formatting", "headings", "bold", "italic"]):
        m3 = re.search(r"(\d+)\s+sections?", text)
        sections = int(m3.group(1)) if m3 else 2
        emphasis = []
        if "bold" in text: emphasis.append("bold")
        if "italic" in text or "italics" in text: emphasis.append("italic")
        if not emphasis: emphasis = ["bold","italic"]
        _add("formatting", {"title": "", "sections": sections, "emphasis": emphasis})

    if any(k in text for k in ["flow chart", "flowchart", "diagram"]):
        mt = re.search(r"(?:of|for)\s+([a-z0-9 \-_/]+)", text)
        topic = (mt.group(1).strip().rstrip(".")) if mt else "Process"
        _add("flow_chart", {"topic": topic})

    return {
        "tasks": tasks,
        "before_text": "Here are your requested artifacts.",
        "after_text": "Let me know if you want any edits."
    }

# ---------------- Edit intent detection + parsing ----------------
_ORD = {
    "first":1,"second":2,"third":3,"fourth":4,"fifth":5,
    "sixth":6,"seventh":7,"eighth":8,"ninth":9,"tenth":10
}
def _word_to_int(tok: str) -> Optional[int]:
    if tok.isdigit(): return int(tok)
    return _ORD.get(tok.lower())

def looks_like_table_edit(text: str) -> bool:
    t = text.lower()
    if not re.search(r"(?:replace|update|change|set)\b", t): 
        return False
    return bool(re.search(r"\bR\d+C\d+\b", t) or ("row" in t and ("column" in t or "col" in t)))

def extract_edit_instruction(text: str) -> Optional[Dict[str,int | str]]:
    """Return {'row':int,'col':int,'value':str} if detected."""
    t = text.strip()

    # R{row}C{col}
    m = re.search(r"\bR(\d+)\s*C(\d+)\b", t, re.I)
    row = col = None
    if m:
        row, col = int(m.group(1)), int(m.group(2))

    # row X column Y (numbers or ordinals)
    mr = re.search(r"\brow\s+(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+)", t, re.I)
    mc = re.search(r"\bcol(?:umn)?\s+(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+)", t, re.I)
    if (mr and mc) and (row is None or col is None):
        row = _word_to_int(mr.group(1))
        col = _word_to_int(mc.group(1))

    # value after 'to|by|as|with'
    mv = re.search(r"\b(?:to|by|as|with)\s+([^\n\.]+)", t, re.I)
    val = mv.group(1).strip() if mv else None

    if row and col and val is not None:
        return {"row": row, "col": col, "value": val}
    return None

# ---------------- Minimal HTML table editor (no external deps) ----------------
_TAG = re.compile(r"<[^>]+>")
def _strip_tags(s: str) -> str:
    return _TAG.sub("", s)

def _open_table_tag(html: str) -> str:
    m = re.search(r"<table[^>]*>", html, re.I)
    return m.group(0) if m else '<table class="llm-table">'

def parse_table_html(html: str) -> Dict[str, Any]:
    """Very simple parser for our generated tables."""
    # header
    header: List[str] = []
    mthead = re.search(r"<thead[^>]*>.*?<tr[^>]*>(.*?)</tr>.*?</thead>", html, re.I|re.S)
    if mthead:
        header = [ _strip_tags(c).strip() for c in re.findall(r"<th[^>]*>(.*?)</th>", mthead.group(1), re.I|re.S) ]

    # tbody or all rows
    tbody = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.I|re.S)
    rows_src = tbody.group(1) if tbody else re.sub(r"<thead[^>]*>.*?</thead>", "", html, flags=re.I|re.S)
    row_chunks = re.findall(r"<tr[^>]*>(.*?)</tr>", rows_src, re.I|re.S)

    rows: List[List[str]] = []
    for chunk in row_chunks:
        # prefer <td>; if none, also accept <th>
        cells = re.findall(r"<td[^>]*>(.*?)</td>", chunk, re.I|re.S)
        if not cells:
            cells = re.findall(r"<th[^>]*>(.*?)</th>", chunk, re.I|re.S)
        rows.append([_strip_tags(c).strip() for c in cells])

    # Remove potential duplicated header row from rows if identical to header
    if header and rows and len(rows[0]) == len(header):
        if all(_strip_tags(a).strip().lower() == _strip_tags(b).strip().lower() for a,b in zip(rows[0], header)):
            rows = rows[1:]

    # detect columns
    cols = max((len(r) for r in rows), default=len(header))
    return {"header": header, "rows": rows, "cols": cols, "open_tag": _open_table_tag(html)}

def build_table_html(model: Dict[str, Any]) -> str:
    header, rows, cols, open_tag = model["header"], model["rows"], model["cols"], model["open_tag"]
    parts: List[str] = [open_tag]
    if header and len(header) == cols:
        parts.append("<thead><tr>")
        parts.extend(f"<th>{h}</th>" for h in header)
        parts.append("</tr></thead>")
    parts.append("<tbody>")
    for r in rows:
        # pad to cols
        r = (r + [""]*cols)[:cols]
        parts.append("<tr>")
        parts.extend(f"<td>{c}</td>" for c in r)
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)

def edit_table_html(previous_html: str, row: int, col: int, value: str) -> str:
    model = parse_table_html(previous_html)
    rows = model["rows"]
    if row < 1 or col < 1: 
        return previous_html
    # ensure enough rows/cols
    while len(rows) < row:
        rows.append([""]*max(model["cols"], 1))
    model["cols"] = max(model["cols"], col)
    for i in range(len(rows)):
        rows[i] = (rows[i] + [""]*model["cols"])[:model["cols"]]
    rows[row-1][col-1] = value
    model["rows"] = rows
    return build_table_html(model)

# ---------------- Executors ----------------
def _exec_task(kind: str, params: Dict[str, Any]) -> str:
    # if we ended here for a normal creation task, run the standard executor prompts
    prompt_name = kind
    sys = _read(prompt_name)
    payload = json.dumps(params, ensure_ascii=False)
    raw = _ask(sys, payload)
    return (raw or "").strip()

def _final_template(tasks: List[Dict[str, Any]]) -> Dict[str, str]:
    sys = _read("final_template")
    kinds = ", ".join(t.get("kind", "") for t in tasks) or "none"
    raw = _ask(sys, f"Artifacts: {kinds}")
    j = _parse_json_loose(raw) or {}
    return {"final_template": j.get("final_template", "{artifacts}")}

# ---------------- Compose ----------------
def compose(user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    context = context or {}

    # 1) Guardrail
    g = guardrail(user_input)
    if not g.get("allowed", False):
        return {"mode":"blocked","preamble":"","final_template":"","variables":{},"postamble":f"Request denied: {g.get('reason','')}".strip()}

    text = user_input.strip()
    last_table_html = context.get("last_table")

    # 2) Special case: deterministic TABLE EDIT
    if last_table_html and looks_like_table_edit(text):
        spec = extract_edit_instruction(text)
        if spec:
            updated = edit_table_html(last_table_html, spec["row"], spec["col"], spec["value"])
            variables = {"table_1": updated}
            final_template = "{table_1}"
            pre = f"Updated cell R{spec['row']}C{spec['col']} → {spec['value']}."
            post = ""
            return {"mode":"html","preamble":pre,"final_template":final_template,"variables":variables,"postamble":post}
        # fallback to LLM editor if parsing failed
        try:
            sys = _read("table_edit")
            payload = json.dumps({"previous_html": last_table_html, "instruction": text}, ensure_ascii=False)
            updated = _ask(sys, payload).strip() or last_table_html
            variables = {"table_1": updated}
            return {"mode":"html","preamble":"Applied table edit.","final_template":"{table_1}","variables":variables,"postamble":""}
        except Exception:
            return {"mode":"html","preamble":"(Could not parse edit request)","final_template":"{table_1}","variables":{"table_1": last_table_html},"postamble":""}

    # 3) Normal plan → execute
    pl = planner_llm(text)
    if not pl or not pl.get("tasks"):
        pl = planner_fallback(text)
    if not pl.get("tasks"):
        return {"mode":"blocked","preamble":"","final_template":"","variables":{},"postamble":"Planner failed"}

    tasks = pl["tasks"]
    pre   = pl.get("before_text", "")
    post  = pl.get("after_text", "")

    variables: Dict[str, str] = {}
    counters = {k: 1 for k in KINDS}
    for t in tasks:
        kind = t.get("kind")
        if kind not in KINDS: 
            continue
        params = t.get("params", {}) or {}
        var = f"{kind}_{counters[kind]}"; counters[kind] += 1
        try:
            variables[var] = _exec_task(kind, params)
        except Exception as e:
            variables[var] = f"<p>_Error generating {kind}: {e}_</p>"

    # placeholders once, in detection order
    var_names_in_order: List[str] = []
    seen = set()
    for t in tasks:
        k = t.get("kind")
        i = 1
        while True:
            v = f"{k}_{i}"
            if v in variables:
                if v not in seen:
                    var_names_in_order.append(v); seen.add(v)
                i += 1
            else:
                break

    tpl = _final_template(tasks)
    final_template = tpl["final_template"]
    placeholders = "\n".join(f"{{{n}}}" for n in var_names_in_order)
    if "{artifacts}" in final_template:
        final_template = final_template.replace("{artifacts}", placeholders)
    else:
        final_template = placeholders

    return {"mode":"html","preamble":pre,"final_template":final_template,"variables":variables,"postamble":post}
