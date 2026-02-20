"""
Test Google Cloud Text-to-Speech.
Usage: python scripts/test_tts.py "Hello, this is a test."
       python scripts/test_tts.py  (uses default text)
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_TEXT = "Hello, this is a test of Google Cloud Text to Speech."


def main():
    text = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TEXT

    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("Set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON path.")
        print("Example: $env:GOOGLE_APPLICATION_CREDENTIALS='path/to/key.json'")
        sys.exit(1)

    from app.services.tts_service import synthesize_speech

    print(f"Synthesizing: {text[:50]}...")
    audio = synthesize_speech(text)
    output = Path(__file__).parent.parent / "audio" / "tts_output.mp3"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(audio)
    print(f"Saved to: {output}")


if __name__ == "__main__":
    main()
