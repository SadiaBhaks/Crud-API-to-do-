"""
llm/client.py — the one module that talks to the model provider.

Same "one module owns the external dependency" pattern as db.py and
auth.py elsewhere in this project: main.py never imports openai directly,
it only ever calls triage() from here.

Handles, in order: the kill switch, stub mode, calling the model with a
real timeout and a bounded retry policy, parsing the answer, validating it
against the schema, one repair retry on failure, and quarantining anything
that still doesn't validate. Every call is logged with its cost.
"""

import json
import logging
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI, APITimeoutError, APIStatusError, RateLimitError
from pydantic import ValidationError

from llm.schema import TriageResult, validate_output

load_dotenv()

PROMPT_VERSION = "triage-v1"
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / f"{PROMPT_VERSION}.md"
QUARANTINE_PATH = Path(__file__).parent.parent / "logs" / "quarantine.jsonl"

# A real timeout — the SDK default is 10 minutes, which is not a timeout
# at all for an HTTP endpoint. 30s is the ceiling for a request this small.
REQUEST_TIMEOUT_SECONDS = 30.0

# We disable the SDK's own retry loop (max_retries=0) and implement our
# own below, so the policy — what gets retried and what doesn't — is
# explicit and visible in one place instead of hidden in a library default.
MAX_RETRY_ATTEMPTS = 3

# cost-logging goes to stdout as structured lines (Twelve-Factor style) —
# not a log file, so it can be routed by whatever's running the process.
logger = logging.getLogger("llm.cost")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _load_system_prompt() -> str:
    return PROMPT_PATH.read_text()


def _get_client() -> OpenAI:
    return OpenAI(
        base_url=os.environ["LLM_BASE_URL"],
        api_key=os.environ["LLM_API_KEY"],
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=0,  # we implement our own policy below
    )


class ModelTimeoutError(Exception):
    """Raised when every retry attempt times out."""


class LLMDisabledError(Exception):
    """Raised when LLM_ENABLED=false — callers turn this into a 503."""


@dataclass
class TriageOutcome:
    result: TriageResult
    repaired: bool
    raw_text: str


def _is_enabled() -> bool:
    return os.environ.get("LLM_ENABLED", "true").lower() != "false"


def _is_stub_mode() -> bool:
    return os.environ.get("LLM_STUB", "0") == "1"


def _stub_result(text: str) -> TriageOutcome:
    # A fixed, schema-valid object — proves the endpoint's contract without
    # spending a single real call. Used for all day-to-day development.
    result = TriageResult(
        category="chore",
        urgency="normal",
        confidence=0.42,
        reason="Stub mode response — no model was called.",
    )
    return TriageOutcome(result=result, repaired=False, raw_text="<stub mode>")


def _call_model_once(client: OpenAI, system_prompt: str, user_text: str, extra_user_msg: Optional[str] = None) -> tuple[str, dict]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps({"text": user_text})},
    ]
    if extra_user_msg:
        messages.append({"role": "user", "content": extra_user_msg})

    start = time.monotonic()
    response = client.chat.completions.create(
        model=os.environ["LLM_MODEL"],
        messages=messages,
        temperature=0.2,  # classification wants the same answer each time, not creativity
    )
    duration_ms = int((time.monotonic() - start) * 1000)

    content = response.choices[0].message.content or ""
    usage = response.usage
    meta = {
        "duration_ms": duration_ms,
        "input_tokens": getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "completion_tokens", None),
    }
    return content, meta


def _call_with_retries(client: OpenAI, system_prompt: str, user_text: str, extra_user_msg: Optional[str] = None) -> tuple[str, dict]:
    """
    Retries on timeouts, 429, and 5xx only — never on 400/401/403, since a
    bad key or bad request will still be bad four seconds later, and on a
    metered free tier a pointless retry burns real quota for nothing.
    """
    last_exc = None
    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            return _call_model_once(client, system_prompt, user_text, extra_user_msg)
        except APITimeoutError as exc:
            last_exc = exc
        except RateLimitError as exc:
            last_exc = exc
        except APIStatusError as exc:
            if exc.status_code >= 500:
                last_exc = exc
            else:
                # 4xx other than 429 (e.g. 400/401/403) — never retried.
                raise

        if attempt < MAX_RETRY_ATTEMPTS - 1:
            backoff = (2 ** attempt) + random.uniform(0, 0.5)  # exponential backoff + jitter
            time.sleep(backoff)

    raise ModelTimeoutError(str(last_exc))


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _extract_json_object(text: str) -> dict:
    cleaned = _strip_code_fence(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise json.JSONDecodeError("no JSON object found", cleaned, 0)
    return json.loads(cleaned[start:end + 1])


def _quarantine(input_text: str, raw_output: str, error: str) -> None:
    QUARANTINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.time(),
        "prompt_version": PROMPT_VERSION,
        "input": input_text,
        "raw_output": raw_output,
        "error": error,
    }
    with open(QUARANTINE_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def triage(text: str) -> TriageOutcome:
    if not _is_enabled():
        raise LLMDisabledError("LLM_ENABLED is false")

    if _is_stub_mode():
        return _stub_result(text)

    system_prompt = _load_system_prompt()
    client = _get_client()

    raw_text, meta = _call_with_retries(client, system_prompt, text)
    repaired = False

    try:
        parsed = _extract_json_object(raw_text)
        result = validate_output(parsed)
    except (json.JSONDecodeError, ValidationError) as first_error:
        # One repair retry: hand the model its own broken output and the
        # exact validation error, and ask for a corrected version.
        repair_instruction = (
            "Your previous answer was rejected for this reason: "
            f"{first_error}. Your previous answer was: {raw_text}. "
            "Return only corrected JSON matching the schema — no other text."
        )
        raw_text_2, meta2 = _call_with_retries(client, system_prompt, text, extra_user_msg=repair_instruction)
        meta["duration_ms"] += meta2["duration_ms"]
        raw_text = raw_text_2
        repaired = True

        try:
            parsed = _extract_json_object(raw_text)
            result = validate_output(parsed)
        except (json.JSONDecodeError, ValidationError) as second_error:
            _quarantine(text, raw_text, str(second_error))
            _log_cost(meta, repaired=True, failed=True)
            raise ValueError(f"Model output failed validation twice: {second_error}") from second_error

    _log_cost(meta, repaired=repaired, failed=False)
    return TriageOutcome(result=result, repaired=repaired, raw_text=raw_text)


def _log_cost(meta: dict, repaired: bool, failed: bool) -> None:
    line = {
        "event": "llm_call",
        "prompt_version": PROMPT_VERSION,
        "model": os.environ.get("LLM_MODEL"),
        "input_tokens": meta.get("input_tokens"),
        "output_tokens": meta.get("output_tokens"),
        "duration_ms": meta.get("duration_ms"),
        "repaired": repaired,
        "failed": failed,
    }
    logger.info(json.dumps(line))