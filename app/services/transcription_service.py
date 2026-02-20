"""Audio-to-text transcription via Deepgram - auto-detect language, no explicit language option."""
from pathlib import Path
from typing import Any, List, Optional

import httpx

from app.config import get_settings

# Longer timeout for large file uploads to Deepgram (write timeout in seconds)
_DEEPGRAM_UPLOAD_TIMEOUT = httpx.Timeout(60.0, write=180.0)


class TranscriptionResult:
    """Result of transcription with optional language, sentiment, intent, topic, and summary metadata."""

    def __init__(
        self,
        transcript: str,
        detected_language: Optional[str] = None,
        language_confidence: Optional[float] = None,
        sentiment_segments: Optional[List[dict]] = None,
        sentiment_average: Optional[dict] = None,
        intent_segments: Optional[List[dict]] = None,
        topic_segments: Optional[List[dict]] = None,
        summary: Optional[dict] = None,
    ):
        self.transcript = transcript
        self.detected_language = detected_language
        self.language_confidence = language_confidence
        self.sentiment_segments = sentiment_segments or []
        self.sentiment_average = sentiment_average
        self.intent_segments = intent_segments or []
        self.topic_segments = topic_segments or []
        self.summary = summary

    @property
    def detected_language_name(self) -> Optional[str]:
        """Full language name (e.g. 'German') when detected_language is set."""
        if self.detected_language is None:
            return None
        return _lang_code_to_name(self.detected_language)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"transcript": self.transcript}
        if self.detected_language is not None:
            d["detected_language"] = self.detected_language
            d["detected_language_name"] = self.detected_language_name
        if self.language_confidence is not None:
            d["language_confidence"] = self.language_confidence
        if self.sentiment_segments or self.sentiment_average is not None:
            if self.sentiment_segments:
                d["sentiment_segments"] = self.sentiment_segments
            if self.sentiment_average is not None:
                d["sentiment_average"] = self.sentiment_average
        if self.intent_segments:
            d["intent_segments"] = self.intent_segments
        if self.topic_segments:
            d["topic_segments"] = self.topic_segments
        if self.summary is not None:
            d["summary"] = self.summary
        return d

# Language code to full name (Deepgram BCP-47)
LANG_CODE_TO_NAME = {
    "ar": "Arabic", "bg": "Bulgarian", "bn": "Bengali", "ca": "Catalan",
    "cs": "Czech", "da": "Danish", "de": "German", "el": "Greek",
    "en": "English", "es": "Spanish", "et": "Estonian", "fi": "Finnish",
    "fr": "French", "hi": "Hindi", "hu": "Hungarian", "id": "Indonesian",
    "it": "Italian", "ja": "Japanese", "ko": "Korean", "lt": "Lithuanian",
    "lv": "Latvian", "mr": "Marathi", "ms": "Malay", "nl": "Dutch",
    "no": "Norwegian", "pl": "Polish", "pt": "Portuguese", "ro": "Romanian",
    "ru": "Russian", "sk": "Slovak", "sv": "Swedish", "ta": "Tamil",
    "te": "Telugu", "th": "Thai", "tr": "Turkish", "uk": "Ukrainian",
    "vi": "Vietnamese", "zh": "Chinese",
    "de-CH": "German (Switzerland)", "nl-BE": "Flemish",
}


def _lang_code_to_name(code: str) -> str:
    """Return full language name from BCP-47 code. Falls back to code if unknown."""
    if not code:
        return ""
    code = code.strip()
    if code in LANG_CODE_TO_NAME:
        return LANG_CODE_TO_NAME[code]
    base = code.split("-")[0].lower()
    return LANG_CODE_TO_NAME.get(base, code)


def lang_code_to_name(code: str) -> str:
    """Return full language name from BCP-47 code."""
    return _lang_code_to_name(code)


def _transcribe_deepgram(audio_path: Path) -> TranscriptionResult:
    """Transcribe using Deepgram Nova-3 - auto-detect language only (no explicit language param)."""
    from deepgram import DeepgramClient, ListenRESTOptions

    settings = get_settings()
    client = DeepgramClient(api_key=settings.deepgram_api_key)

    # detect_language=true: identifies dominant language, supports 40+ languages
    # sentiment=true: sentiment per segment + average (English only; may be empty for other langs)
    # intents=true: speaker intent per segment (English only; may be empty for other langs)
    # topics=true: key topics per segment (English only; may be empty for other langs)
    # summarize=v2: brief summary of audio (English only; requires 50+ words)
    options = ListenRESTOptions(
        model="nova-3-general",
        punctuate=True,
        detect_language=True,
        sentiment=True,
        intents=True,
        topics=True,
        summarize="v2",
    )

    with open(audio_path, "rb") as audio:
        source = {"buffer": audio.read()}
        response = client.listen.rest.v("1").transcribe_file(
            source, options, timeout=_DEEPGRAM_UPLOAD_TIMEOUT
        )

    transcript = ""
    detected_language = None
    language_confidence = None
    sentiment_segments: List[dict] = []
    sentiment_average: Optional[dict] = None
    intent_segments: List[dict] = []
    topic_segments: List[dict] = []
    summary: Optional[dict] = None

    def _get(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _results_field(name: str) -> Any:
        if hasattr(response, "results") and response.results:
            return getattr(response.results, name, None)
        if isinstance(response, dict):
            return response.get("results", {}).get(name)
        return None

    try:
        channels = _results_field("channels")
        if channels:
            ch = channels[0]
            alts = _get(ch, "alternatives") or []
            if alts:
                transcript = (_get(alts[0], "transcript") or "").strip()
            detected_language = _get(ch, "detected_language")
            conf = _get(ch, "language_confidence")
            if conf is not None:
                language_confidence = float(conf)

        sentiments = _results_field("sentiments")
        if sentiments:
            segs = _get(sentiments, "segments") or []
            for s in segs:
                sentiment_segments.append({
                    "text": _get(s, "text", ""),
                    "start_word": _get(s, "start_word", 0),
                    "end_word": _get(s, "end_word", 0),
                    "sentiment": str(_get(s, "sentiment", "")) or "neutral",
                    "sentiment_score": float(_get(s, "sentiment_score", 0) or 0),
                })
            avg = _get(sentiments, "average")
            if avg:
                sentiment_average = {
                    "sentiment": str(_get(avg, "sentiment", "")) or "neutral",
                    "sentiment_score": float(_get(avg, "sentiment_score", 0) or 0),
                }

        # Extract intents (English only; may be absent for other languages)
        intents_obj = _results_field("intents")
        if intents_obj:
            segs = _get(intents_obj, "segments") or []
            for s in segs:
                ints = _get(s, "intents") or []
                intent_segments.append({
                    "text": _get(s, "text", ""),
                    "start_word": _get(s, "start_word", 0),
                    "end_word": _get(s, "end_word", 0),
                    "intents": [
                        {"intent": _get(i, "intent", ""), "confidence_score": float(_get(i, "confidence_score", 0) or 0)}
                        for i in ints
                    ],
                })

        # Extract topics (English only; may be absent for other languages)
        topics_obj = _results_field("topics")
        if topics_obj:
            segs = _get(topics_obj, "segments") or []
            for s in segs:
                tops = _get(s, "topics") or []
                topic_segments.append({
                    "text": _get(s, "text", ""),
                    "start_word": _get(s, "start_word", 0),
                    "end_word": _get(s, "end_word", 0),
                    "topics": [
                        {"topic": _get(t, "topic", ""), "confidence_score": float(_get(t, "confidence_score", 0) or 0)}
                        for t in tops
                    ],
                })

        # Extract summary (English only; requires 50+ words; may be absent for other languages)
        summary_obj = _results_field("summary")
        if summary_obj:
            summary = {
                "result": _get(summary_obj, "result", ""),
                "short": _get(summary_obj, "short", ""),
            }
    except (AttributeError, IndexError, KeyError):
        pass

    return TranscriptionResult(
        transcript=transcript,
        detected_language=detected_language,
        language_confidence=language_confidence,
        sentiment_segments=sentiment_segments,
        sentiment_average=sentiment_average,
        intent_segments=intent_segments,
        topic_segments=topic_segments,
        summary=summary,
    )


def transcribe_audio(audio_path: Path) -> TranscriptionResult:
    """Transcribe audio using Deepgram only. Language is auto-detected."""
    settings = get_settings()
    if not settings.deepgram_api_key:
        raise ValueError("Set DEEPGRAM_API_KEY in .env")
    return _transcribe_deepgram(audio_path)


def transcribe_whisper(audio_path: Path) -> TranscriptionResult:
    """Transcribe audio using OpenAI Whisper API. Returns transcript only (no sentiment/intents)."""
    from openai import OpenAI

    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("Set OPENAI_API_KEY in .env for Whisper")

    client = OpenAI(api_key=settings.openai_api_key)
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(model="whisper-1", file=f)

    transcript = (response.text or "").strip()
    return TranscriptionResult(transcript=transcript)


def transcribe_audio_provider(audio_path: Path, provider: str = "deepgram") -> TranscriptionResult:
    """Transcribe using specified provider: 'deepgram', 'whisper' (OpenAI API), or 'whisper-gemini' (local Whisper + Gemini translate + Deepgram analyze)."""
    if provider.lower() == "whisper":
        return transcribe_whisper(audio_path)
    if provider.lower() == "whisper-gemini":
        return transcribe_whisper_gemini_deepgram(audio_path)
    return transcribe_audio(audio_path)


def _transcribe_whisper_local(audio_path: Path) -> tuple[str, str]:
    """Transcribe using local Whisper. Returns (transcript, detected_language_code)."""
    import whisper

    model = whisper.load_model("turbo")  # tiny, base, small, medium, large, turbo
    result = model.transcribe(str(audio_path))
    transcript = (result.get("text") or "").strip()
    detected_lang = (result.get("language") or "en").lower()
    return transcript, detected_lang


def _transcribe_whisper_api(audio_path: Path) -> tuple[str, str]:
    """Transcribe using OpenAI Whisper API (no PyTorch). Returns (transcript, detected_language_code)."""
    from openai import OpenAI

    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("Set OPENAI_API_KEY in .env for Whisper API fallback")

    client = OpenAI(api_key=settings.openai_api_key)
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(model="whisper-1", file=f)
    transcript = (response.text or "").strip()
    # OpenAI API doesn't return language; use langdetect if available
    detected_lang = "en"
    if transcript:
        try:
            import langdetect
            detected_lang = (langdetect.detect(transcript) or "en").lower()
        except Exception:
            pass
    return transcript, detected_lang


def detect_language_from_text(text: str) -> str:
    """Detect language code from text (e.g. 'en', 'hi'). Returns 'en' if detection fails."""
    if not (text or "").strip():
        return "en"
    try:
        import langdetect
        return (langdetect.detect(text) or "en").lower()
    except Exception:
        return "en"


def translate_to_english(text: str, from_lang_code: str) -> str:
    """Translate non-English text to English via Gemini. Returns original if already English or on failure."""
    if not (text or "").strip() or not (from_lang_code or "").strip():
        return text or ""
    code = (from_lang_code or "").strip().lower()
    if code.startswith("en"):
        return text
    lang_name = _lang_code_to_name(from_lang_code)
    try:
        return _translate_with_gemini(text, lang_name)
    except Exception:
        return text


def _translate_with_gemini(text: str, from_lang_name: str) -> str:
    """Translate text to English using Gemini. from_lang_name = full name (e.g. 'Hindi')."""
    settings = get_settings()
    if not settings.google_api_key:
        raise ValueError("Set GOOGLE_API_KEY in .env for Gemini translation")

    prompt = f"Translate the following text from {from_lang_name} to English. Provide ONLY the translated text:\n\n{text}"

    # Try new google-genai SDK first (gemini-3-flash-preview)
    try:
        from google import genai
        client = genai.Client(api_key=settings.google_api_key)
        response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
        translated = (response.text or "").strip()
        if translated:
            return translated
    except Exception:
        pass

    # Fallback: legacy google-generativeai (gemini-1.5-flash)
    import google.generativeai as genai
    genai.configure(api_key=settings.google_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    translated = (response.text or "").strip()
    if not translated:
        raise ValueError("Gemini returned empty translation")
    return translated


def transcribe_whisper_gemini_deepgram(audio_path: Path) -> TranscriptionResult:
    """
    Full pipeline: Whisper (local) for transcription + language detection
    → Gemini for translation (if non-English)
    → Deepgram for analysis (sentiment, intents, topics, summary).
    """
    settings = get_settings()
    if not settings.deepgram_api_key:
        raise ValueError("Set DEEPGRAM_API_KEY in .env")

    # Step 1: Local Whisper; fallback to OpenAI API when PyTorch DLL fails
    try:
        transcript, detected_lang = _transcribe_whisper_local(audio_path)
    except (OSError, ImportError):
        transcript, detected_lang = _transcribe_whisper_api(audio_path)
    detected_lang_name = _lang_code_to_name(detected_lang)
    translated_text = transcript

    # Step 2: Translate to English if needed (Deepgram analysis is English-only)
    if detected_lang != "en" and transcript.strip():
        try:
            translated_text = _translate_with_gemini(transcript, detected_lang_name)
        except Exception:
            translated_text = transcript  # fallback to original

    # Step 3: Deepgram text analysis (sentiment, intents, topics, summary)
    if not translated_text.strip():
        return TranscriptionResult(
            transcript=transcript,
            detected_language=detected_lang,
        )

    analysis_result = analyze_text(translated_text)
    # Merge: keep original transcript, use analysis from translated text
    return TranscriptionResult(
        transcript=transcript,
        detected_language=detected_lang,
        language_confidence=analysis_result.language_confidence,
        sentiment_segments=analysis_result.sentiment_segments,
        sentiment_average=analysis_result.sentiment_average,
        intent_segments=analysis_result.intent_segments,
        topic_segments=analysis_result.topic_segments,
        summary=analysis_result.summary,
    )


def analyze_text(text: str) -> TranscriptionResult:
    """
    Analyze text using Deepgram's Text Intelligence API (read endpoint).
    Returns full results (transcript, sentiment, intents, topics, summary) in the same
    format as audio transcription. English only.
    """
    from deepgram import DeepgramClient
    from deepgram.clients.analyze.v1.options import AnalyzeOptions

    settings = get_settings()
    if not settings.deepgram_api_key:
        raise ValueError("Set DEEPGRAM_API_KEY in .env")

    text = (text or "").strip()
    if not text:
        return TranscriptionResult(transcript="")

    client = DeepgramClient(api_key=settings.deepgram_api_key)
    options = AnalyzeOptions(
        topics=True,
        sentiment=True,
        intents=True,
        summarize=True,
        language="en",
    )
    source = {"buffer": text.encode("utf-8")}
    headers = {"Content-Type": "text/plain; charset=utf-8"}

    response = client.read.analyze.v("1").analyze_text(
        source, options, headers=headers
    )

    transcript = text
    detected_language = None
    language_confidence = None
    sentiment_segments: List[dict] = []
    sentiment_average: Optional[dict] = None
    intent_segments: List[dict] = []
    topic_segments: List[dict] = []
    summary: Optional[dict] = None

    def _get(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _results_field(name: str) -> Any:
        if hasattr(response, "results") and response.results:
            return getattr(response.results, name, None)
        if isinstance(response, dict):
            return response.get("results", {}).get(name)
        return None

    try:
        metadata = getattr(response, "metadata", None)
        if metadata:
            detected_language = _get(metadata, "language") or "en"

        sentiments = _results_field("sentiments")
        if sentiments:
            segs = _get(sentiments, "segments") or []
            for s in segs:
                sentiment_segments.append({
                    "text": _get(s, "text", ""),
                    "start_word": _get(s, "start_word", 0),
                    "end_word": _get(s, "end_word", 0),
                    "sentiment": str(_get(s, "sentiment", "")) or "neutral",
                    "sentiment_score": float(_get(s, "sentiment_score", 0) or 0),
                })
            avg = _get(sentiments, "average")
            if avg:
                sentiment_average = {
                    "sentiment": str(_get(avg, "sentiment", "")) or "neutral",
                    "sentiment_score": float(_get(avg, "sentiment_score", 0) or 0),
                }

        intents_obj = _results_field("intents")
        if intents_obj:
            segs = _get(intents_obj, "segments") or []
            for s in segs:
                ints = _get(s, "intents") or []
                intent_segments.append({
                    "text": _get(s, "text", ""),
                    "start_word": _get(s, "start_word", 0),
                    "end_word": _get(s, "end_word", 0),
                    "intents": [
                        {"intent": _get(i, "intent", ""), "confidence_score": float(_get(i, "confidence_score", 0) or 0)}
                        for i in ints
                    ],
                })

        topics_obj = _results_field("topics")
        if topics_obj:
            segs = _get(topics_obj, "segments") or []
            for s in segs:
                tops = _get(s, "topics") or []
                topic_segments.append({
                    "text": _get(s, "text", ""),
                    "start_word": _get(s, "start_word", 0),
                    "end_word": _get(s, "end_word", 0),
                    "topics": [
                        {"topic": _get(t, "topic", ""), "confidence_score": float(_get(t, "confidence_score", 0) or 0)}
                        for t in tops
                    ],
                })

        summary_obj = _results_field("summary")
        if summary_obj:
            summary_text = _get(summary_obj, "text", "")
            if summary_text:
                summary = {"result": "success", "short": summary_text}
    except (AttributeError, IndexError, KeyError):
        pass

    return TranscriptionResult(
        transcript=transcript,
        detected_language=detected_language,
        language_confidence=language_confidence,
        sentiment_segments=sentiment_segments,
        sentiment_average=sentiment_average,
        intent_segments=intent_segments,
        topic_segments=topic_segments,
        summary=summary,
    )
