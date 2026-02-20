"""Text-to-Speech using Google Cloud TTS (API key or service account)."""
import base64
import json
import tempfile
from pathlib import Path
from typing import Optional

import requests

from app.config import get_settings

TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"


def _synthesize_via_api_key(text: str, api_key: str, language_code: str, voice_name: Optional[str], audio_encoding: str) -> bytes:
    """Use Google TTS REST API with API key."""
    voice = {"languageCode": language_code}
    if voice_name:
        voice["name"] = voice_name
    else:
        voice["ssmlGender"] = "NEUTRAL"

    payload = {
        "input": {"text": text},
        "voice": voice,
        "audioConfig": {"audioEncoding": audio_encoding},
    }

    resp = requests.post(
        f"{TTS_URL}?key={api_key}",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return base64.b64decode(data["audioContent"])


def _synthesize_via_client(text: str, language_code: str, voice_name: Optional[str], audio_encoding: str) -> bytes:
    """Use Google TTS client library (service account)."""
    from google.cloud import texttospeech

    client = texttospeech.TextToSpeechClient()
    input_text = texttospeech.SynthesisInput(text=text)

    voice_kwargs = {"language_code": language_code}
    if voice_name:
        voice_kwargs["name"] = voice_name
    else:
        voice_kwargs["ssml_gender"] = texttospeech.SsmlVoiceGender.NEUTRAL

    voice_params = texttospeech.VoiceSelectionParams(**voice_kwargs)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=getattr(texttospeech.AudioEncoding, audio_encoding),
    )

    response = client.synthesize_speech(
        input=input_text,
        voice=voice_params,
        audio_config=audio_config,
    )
    return response.audio_content


def _ensure_credentials_path(creds_value: Optional[str]) -> Optional[str]:
    """If value is JSON, write to temp file and return path."""
    if not creds_value or not creds_value.strip():
        return None
    value = creds_value.strip()
    if value.startswith("{"):
        try:
            json.loads(value)
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
            tmp.write(value)
            tmp.close()
            return tmp.name
        except json.JSONDecodeError:
            return None
    return value if Path(value).exists() else None


def synthesize_speech(
    text: str,
    language_code: str = "en-US",
    voice_name: Optional[str] = None,
    audio_encoding: str = "MP3",
) -> bytes:
    """Convert text to speech using Google Cloud TTS."""
    import os

    settings = get_settings()

    # Prefer API key (direct)
    if settings.google_api_key:
        return _synthesize_via_api_key(
            text, settings.google_api_key, language_code, voice_name, audio_encoding
        )

    # Fallback: service account
    creds_value = settings.google_application_credentials or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    creds_path = _ensure_credentials_path(creds_value)
    if creds_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path

    return _synthesize_via_client(text, language_code, voice_name, audio_encoding)
