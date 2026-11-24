"""Intent extraction (rule-based + Claude) and grounded answer generation.

Design rule from the playbook: deterministic code retrieves and ranks prices;
Claude only interprets the question and explains retrieved records.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterator, Literal, Optional

import pandas as pd
from pydantic import BaseModel

MODEL = "claude-opus-5-5"

PROCEDURES = {
    "73721": ("MRI lower-extremity joint without contrast", ("knee", "lower extremity", "leg mri", "73721")),
    "70551": ("MRI brain without contrast", ("brain", "head mri", "70551")),
    "74176": ("CT abdomen and pelvis without contrast", ("abdomen", "pelvis", "ct abdomen", "74176")),
}

IntentName = Literal[
    "procedure", "clarify", "unsupported", "benefit", "source",
    "comparison", "refuse", "distance", "unknown",
]


@dataclass
class Intent:
    code: str | None
    intent: str
    ambiguous: bool = False


def extract_intent(question: str) -> Intent:
    """Deterministic, offline intent extraction (also the safety baseline)."""
    q = question.lower().strip()
    if any(x in q for x in ("c-section", "cesarean", "caesarean", "delivery")):
        return Intent(None, "unsupported")
    if "mri" in q:
        if any(x in q for x in ("knee", "lower extremity", "leg", "73721")):
            return Intent("73721", "procedure")
        if any(x in q for x in ("brain", "head", "70551")):
            return Intent("70551", "procedure")
        return Intent(None, "clarify", True)
    for code, (_, terms) in PROCEDURES.items():
        if code in q or any(term in q for term in terms if len(term) > 3):
            return Intent(code, "procedure")
    if any(x in q for x in ("will i pay", "i have to pay", "i actually pay", "will i owe", "out of pocket",
                            "out-of-pocket", "insurance pay", "insurance cover", "my cost", "covered")):
        return Intent(None, "benefit")
    if any(x in q for x in ("where did", "source", "provenance", "cite")):
        return Intent(None, "source")
    if any(x in q for x in ("cheapest", "lowest", "least", "compare", "rank")):
        return Intent(None, "comparison")
    if any(x in q for x in ("guess", "invent", "assume", "make up")):
        return Intent(None, "refuse")
    if any(x in q for x in ("nearest", "near me", "closest")):
        return Intent(None, "distance")
    return Intent(None, "unknown")


def _money(value) -> str:
    return f"${float(value):,.0f}"


_DASH = re.compile(r"\s*[—–]\s*")  # em dash and en dash, with surrounding spaces
_RANGE = re.compile(r"(\d)\s*[—–]\s*(\$?\d)")  # 350–560 -> 350 to 560


def clean(text: str) -> str:
    """House style for every chat reply: no asterisks, no em/en dashes."""
    text = _RANGE.sub(r"\1 to \2", text)
    return _DASH.sub(", ", text).replace("*", "")


def clean_stream(chunks: Iterable[str]) -> Iterator[str]:
    """Apply clean() to streamed text. Trailing spaces/dashes are held back until the
    next chunk arrives, so a dash split across chunks is still replaced correctly."""
    buf, sent = "", 0
    for chunk in chunks:
        buf += chunk
        safe = clean(buf[:len(buf.rstrip(" \t\n—–"))])
        if len(safe) > sent:
            yield safe[sent:]
            sent = len(safe)
    final = clean(buf)
    if len(final) > sent:
        yield final[sent:]


def format_answer(question: str, records: pd.DataFrame, live_mode: bool = False,
                  intent: Intent | None = None) -> str:
    """Deterministic grounded answer. Used offline and as the Claude fallback."""
    return clean(_format_answer(question, records, live_mode, intent))


def _format_answer(question: str, records: pd.DataFrame, live_mode: bool = False,
                   intent: Intent | None = None) -> str:
    intent = intent or extract_intent(question)

    if intent.intent == "procedure" and intent.code:
        if records.empty:
            return "I couldn't find any comparable verified rates for this procedure. I won't estimate or invent a price."
        noun = "verified records" if live_mode else "demo records"
        lo, hi = records.iloc[0], records.iloc[-1]
        text = (
            f"I found **{len(records)} comparable {noun}** for **{PROCEDURES[intent.code][0]}** "
            f"(CPT {intent.code}), Blue Choice PPO outpatient facility rates. "
            f"The lowest is **{lo['hospital_name']}** at **{_money(lo['price'])}**"
        )
        if len(records) > 1:
            spread = float(hi["price"]) - float(lo["price"])
            text += f"; the highest is {_money(hi['price'])}, a **{_money(spread)} spread** for the same service"
        text += ". These are negotiated facility rates, not your final out-of-pocket cost."
        if not live_mode:
            text += " _Demo records are fictional and for development only._"
        return text

    if intent.intent == "clarify":
        return "Which MRI do you mean: a **knee / lower-extremity MRI** (CPT 73721) or a **brain MRI** (CPT 70551)? Both are without contrast."
    if intent.intent == "unsupported":
        return ("That procedure is outside this proof of concept. Delivery bundles, professional fees, anesthesia and "
                "newborn care make those rates hard to compare, so I won't give a price.")
    if intent.intent == "benefit":
        return ("I can show negotiated facility rates, but I can't tell you what you will personally pay. That depends on "
                "your eligibility, deductible, copay, coinsurance, network rules and claim details. Your insurer can give a personal estimate.")
    if intent.intent == "source":
        if records.empty:
            return ("Every live answer cites the official hospital price transparency file, the original record reference "
                    "and the published date. Ask about a procedure first and I'll show the sources.")
        lines = ["Here is where those prices came from:"]
        for _, r in records.head(5).iterrows():
            src = r.get("source_url")
            if pd.notna(src) and src:
                lines.append(f"- **{r['hospital_name']}**: [official file]({src}), row {r['source_row']}, published {r['last_updated']} (record {r['record_id']})")
            else:
                lines.append(f"- **{r['hospital_name']}**: fictional demo record {r['record_id']}, no official source")
        return "\n".join(lines)
    if intent.intent == "distance":
        return ("I don't have reliable distance or travel-time data in this proof of concept, so I can't say which hospital "
                "is nearest. I can compare prices, and you can check location on a map.")
    if intent.intent == "refuse":
        return "I won't make up a price or a hospital. I only answer from records in the curated dataset."
    if intent.intent == "comparison":
        if records.empty:
            return "Tell me which procedure first: a knee MRI, a brain MRI, or an abdomen/pelvis CT."
        cheapest = records.iloc[0]
        return (f"Among the comparable records retrieved, **{cheapest['hospital_name']}** has the lowest Blue Choice PPO "
                f"negotiated rate at **{_money(cheapest['price'])}**. A lower price does not by itself mean better quality or suitability.")
    return ("I can compare Blue Choice PPO outpatient facility rates for a **knee MRI** (CPT 73721), a **brain MRI** "
            "(CPT 70551) or an **abdomen/pelvis CT** (CPT 74176).")


# --------------------------------------------------------------------------- Claude

SYSTEM_PROMPT = """You are CareConnect, a healthcare price transparency assistant built by Perficient.
Answer only supported procedure and hospital questions using the retrieved records you are given.
Never invent prices, hospitals, coverage, distances or availability. Every dollar figure you mention must appear in the retrieved records.
Ask for clarification if the procedure is ambiguous. Compare only equivalent services; never sum unrelated rows.
Explain that prices are Blue Choice PPO negotiated outpatient facility rates, not exact patient costs.
When you cite a record, give its hospital and record ID. If records are marked is_demo=true, say they are fictional demo data.
If data is unavailable, say so. Do not diagnose, recommend treatment, delay emergency care or ask for personal identifiers.
Write in plain, warm language at an 8th-grade reading level. Keep answers under 120 words.
Formatting: write plain sentences. Never use asterisks (no bold, no italics, no asterisk bullets). Never use em dashes or en dashes; use commas, periods or the word "to" instead. If you list items, start each line with a hyphen and a space.
The interface already shows a ranked price table under your answer, so summarize the key takeaway rather than repeating every row."""

INTENT_PROMPT = """Classify the patient's latest message for a price lookup tool that supports only these procedures:
73721 = MRI lower-extremity joint (knee, ankle, hip) without contrast
70551 = MRI brain without contrast
74176 = CT abdomen and pelvis without contrast

Intents: procedure (a supported procedure is identified), clarify (an MRI or scan is mentioned but body part is unclear),
unsupported (any other procedure, e.g. C-section, colonoscopy), benefit (what the patient will personally pay / coverage),
source (where data came from), comparison (cheapest / rank / compare, without naming a new procedure),
refuse (asks you to guess, invent or ignore the data), distance (nearest / closest / travel), unknown (anything else).
Use earlier turns to resolve follow-ups like "what about the brain one?". Set procedure_code only when confident."""


class ClaudeIntent(BaseModel):
    intent: IntentName
    procedure_code: Optional[Literal["73721", "70551", "74176"]] = None


def make_client(api_key: str):
    from anthropic import Anthropic
    return Anthropic(api_key=api_key, max_retries=2, timeout=60.0)


def _history(history: list[dict], limit: int = 6) -> list[dict]:
    turns = [{"role": m["role"], "content": m["content"]} for m in history if m.get("content")][-limit:]
    while turns and turns[0]["role"] != "user":
        turns.pop(0)
    return turns


def claude_intent(client, question: str, history: list[dict]) -> Intent:
    """Structured intent extraction. Rule-based safety intents always win."""
    baseline = extract_intent(question)
    if baseline.intent in ("unsupported", "refuse"):
        return baseline
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in _history(history))
    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=2000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low"},
        system=INTENT_PROMPT,
        messages=[{"role": "user", "content": f"Earlier conversation:\n{convo or '(none)'}\n\nLatest message: {question}"}],
        output_format=ClaudeIntent,
    )
    parsed = response.parsed_output
    if response.stop_reason == "refusal" or parsed is None:
        return baseline
    if parsed.intent == "procedure" and not parsed.procedure_code:
        return Intent(None, "clarify", True)
    return Intent(parsed.procedure_code, parsed.intent, parsed.intent == "clarify")


def stream_grounded_answer(client, question: str, history: list[dict], records: pd.DataFrame,
                           intent: Intent, live_mode: bool) -> Iterator[str]:
    """Stream Claude's plain-language explanation of retrieved records only."""
    cols = ["record_id", "hospital_name", "city", "zip_code", "procedure_code", "procedure_name",
            "plan", "price", "source_url", "source_row", "last_updated", "is_demo"]
    payload = records[cols].to_dict(orient="records") if not records.empty else []
    context = {
        "detected_intent": intent.intent,
        "procedure_code": intent.code,
        "data_mode": "live verified" if live_mode else "demo (fictional)",
        "retrieved_records_sorted_by_price": payload,
        "reference_answer": format_answer(question, records, live_mode, intent),
    }
    messages = _history(history) + [{
        "role": "user",
        "content": f"{question}\n\n<retrieval>\n{json.dumps(context, default=str)}\n</retrieval>",
    }]
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=4000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low"},
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        yield from clean_stream(stream.text_stream)
        final = stream.get_final_message()
    if final.stop_reason == "refusal":
        yield "\n\n" + format_answer(question, records, live_mode, intent)
