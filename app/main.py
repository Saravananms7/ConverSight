"""CoverSight - Audio to Text (Deepgram) + Text to Speech (Google Cloud)."""
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

app = FastAPI(
    title="CoverSight",
    description="Transcribe audio (Deepgram) and synthesize speech (Google Cloud TTS).",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

ALLOWED_EXT = {".mp3", ".mpeg", ".wav", ".m4a", ".ogg", ".webm", ".flac", ".mp4"}
ALLOWED_TEXT_EXT = {".txt"}


def _build_analysis_response(
    transcript: str,
    structured: dict,
    detected_lang: str,
    translated: str | None = None,
    **extra,
) -> dict:
    """Build unified response format for transcribe and text analysis."""
    base = {
        "transcript": transcript,
        "detected_language": lang_code_to_name(detected_lang) or detected_lang or "English",
        "conversation_summary": structured["conversation_summary"],
        "overall_sentiment": structured["detected_sentiment"],
        "primary_customer_intents": structured["customer_intents"],
        "key_topics": structured["key_topics"],
        "entities": structured["entities"],
        **extra,
    }
    if translated is not None:
        base["translated_transcript"] = translated
    return base


def _analyze_text_and_build_response(text: str, filename: str | None = None) -> dict:
    """Analyze text and return unified format (same as transcribe/audio)."""
    text = (text or "").strip()
    if not text:
        out = {
            "transcript": "",
            "detected_language": "Not specified",
            "conversation_summary": "Not specified",
            "overall_sentiment": "Not specified",
            "primary_customer_intents": ["Not specified"],
            "key_topics": ["Not specified"],
            "entities": [],
        }
        if filename:
            out["filename"] = filename
        return out
    detected_lang = detect_language_from_text(text)
    is_english = not detected_lang or detected_lang.startswith("en")

    if not is_english:
        translated = translate_to_english(text, detected_lang)
        result = analyze_text(translated)
        structured = extract_structured_analysis(translated, result.to_dict())
        out = _build_analysis_response(text, structured, detected_lang, translated=translated)
    else:
        result = analyze_text(text)
        structured = extract_structured_analysis(text, result.to_dict())
        out = _build_analysis_response(text, structured, detected_lang)
    if filename:
        out["filename"] = filename
    return out


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
    "/transcribe/audio",
    summary="Transcribe audio to text",
    description="Upload an audio file. Use provider: deepgram (default), whisper (OpenAI API), or whisper-gemini (local Whisper + Gemini translate + Deepgram analyze).",
)
async def transcribe(
    file: UploadFile = File(..., description="Audio file (mp3, wav, m4a, etc.)"),
    provider: str = "deepgram",
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
            analysis_result = analyze_text(translated)
            structured = extract_structured_analysis(translated, analysis_result.to_dict())
            return _build_analysis_response(
                transcript, structured, detected_lang, translated=translated,
                filename=file.filename, provider=provider,
            )
        structured = extract_structured_analysis(transcript, d)
        return _build_analysis_response(
            transcript, structured,
            d.get("detected_language") or "en",
            filename=file.filename, provider=provider,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post(
    "/synthesize/speech",
    summary="Text to Speech",
    description="Convert text to speech using Google Cloud TTS. Returns MP3 audio.",
)
async def synthesize(
    text: str = Form(..., description="Text to convert to speech"),
    language_code: str = Form("en-US", description="Language code (e.g. en-US)"),
    voice_name: Optional[str] = Form(None, description="Voice name (optional)"),
    audio_encoding: str = Form("MP3", description="MP3, LINEAR16, MP3_64_KBPS"),
    _: bool = Depends(verify_api_key),
):
    """Convert text to speech and return audio file."""
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        audio_bytes = synthesize_speech(
            text=text,
            language_code=language_code,
            voice_name=voice_name,
            audio_encoding=audio_encoding,
        )
        media_type = "audio/mpeg" if audio_encoding.upper() == "MP3" else "audio/wav"
        return Response(
            content=audio_bytes,
            media_type=media_type,
            headers={"Content-Disposition": "attachment; filename=speech.mp3"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"TTS failed: {str(e)}. Ensure GOOGLE_APPLICATION_CREDENTIALS is set.",
        )


@app.post(
    "/detect-topics",
    summary="Analyze text (full results)",
    description="Analyze text/transcript and return same format as audio (transcript, detected_language, conversation_summary, overall_sentiment, primary_customer_intents, key_topics, entities). Translates non-English text via Gemini.",
)
async def detect_topics(
    body: dict = Body(..., example={"text": "Can I upgrade my phone? I need a new battery."}),
    _: bool = Depends(verify_api_key),
):
    """Analyze text and return same format as transcribe/audio."""
    text = body.get("text") if isinstance(body, dict) else None
    if text is None:
        raise HTTPException(status_code=400, detail="Missing 'text' field in request body")
    if not isinstance(text, str):
        raise HTTPException(status_code=400, detail="'text' must be a string")

    try:
        return _analyze_text_and_build_response(text)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text analysis failed: {str(e)}")


@app.post(
    "/analyze/text",
    summary="Analyze text file",
    description="Upload a text file (e.g. chat transcript). Returns same format as audio (transcript, detected_language, conversation_summary, overall_sentiment, primary_customer_intents, key_topics, entities). Translates non-English via Gemini.",
)
async def analyze_text_file(
    file: UploadFile = File(..., description="Text file (.txt)"),
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
        return _analyze_text_and_build_response(text, filename=file.filename)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text analysis failed: {str(e)}")


