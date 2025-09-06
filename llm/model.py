# llm/model.py
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from .config import OPENAI_API_KEY, DEFAULT_MODEL, TEMPERATURE
from .utils import log_error

# Load default system prompt from file (optional)
import io
import pathlib

_PROMPT_PATH = pathlib.Path(__file__).with_name("prompts") / "system_prompt.txt"
_DEFAULT_SYSTEM_PROMPT = ""
if _PROMPT_PATH.exists():
    try:
        _DEFAULT_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        _DEFAULT_SYSTEM_PROMPT = ""

# Lazy, cached LLM instance
_llm = None

def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set")
        _llm = ChatOpenAI(
            model=DEFAULT_MODEL,
            temperature=TEMPERATURE,
            openai_api_key=OPENAI_API_KEY,
            timeout=60,
        )
    return _llm

def generate_response(user_text: str, system_prompt: str | None = None) -> str:
    """
    Single-turn call used by the orchestrator and /api/chat.
    - If `system_prompt` is provided, it overrides the default file prompt.
    - Returns the .content string from the model.
    """
    try:
        sys = (system_prompt or _DEFAULT_SYSTEM_PROMPT or "You are a helpful assistant.")
        msgs = [SystemMessage(content=sys), HumanMessage(content=user_text)]
        return _get_llm().invoke(msgs).content
    except Exception as e:
        # Log and re-raise so /api/compose can surface a clean "unavailable" message
        log_error(e)
        raise
