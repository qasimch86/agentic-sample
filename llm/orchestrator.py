# FILE: llm/orchestrator.py
from __future__ import annotations
import os, json, re
from typing import Dict, Any, List, Optional
from llm.model import generate_response

PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")
KINDS = ["table", "list", "formatting", "flow_chart"]

# ---------- file + LLM helpers ----------
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

# ---------- small sanitizers ----------
def _strip_optional_string(html: str) -> str:
    if not html: return html
    html = re.sub(r"\s*<h3>\s*optional string\s*</h3>\s*", "", html, flags=re.I)
    html = re.sub(r"\s*<p>\s*optional string\s*</p>\s*", "", html, flags=re.I)
    html = re.sub(r"(^|\s)optional string(\s|$)", " ", html, flags=re.I)
    return html.strip()

# Keep only the single, allowed HTML block per kind
def _coerce_artifact(kind: str, raw: str) -> str:
    s = _strip_optional_string(raw or "")
    if kind == "table":
        # Allow optional <h1-3> title immediately before table
        mtab = re.search(r"(<table\b[\s\S]*?</table>)", s, re.I)
        if mtab:
            title = ""
            before = s[:mtab.start()]
            mtitle = re.search(r"(?:<h[1-3][^>]*>[\s\S]*?</h[1-3]>\s*)$", before, re.I)
            if mtitle:
                title = mtitle.group(0)
            return (title + mtab.group(1)).strip()
        return s  # fall back
    if kind == "list":
        mul = re.search(r"(<ul\b[\s\S]*?</ul>)", s, re.I)
        mol = re.search(r"(<ol\b[\s\S]*?</ol>)", s, re.I)
        if mul and mol:
            return mul.group(1) if mul.start() < mol.start() else mol.group(1)
        if mul: return mul.group(1)
        if mol: return mol.group(1)
        # fallback: convert Markdown bullets to HTML UL (very simple)
        if re.search(r"^\s*[-*]\s+", s, re.M):
            items = [re.sub(r"^\s*[-*]\s+", "", line) for line in re.findall(r"^\s*[-*]\s+.*$", s, re.M)]
            return "<ul>\n" + "\n".join(f"  <li>{re.sub(r'<[^>]+>', '', it)}</li>" for it in items) + "\n</ul>"
        return s
    if kind == "formatting":
        allowed = re.findall(r"(?:<h[1-6][^>]*>[\s\S]*?</h[1-6]>)|(?:<p[^>]*>[\s\S]*?</p>)|(?:<strong>[\s\S]*?</strong>)|(?:<em>[\s\S]*?</em>)", s, re.I)
        return "".join(allowed) if allowed else s
    if kind == "flow_chart":
        # Allow <div class="mermaid">…</div> or ```mermaid fences
        mdiv = re.search(r"(<div[^>]*\bclass=[\"'][^\"']*\bmermaid\b[^\"']*[\"'][^>]*>[\s\S]*?</div>)", s, re.I)
        if mdiv: return mdiv.group(1)
        mfence = re.search(r"```(?:mermaid)?\s*([\s\S]*?)```", s, re.I)
        if mfence:
            inner = mfence.group(1).strip()
            return f'<div class="mermaid">\n{inner}\n</div>'
        return s
    return s

# ---------- guardrail ----------
def guardrail(user_input: str) -> Dict[str, Any]:
    sys = _read("guardrail")
    raw = _ask(sys, user_input)
    j = _parse_json_loose(raw) or {}
    if "allowed" not in j or "reason" not in j:
        return {"allowed": False, "reason": "Guardrail did not return strict JSON"}
    return j

# ---------- intent detection (text) ----------
def _detect_intents_from_text(user_input: str) -> set[str]:
    t = user_input.lower()
    intents = set()
    if re.search(r"\btable|grid|matrix\b", t): intents.add("table")
    if re.search(r"\blist|bulleted|bullet|numbered|ordered\b", t): intents.add("list")
    if re.search(r"\bformat|heading|headings|bold|italic|italics|font\b", t): intents.add("formatting")
    if re.search(r"\bflow\s*chart|flowchart|mermaid|diagram\b", t): intents.add("flow_chart")
    return intents

# ---------- planner (LLM + strong gating + fallback) ----------
def planner_llm(user_input: str) -> Optional[Dict[str, Any]]:
    sys = _read("planner")
    raw = _ask(sys, user_input)
    j = _parse_json_loose(raw)
    if not j or "tasks" not in j or not isinstance(j["tasks"], list):
        return None
    # Only allow supported kinds
    j["tasks"] = [t for t in j["tasks"] if t.get("kind") in KINDS]
    # Gate by explicit intent words in the user input, if any found
    explicit = _detect_intents_from_text(user_input)
    if explicit:
        j["tasks"] = [t for t in j["tasks"] if t.get("kind") in explicit]
    return j

def planner_fallback(user_input: str) -> Dict[str, Any]:
    text = user_input.lower()
    tasks: List[Dict[str, Any]] = []
    tid = 1
    def _add(kind: str, params: Dict[str, Any]):
        nonlocal tid
        tasks.append({"id": f"task_{tid}", "kind": kind, "params": params})
        tid += 1

    # detect only what the user actually asked for
    if re.search(r"\btable|grid|matrix\b", text):
        m = re.search(r"(\d+)\s*(?:x|×|by)\s*(\d+)", text)
        rows, cols = (int(m.group(1)), int(m.group(2))) if m else (3, 3)
        mt = re.search(r"(?:titled|title[d]?)\s+([a-z0-9 \-_/]+)", text)
        title = (mt.group(1).strip().rstrip(".")) if mt else ""
        _add("table", {"rows": rows, "cols": cols, "title": title})

    if re.search(r"\blist|bulleted|bullet|numbered|ordered\b", text):
        ordered = bool(re.search(r"ordered|numbered|1\.", text))
        m2 = re.search(r"(\d+)\s+(?:items|points|bullets|risks|tasks)", text)
        count = int(m2.group(1)) if m2 else 5
        _add("list", {"ordered": ordered, "count": count, "topic": ""})

    if re.search(r"\bformat|heading|headings|bold|italic|italics|font\b", text):
        m3 = re.search(r"(\d+)\s+sections?", text)
        sections = int(m3.group(1)) if m3 else 2
        emphasis = []
        if "bold" in text: emphasis.append("bold")
        if "italic" in text or "italics" in text: emphasis.append("italic")
        if not emphasis: emphasis = ["bold","italic"]
        _add("formatting", {"title": "", "sections": sections, "emphasis": emphasis})

    if re.search(r"\bflow\s*chart|flowchart|mermaid|diagram\b", text):
        mt = re.search(r"(?:of|for)\s+([a-z0-9 \-_/]+)", text)
        topic = (mt.group(1).strip().rstrip(".")) if mt else "Process"
        _add("flow_chart", {"topic": topic})

    return {
        "tasks": tasks,
        "before_text": "Here are your results:",
        "after_text": "Need edits? Say, “Replace R2C1 with 32”."
    }

# ---------- table edit (unchanged from previous hardened version) ----------
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
    t = text.strip()
    m = re.search(r"\bR(\d+)\s*C(\d+)\b", t, re.I)
    row = col = None
    if m: row, col = int(m.group(1)), int(m.group(2))
    mr = re.search(r"\brow\s+(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+)", t, re.I)
    mc = re.search(r"\bcol(?:umn)?\s+(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+)", t, re.I)
    if (mr and mc) and (row is None or col is None):
        row = _word_to_int(mr.group(1)); col = _word_to_int(mc.group(1))
    mv = re.search(r"\b(?:to|by|as|with)\s+([^\n\.]+)", t, re.I)
    val = mv.group(1).strip() if mv else None
    if row and col and val is not None:
        return {"row": row, "col": col, "value": val}
    return None

_TAG = re.compile(r"<[^>]+>")
def _strip_tags(s: str) -> str: return _TAG.sub("", s)

def _open_table_tag(html: str) -> str:
    m = re.search(r"<table[^>]*>", html, re.I)
    return m.group(0) if m else '<table class="llm-table">'

def parse_table_html(html: str) -> Dict[str, Any]:
    header: List[str] = []
    mthead = re.search(r"<thead[^>]*>.*?<tr[^>]*>(.*?)</tr>.*?</thead>", html, re.I|re.S)
    if mthead:
        header = [ _strip_tags(c).strip() for c in re.findall(r"<th[^>]*>(.*?)</th>", mthead.group(1), re.I|re.S) ]
    tbody = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.I|re.S)
    rows_src = tbody.group(1) if tbody else re.sub(r"<thead[^>]*>.*?</thead>", "", html, flags=re.I|re.S)
    row_chunks = re.findall(r"<tr[^>]*>(.*?)</tr>", rows_src, re.I|re.S)
    rows: List[List[str]] = []
    for chunk in row_chunks:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", chunk, re.I|re.S)
        if not cells:
            cells = re.findall(r"<th[^>]*>(.*?)</th>", chunk, re.I|re.S)
        rows.append([_strip_tags(c).strip() for c in cells])
    if header and rows and len(rows[0]) == len(header):
        if all(_strip_tags(a).strip().lower() == _strip_tags(b).strip().lower() for a,b in zip(rows[0], header)):
            rows = rows[1:]
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
    while len(rows) < row:
        rows.append([""]*max(model["cols"], 1))
    model["cols"] = max(model["cols"], col)
    for i in range(len(rows)):
        rows[i] = (rows[i] + [""]*model["cols"])[:model["cols"]]
    rows[row-1][col-1] = value
    model["rows"] = rows
    return build_table_html(model)

# ---------- executors ----------
def _exec_task(kind: str, params: Dict[str, Any]) -> str:
    sys = _read(kind)
    payload = json.dumps(params, ensure_ascii=False)
    raw = _ask(sys, payload)
    return _coerce_artifact(kind, raw)

def _final_template(tasks: List[Dict[str, Any]]) -> str:
    # simple: placeholders only; client substitutes
    placeholders = "\n".join(f"{{{t['kind']}_{i+1}}}" for i, t in enumerate(tasks))
    return placeholders or "{artifacts}"

# ---------- compose ----------
def compose(user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    context = context or {}

    # 1) guard
    g = guardrail(user_input)
    if not g.get("allowed", False):
        return {"mode":"blocked","preamble":"","final_template":"","variables":{},"postamble":f"Request denied: {g.get('reason','')}".strip()}

    text = user_input.strip()
    last_table_html = context.get("last_table")

    # 2) deterministic table edit (if we have prev table)
    if last_table_html and looks_like_table_edit(text):
        spec = extract_edit_instruction(text)
        if spec:
            updated = edit_table_html(last_table_html, spec["row"], spec["col"], spec["value"])
            return {
                "mode":"html",
                "preamble": f'Updated cell R{spec["row"]}C{spec["col"]} → {spec["value"]}.',
                "final_template": "{table_1}",
                "variables": {"table_1": updated},
                "postamble": ""
            }

    # 3) plan → execute
    pl = planner_llm(text)
    if not pl or not pl.get("tasks"):
        pl = planner_fallback(text)

    tasks = pl.get("tasks", [])
    if not tasks:
        return {"mode":"blocked","preamble":"","final_template":"","variables":{},"postamble":"Planner failed"}

    variables: Dict[str, str] = {}
    counters = {k: 1 for k in KINDS}
    order: List[str] = []
    for t in tasks:
        kind = t.get("kind")
        if kind not in KINDS: 
            continue
        params = t.get("params", {}) or {}
        var = f"{kind}_{counters[kind]}"; counters[kind] += 1
        variables[var] = _exec_task(kind, params)
        order.append(var)

    # final template with placeholders only, in order
    final_template = "\n".join(f"{{{v}}}" for v in order) if order else "{artifacts}"
    pre = pl.get("before_text") or "Here are your results:"
    post = pl.get("after_text") or "Need edits? Say, “Replace R2C1 with 32”."

    return {"mode":"html","preamble":pre,"final_template":final_template,"variables":variables,"postamble":post}
