import os
from flask import Flask, request, jsonify, send_from_directory
# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

# LangChain + OpenAI imports
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# >>> LLM-COMPOSE: START
# Orchestrated, structured artifact generation (table/list/formatting/flow_chart)
# Requires llm/orchestrator.py to be present in your project.
from llm.orchestrator import compose
# >>> LLM-COMPOSE: END

# Serve static assets from /src so /src/css/... and /src/js/... work
app = Flask(__name__)

# Serve /static/logo/... and /static/favicon.png for images and favicon
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# Serve component HTML files from templates/components for frontend fetch
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

# Simple health check
@app.get("/health")
def health():
    return {"status": "ok"}

# Chat endpoint: allow GET (manual tests), POST (used by page), OPTIONS (preflight)
@app.route("/api/chat", methods=["GET", "POST", "OPTIONS"])
def api_chat():
    cors = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    }

    if request.method == "OPTIONS":
        return ("", 204, cors)

    if request.method == "GET":
        q = (request.args.get("q") or "").strip()
        return (jsonify({"reply": f"(demo GET) You said: {q or 'Send a POST to /api/chat'}"}), 200, cors)

    # POST JSON: { "message": "..." }
    data = request.get_json(force=True) or {}
    user_msg = (data.get("message") or "").strip()
    if not user_msg:
        return (jsonify({"reply": "Please enter a message."}), 200, cors)

    # --- LangChain + OpenAI reply ---
    try:
        # System prompt for consistent assistant behavior
        system_prompt = "You are a helpful AI assistant for this website."
        # Initialize LLM (model can be changed via env or here)
        llm = ChatOpenAI(
            model="gpt-4o-mini",  # Change model name here to switch
            temperature=0.2,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        msgs = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_msg)
        ]
        # Synchronous invoke, returns LLM reply
        reply = llm.invoke(msgs).content
    except Exception as e:
        # Minimal robust error handling
        reply = "Sorry, the assistant is unavailable. Please try again later."

    return (jsonify({"reply": reply}), 200, cors)

# >>> LLM-COMPOSE: START
# Structured compose endpoint for tables/lists/formatting/flow charts (Markdown/Mermaid)
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
        # Manual test helper (mirrors your style of friendly GET)
        return (jsonify({
            "mode": "markdown",
            "preamble": "(demo GET) POST { user_input: \"...\" } to /api/compose",
            "final_template": "",
            "variables": {},
            "postamble": ""
        }), 200, cors)

    data = request.get_json(force=True) or {}
    user_input = (data.get("user_input") or data.get("message") or "").strip()
    if not user_input:
        # Match your chat endpoint’s friendly style (HTTP 200 + message)
        return (jsonify({
            "mode": "blocked",
            "preamble": "",
            "final_template": "",
            "variables": {},
            "postamble": "No input provided."
        }), 200, cors)

    try:
        envelope = compose(user_input)  # returns the agreed envelope schema
    except Exception:
        envelope = {
            "mode": "blocked",
            "preamble": "",
            "final_template": "",
            "variables": {},
            "postamble": "LLM service unavailable. Please try again later."
        }

    return (jsonify(envelope), 200, cors)
# >>> LLM-COMPOSE: END

if __name__ == "__main__":
    # Use port 8001 to match earlier checks
    app.run(debug=True, port=8001)
