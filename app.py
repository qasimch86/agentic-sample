import os
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

load_dotenv()

# >>> LLM-COMPOSE: START
# Orchestrated, structured artifact generation (table/list/formatting/flow_chart)
from llm.orchestrator import compose
# >>> LLM-COMPOSE: END

app = Flask(__name__)

# --- Static and component routing (unchanged) ---
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/templates/components/<path:filename>')
def component_files(filename):
    return send_from_directory('templates/components', filename)

def _chat_html_path():
    """
    Prefer ./public/index.html if you keep HTML pages in a 'public' folder.
    Otherwise fall back to ./index.html at project root.
    """
    if os.path.exists(os.path.join("public", "index.html")):
        return ("public", "index.html")
    return (".", "index.html")

@app.get("/")
def root():
    folder, fname = _chat_html_path()
    return send_from_directory(folder, fname)

@app.get("/health")
def health():
    return {"status": "ok"}

# --- Structured compose endpoint ---
@app.route("/api/compose", methods=["GET", "POST", "OPTIONS"])
def api_compose():
    cors = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    }

    if request.method == "OPTIONS":
        return ("", 204, cors)

    if request.method == "GET":
        # Friendly GET for quick manual checks
        return (
            jsonify({
                "mode": "markdown",
                "preamble": "(demo GET) POST { user_input: \"...\", context: {...} } to /api/compose",
                "final_template": "",
                "variables": {},
                "postamble": ""
            }),
            200,
            cors
        )

    # POST JSON: { "user_input": "...", "context": { ... } }
    data = request.get_json(force=True) or {}
    user_input = (data.get("user_input") or data.get("message") or "").strip()
    context = data.get("context") or {}

    if not user_input:
        return (
            jsonify({
                "mode": "blocked",
                "preamble": "",
                "final_template": "",
                "variables": {},
                "postamble": "No input provided."
            }),
            200,
            cors
        )

    try:
        envelope = compose(user_input, context=context)
    except Exception:
        envelope = {
            "mode": "blocked",
            "preamble": "",
            "final_template": "",
            "variables": {},
            "postamble": "LLM service unavailable. Please try again later."
        }

    return (jsonify(envelope), 200, cors)

if __name__ == "__main__":
    app.run(debug=True, port=8001)
