"""CoverSight - Audio to Text (Deepgram) + Text to Speech (Google Cloud)."""
import json
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header, Body
from fastapi.responses import Response

from app.config import get_settings
from app.services.transcription_service import (
    transcribe_audio,
    transcribe_audio_provider,
    analyze_text,
    translate_to_english,
    detect_language_from_text,
    lang_code_to_name,
)
from app.services.structured_analysis import extract_structured_analysis
from app.services.tts_service import synthesize_speech
from app.services.policy_service import store_policy_in_supabase, run_policy_rag_safe

app = FastAPI(
    title="CoverSight",
    description="Transcribe audio (Deepgram) and synthesize speech (Google Cloud TTS).",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

ALLOWED_EXT = {".mp3", ".mpeg", ".wav", ".m4a", ".ogg", ".webm", ".flac", ".mp4"}
ALLOWED_TEXT_EXT = {".txt"}


def _parse_client_config(config: str | dict | None) -> dict | None:
    """Parse client_config from JSON string or dict. Returns None if invalid or empty."""
    if config is None:
        return None
    if isinstance(config, dict):
        return config if config else None
    if isinstance(config, str) and config.strip():
        try:
            data = json.loads(config)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _build_client_context_str(config: dict) -> str:
    """Build context string from client config for prepending to transcript."""
    parts = ["Client context (assess whether transcript matches these criteria):"]
    if config.get("business_domain"):
        parts.append(f"- Business domain: {config['business_domain']}")
    if config.get("products_or_services"):
        p = config["products_or_services"]
        val = ", ".join(p) if isinstance(p, list) else str(p)
        parts.append(f"- Products/services: {val}")
    if config.get("policies_or_rules"):
        p = config["policies_or_rules"]
        val = "; ".join(p) if isinstance(p, list) else str(p)
        parts.append(f"- Policies/rules: {val}")
    if config.get("risk_or_compliance_triggers"):
        r = config["risk_or_compliance_triggers"]
        val = ", ".join(r) if isinstance(r, list) else str(r)
        parts.append(f"- Risk/compliance triggers: {val}")
    return "\n".join(parts)


def _text_with_context(transcript: str, client_config: dict | None) -> str:
    """Prepend client context to transcript for Deepgram analysis."""
    if not client_config:
        return transcript
    ctx = _build_client_context_str(client_config)
    return f"{ctx}\n\nTranscript:\n{transcript}"


def _build_analysis_response(
    transcript: str,
    structured: dict,
    detected_lang: str,
    translated: str | None = None,
    client_config: dict | None = None,
    policy_rag_report: list | None = None,
    **extra,
) -> dict:
    """Build clean unified response for transcribe and text analysis."""
    lang_name = lang_code_to_name(detected_lang) or detected_lang or "English"

    # Policy violation: extract violations only
    policy_violation = None
    if policy_rag_report is not None:
        def _is_violation(analysis: dict) -> bool:
            v = analysis.get("violation")
            if v is True:
                return True
            if isinstance(v, str) and v.lower() in ("true", "yes", "1"):
                return True
            return False

        violations = [
            {
                "segment": r["transcript_chunk"],
                "reason": r["analysis"].get("reason", ""),
                "violated_policy": r["analysis"].get("violated_policy_excerpt", ""),
            }
            for r in policy_rag_report
            if _is_violation(r.get("analysis", {}))
        ]
        policy_violation = {
            "has_violations": len(violations) > 0,
            "count": len(violations),
            "violations": violations,
        }

    return {
        "transcript": transcript,
        "translation": translated if translated else None,
        "detected_language": lang_name,
        "topics": structured.get("key_topics") or ["Not specified"],
        "sentiment": structured.get("detected_sentiment") or "Not specified",
        "intent": structured.get("customer_intents") or ["Not specified"],
        "policy_violation": policy_violation,
        "summary": structured.get("conversation_summary") or "Not specified",
    }


def _run_rag_and_build_response(
    text: str,
    filename: str | None = None,
    client_config: dict | None = None,
) -> dict:
    """Analyze text and return unified format (same as transcribe/audio)."""
    text = (text or "").strip()
    if not text:
        return {
            "transcript": "",
            "translation": None,
            "detected_language": "Not specified",
            "topics": ["Not specified"],
            "sentiment": "Not specified",
            "intent": ["Not specified"],
            "policy_violation": None,
            "summary": "Not specified",
        }
    detected_lang = detect_language_from_text(text)
    is_english = not detected_lang or detected_lang.startswith("en")

    policy_rag_report = run_policy_rag_safe(text)

    if not is_english:
        translated = translate_to_english(text, detected_lang)
        text_for_analysis = _text_with_context(translated, client_config)
        result = analyze_text(text_for_analysis)
        structured = extract_structured_analysis(translated, result.to_dict())
        return _build_analysis_response(
            text, structured, detected_lang, translated=translated,
            client_config=client_config, policy_rag_report=policy_rag_report,
        )
    text_for_analysis = _text_with_context(text, client_config)
    result = analyze_text(text_for_analysis)
    structured = extract_structured_analysis(text, result.to_dict())
    return _build_analysis_response(
        text, structured, detected_lang,
        client_config=client_config, policy_rag_report=policy_rag_report,
    )


async def verify_api_key(x_api_key: str | None = Header(None)):
    """Optional API key verification."""
    settings = get_settings()
    if settings.api_secret_key and x_api_key != settings.api_secret_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True


@app.get("/")
async def root():
    return {
        "service": "CoverSight",
        "version": "1.0.0",
        "description": "Audio to Text (Deepgram) + Text to Speech (Google Cloud)",
        "docs": "/docs",
        "endpoints": {
            "policy": "POST /policy",
            "transcribe": "POST /transcribe/audio",
            "synthesize": "POST /synthesize/speech",
            "detect_topics": "POST /detect-topics",
            "analyze_text_file": "POST /analyze/text",
        },
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post(
    "/policy",
    summary="Upload policy document",
    description="Upload policy text. Generates embeddings and stores locally (data/policy_embeddings.json). Required before transcribe/analyze can run policy RAG.",
)
async def upload_policy(
    file: UploadFile = File(None, description="Policy text file (.txt)"),
    policy_text: Optional[str] = Form(None, description="Or paste policy text directly"),
    _: bool = Depends(verify_api_key),
):
    """Store policy chunks and embeddings for RAG."""
    text = None
    if file and file.filename:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix and suffix != ".txt":
            raise HTTPException(status_code=400, detail="Policy file must be .txt")
        contents = await file.read()
        try:
            text = contents.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File must be valid UTF-8")
    elif policy_text:
        text = policy_text

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Provide policy via file upload or policy_text form field")

    try:
        result = store_policy_in_supabase(text.strip())
        log_msg = (
            f"Policy embeddings created: {result['chunks_count']} chunks "
            f"(storage: {result['storage']})"
        )
        return {"message": "Policy stored successfully", "log": log_msg, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Policy storage failed: {str(e)}")


@app.post(
    "/transcribe/audio",
    summary="Transcribe audio to text",
    description="Upload an audio file. Optional client_config (JSON): business_domain, products_or_services, policies_or_rules, risk_or_compliance_triggers. Context is prepended to transcript before Deepgram analysis; LLM assesses if criteria match.",
)
async def transcribe(
    file: UploadFile = File(..., description="Audio file (mp3, wav, m4a, etc.)"),
    provider: str = Form("deepgram"),
    client_config: Optional[str] = Form(None, description="JSON: {business_domain, products_or_services, policies_or_rules, risk_or_compliance_triggers}"),
    _: bool = Depends(verify_api_key),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format. Allowed: {', '.join(ALLOWED_EXT)}",
        )

    contents = await file.read()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        cfg = _parse_client_config(client_config)
        if provider.lower() in ("whisper", "whisper-gemini"):
            result = transcribe_audio_provider(tmp_path, provider)
        else:
            result = transcribe_audio(tmp_path)
        d = result.to_dict()
        transcript = d.get("transcript", "")
        detected_lang = (d.get("detected_language") or "").strip().lower()
        is_english = not detected_lang or detected_lang.startswith("en")

        if not is_english and transcript.strip():
            translated = translate_to_english(transcript, detected_lang)
            policy_rag_report = run_policy_rag_safe(translated)
            text_for_analysis = _text_with_context(translated, cfg)
            analysis_result = analyze_text(text_for_analysis)
            structured = extract_structured_analysis(translated, analysis_result.to_dict())
            return _build_analysis_response(
                transcript, structured, detected_lang, translated=translated,
                client_config=cfg, policy_rag_report=policy_rag_report,
                filename=file.filename, provider=provider,
            )
        policy_rag_report = run_policy_rag_safe(transcript)
        if cfg:
            text_for_analysis = _text_with_context(transcript, cfg)
            analysis_result = analyze_text(text_for_analysis)
            structured = extract_structured_analysis(transcript, analysis_result.to_dict())
        else:
            structured = extract_structured_analysis(transcript, d)
        return _build_analysis_response(
            transcript, structured,
            d.get("detected_language") or "en",
            client_config=cfg, policy_rag_report=policy_rag_report,
            filename=file.filename, provider=provider,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        tmp_path.unlink(missing_ok=True)



@app.post(
    "/detect-topics",
    summary="Analyze text (full results)",
    description="Analyze text/transcript. Optional client_config (JSON) for domain-specific analysis and criteria match assessment.",
)
async def detect_topics(
    body: dict = Body(
        ...,
        example={
            "text": "Can I upgrade my phone? I need a new battery.",
            "client_config": {"business_domain": "telecom", "products_or_services": ["mobile plans"]},
        },
    ),
    _: bool = Depends(verify_api_key),
):
    """Analyze text and return same format as transcribe/audio."""
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Request body must be JSON object")
    text = body.get("text")
    if text is None:
        raise HTTPException(status_code=400, detail="Missing 'text' field in request body")
    if not isinstance(text, str):
        raise HTTPException(status_code=400, detail="'text' must be a string")

    try:
        cfg = _parse_client_config(body.get("client_config"))
        return _run_rag_and_build_response(text, client_config=cfg)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text analysis failed: {str(e)}")


@app.post(
    "/analyze/text",
    summary="Analyze text file",
    description="Upload a text file. Optional client_config (JSON form field) for domain-specific analysis and criteria match assessment.",
)
async def analyze_text_file(
    file: UploadFile = File(..., description="Text file (.txt)"),
    client_config: Optional[str] = Form(None, description="JSON: {business_domain, products_or_services, policies_or_rules, risk_or_compliance_triggers}"),
    _: bool = Depends(verify_api_key),
):
    """Analyze a text file and return same format as transcribe/audio."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_TEXT_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format. Allowed: {', '.join(ALLOWED_TEXT_EXT)}",
        )

    contents = await file.read()
    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be valid UTF-8 text")

    try:
        cfg = _parse_client_config(client_config)
        return _run_rag_and_build_response(text, filename=file.filename, client_config=cfg)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text analysis failed: {str(e)}")


