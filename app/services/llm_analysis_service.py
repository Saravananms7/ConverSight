"""LLM-based structured conversation analysis (Gemini)."""
import json
import re
from typing import Any, Dict, List

from app.config import get_settings

STRUCTURED_SCHEMA = {
    "conversation_summary": "str",
    "detected_sentiment": "str (positive|negative|neutral)",
    "customer_intents": "list[str]",
    "key_topics": "list[str]",
    "entities": "list[dict] with type and value",
    "compliance_flags": "list[str]",
    "call_outcome": "str",
}

PROMPT = """Analyze this customer support / call transcript and return a strict JSON object.

Use ONLY information explicitly present in the transcript. No assumptions or fabrications.

Required JSON structure:
{
  "conversation_summary": "Brief 1-2 sentence summary of the call",
  "detected_sentiment": "positive" | "negative" | "neutral" (overall customer tone),
  "customer_intents": ["intent1", "intent2"],
  "key_topics": ["topic1", "topic2"],
  "entities": [{"type": "amount|name|card_last4|timeframe", "value": "..."}],
  "compliance_flags": ["flag if agent violated policy, else empty"],
  "call_outcome": "What was resolved or how the call ended"
}

Transcript:
---
{transcript}
---

Return ONLY valid JSON, no markdown or extra text."""


def analyze_with_llm(transcript: str) -> Dict[str, Any]:
    """
    Use Gemini to produce structured analysis from transcript.
    Falls back to extract_structured_analysis if Gemini is not configured.
    """
    settings = get_settings()
    if not settings.google_api_key:
        # Fallback to rule-based analysis
        from app.services.transcription_service import analyze_text
        from app.services.structured_analysis import extract_structured_analysis
        result = analyze_text(transcript)
        return extract_structured_analysis(transcript, result.to_dict())

    import google.generativeai as genai

    genai.configure(api_key=settings.google_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = PROMPT.format(transcript=transcript[:15000])  # Limit context
    response = model.generate_content(prompt)

    text = (response.text or "").strip()
    # Strip markdown code blocks if present
    if "```json" in text:
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    elif "```" in text:
        text = re.sub(r"^```\w*\s*", "", text)
        text = re.sub(r"\s*```\s*$", "")

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fallback
        from app.services.transcription_service import analyze_text
        from app.services.structured_analysis import extract_structured_analysis
        result = analyze_text(transcript)
        return extract_structured_analysis(transcript, result.to_dict())

    # Normalize to expected schema
    return {
        "conversation_summary": _str(data.get("conversation_summary")),
        "detected_sentiment": _str(data.get("detected_sentiment")),
        "customer_intents": _list_str(data.get("customer_intents")),
        "key_topics": _list_str(data.get("key_topics")),
        "entities": _list_entities(data.get("entities")),
        "compliance_flags": _list_str(data.get("compliance_flags")),
        "call_outcome": _str(data.get("call_outcome")),
    }


def _str(v: Any) -> str:
    return str(v).strip() if v is not None else "Not specified"


def _list_str(v: Any) -> List[str]:
    if isinstance(v, list):
        return [str(x).strip() for x in v if x]
    return ["Not specified"] if not v else [str(v)]


def _list_entities(v: Any) -> List[Dict[str, str]]:
    if not isinstance(v, list):
        return []
    out = []
    for item in v:
        if isinstance(item, dict) and "type" in item and "value" in item:
            out.append({"type": str(item["type"]), "value": str(item["value"])})
    return out


CRITERIA_MATCH_PROMPT = """Given this client configuration and transcript, assess whether the conversation matches the criteria.

Client configuration:
{context}

Transcript:
---
{transcript}
---

Return a JSON object:
{{
  "criteria_matches": true or false,
  "explanation": "Brief explanation of why it matches or does not match the business domain, products, policies, and risk triggers."
}}

Return ONLY valid JSON, no markdown."""


def assess_criteria_match(transcript: str, context_str: str) -> dict:
    """
    Use LLM to assess if transcript matches client criteria.
    Returns {criteria_matches: bool, explanation: str} or defaults if Gemini unavailable.
    """
    defaults = {"criteria_matches": None, "explanation": "Not assessed (GOOGLE_API_KEY not set)"}
    settings = get_settings()
    if not settings.google_api_key:
        return defaults

    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.google_api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = CRITERIA_MATCH_PROMPT.format(
            context=context_str,
            transcript=transcript[:12000],
        )
        response = model.generate_content(prompt)
        text = (response.text or "").strip()
        if "```json" in text:
            text = re.sub(r"^```json\s*", "", text)
            text = re.sub(r"\s*```\s*$", "", text)
        elif "```" in text:
            text = re.sub(r"^```\w*\s*", "", text)
            text = re.sub(r"\s*```\s*$", "")

        data = json.loads(text)
        return {
            "criteria_matches": bool(data.get("criteria_matches", False)),
            "explanation": _str(data.get("explanation")) or "No explanation",
        }
    except Exception:
        return defaults
