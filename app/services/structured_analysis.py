"""
Structured conversation analysis - strict JSON output.
Uses ONLY information explicitly present in the transcript.
No assumptions, inferences, or fabrications.
"""
import re
from typing import Any, Dict, List, Optional


def _extract_customer_utterances(transcript: str) -> List[str]:
    """Extract text blocks that follow 'Customer:' (case-insensitive)."""
    utterances: List[str] = []
    for m in re.finditer(
        r"Customer\s*:\s*\n([\s\S]*?)(?=\n(?:Agent|Customer)\s*:|$)",
        transcript,
        re.IGNORECASE,
    ):
        text = m.group(1).strip()
        if text:
            utterances.append(text)
    return utterances


def _extract_entities(transcript: str) -> List[Dict[str, str]]:
    """Extract entities from transcript - amounts, names, card digits, timeframes."""
    entities: List[Dict[str, str]] = []
    seen: set = set()

    # Currency amounts: ₹7,850 or $100 or 7,850 (near transaction/rupees)
    for m in re.finditer(r"([₹$€£])\s*([\d,]+(?:\.\d{2})?)", transcript):
        val = f"{m.group(1)}{m.group(2).replace(',', '')}"
        if val not in seen:
            seen.add(val)
            entities.append({"type": "amount", "value": val})
    for m in re.finditer(r"([\d,]+(?:\.\d{2})?)\s*(?:rupees?|dollars?|USD|INR)\b", transcript, re.IGNORECASE):
        val = m.group(1).replace(",", "")
        if val not in seen and len(val) <= 10:
            seen.add(val)
            entities.append({"type": "amount", "value": val})

    # Card digits (last 4)
    for m in re.finditer(r"\b(\d{4})\b", transcript):
        # Context: "last four digits", "4482", etc.
        ctx = transcript[max(0, m.start() - 50) : m.end() + 20].lower()
        if "digit" in ctx or "card" in ctx or "confirm" in ctx:
            val = m.group(1)
            if val not in seen:
                seen.add(val)
                entities.append({"type": "card_last4", "value": val})

    # Names after "name is" or "Mr./Ms."
    for m in re.finditer(r"(?:name is|I'm|I am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", transcript, re.IGNORECASE):
        val = m.group(1).strip()
        if val not in seen and len(val) > 2:
            seen.add(val)
            entities.append({"type": "name", "value": val})
    for m in re.finditer(r"(?:Mr\.?|Ms\.?|Mrs\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", transcript):
        val = m.group(1).strip()
        if val not in seen and len(val) > 2:
            seen.add(val)
            entities.append({"type": "name", "value": val})

    # Timeframes: "5-7 working days", "20 minutes ago"
    for m in re.finditer(r"(\d+(?:\s*-\s*\d+)?\s*(?:working\s+)?days?|\d+\s+minutes?\s+ago)", transcript, re.IGNORECASE):
        val = m.group(1).strip()
        if val not in seen:
            seen.add(val)
            entities.append({"type": "timeframe", "value": val})

    return entities


def _infer_call_outcome(transcript: str) -> str:
    """Infer call outcome from explicit statements only. Conservative."""
    t = transcript.lower()
    outcomes: List[str] = []

    if "card has been blocked" in t or ("blocked" in t and "card" in t):
        outcomes.append("Card blocked")
    if "dispute" in t or "complaint" in t or "investigation" in t:
        outcomes.append("Dispute/complaint raised")
    if "thanks" in t or "thank you" in t:
        outcomes.append("Customer acknowledged")
    if "no" in t and ("anything else" in t or "help" in t):
        outcomes.append("Call ended")

    if not outcomes:
        return "Not specified"
    return ". ".join(outcomes)


def extract_structured_analysis(
    transcript: str,
    deepgram_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Extract structured analysis from transcript.
    Uses ONLY explicit information. No assumptions or hallucinations.

    Args:
        transcript: Raw conversation text
        deepgram_result: Optional dict from analyze_text().to_dict() or transcribe_audio().to_dict()

    Returns:
        Strict JSON structure per requirements.
    """
    dr = deepgram_result or {}

    # conversation_summary - from Deepgram if available, else Not specified
    summary_obj = dr.get("summary") or {}
    conversation_summary = summary_obj.get("short", "").strip() or "Not specified"

    # detected_sentiment - overall emotional tone of CUSTOMER
    sentiment_avg = dr.get("sentiment_average") or {}
    sent = str(sentiment_avg.get("sentiment", "") or "").lower()
    if sent in ("positive", "negative", "neutral"):
        detected_sentiment = sent
    else:
        detected_sentiment = "Not specified"

    # customer_intents - from intent segments that match customer utterances
    customer_utterances = _extract_customer_utterances(transcript)
    intent_segments = dr.get("intent_segments") or []
    customer_intents: List[str] = []
    seen_intents: set = set()
    for seg in intent_segments:
        seg_text = (seg.get("text") or "").strip()
        # Match if segment overlaps with a customer utterance (normalize for comparison)
        seg_norm = " ".join(seg_text.lower().split())[:50]
        is_customer = any(
            seg_norm in u.lower() or u.lower()[:50] in seg_text.lower()
            for u in customer_utterances
        ) if customer_utterances else True
        if is_customer:
            for i in seg.get("intents") or []:
                intent_name = (i.get("intent") or "").strip()
                if intent_name and intent_name not in seen_intents:
                    seen_intents.add(intent_name)
                    customer_intents.append(intent_name)
    if not customer_intents:
        customer_intents = ["Not specified"]

    # key_topics - from topic segments
    topic_segments = dr.get("topic_segments") or []
    key_topics: List[str] = []
    seen_topics: set = set()
    for seg in topic_segments:
        for t in seg.get("topics") or []:
            topic_name = (t.get("topic") or "").strip()
            if topic_name and topic_name not in seen_topics:
                seen_topics.add(topic_name)
                key_topics.append(topic_name)
    if not key_topics:
        key_topics = ["Not specified"]

    # entities
    entities = _extract_entities(transcript)
    if not entities:
        entities = []

    # compliance_flags - only if explicit violations visible
    compliance_flags: List[str] = []

    # call_outcome
    call_outcome = _infer_call_outcome(transcript)

    return {
        "conversation_summary": conversation_summary,
        "detected_sentiment": detected_sentiment,
        "customer_intents": customer_intents,
        "key_topics": key_topics,
        "entities": entities,
        "compliance_flags": compliance_flags,
        "call_outcome": call_outcome,
    }
