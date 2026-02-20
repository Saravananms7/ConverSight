"""
Test your own audio file with CoverSight transcription.
With --direct: Whisper (transcribe + detect) → Gemini (translate if needed) → Deepgram (analysis).
Returns JSON: {metadata, transcription, analysis}
Usage: python scripts/test_my_audio.py --direct
"""
import json
import sys
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

API_URL = "http://localhost:8000/transcribe/audio"
ALLOWED = {".mp3", ".mpeg", ".wav", ".m4a", ".ogg", ".webm", ".flac", ".mp4"}
AUDIO_FOLDER = Path(__file__).resolve().parent.parent / "audio"


def get_audio_files():
    """Get supported audio files from the audio folder."""
    if not AUDIO_FOLDER.exists():
        return []
    return sorted(
        f for f in AUDIO_FOLDER.iterdir()
        if f.is_file() and f.suffix.lower() in ALLOWED
    )


def main():
    args = [a for a in sys.argv[1:] if a != "--direct"]
    if args:
        arg = Path(args[0])
        if arg.is_absolute():
            audio_path = arg
        elif (AUDIO_FOLDER / arg.name).exists():
            audio_path = AUDIO_FOLDER / arg.name
        else:
            audio_path = arg
    else:
        files = get_audio_files()
        if not files:
            print(f"No audio files in {AUDIO_FOLDER}")
            print("Put your .mp3, .wav, .m4a etc. files there and run again.")
            sys.exit(1)
        if len(files) == 1:
            audio_path = files[0]
            print(f"Using: {audio_path.name}")
        else:
            print("Files in audio/ folder:")
            for i, f in enumerate(files, 1):
                print(f"  {i}. {f.name}")
            choice = input("Enter number (or filename): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(files):
                audio_path = files[int(choice) - 1]
            else:
                audio_path = AUDIO_FOLDER / choice
                if not audio_path.exists():
                    audio_path = Path(choice)

    if not audio_path.exists():
        print(f"Error: File not found: {audio_path}")
        sys.exit(1)

    suffix = audio_path.suffix.lower()
    if suffix not in ALLOWED:
        print(f"Error: Unsupported format. Allowed: {', '.join(ALLOWED)}")
        sys.exit(1)

    print(f"Transcribing: {audio_path}")

    use_direct = "--direct" in sys.argv
    if use_direct:
        print("Pipeline: Whisper (transcribe + detect) → Gemini (translate if needed) → Deepgram (analysis)")
    print("...")
    if use_direct:
        # Whisper → Gemini (translate) → Deepgram → user's JSON format
        try:
            from app.services.transcription_service import transcribe_whisper_gemini_deepgram_json
            result = transcribe_whisper_gemini_deepgram_json(audio_path)
            print(json.dumps(result, indent=4, ensure_ascii=False))
        except ValueError as e:
            print(f"Error: {e}")
            print("Required: DEEPGRAM_API_KEY, GOOGLE_API_KEY in .env.")
            print("If local Whisper fails (PyTorch DLL): add OPENAI_API_KEY for API fallback.")
            sys.exit(1)
    else:
        # Use API (server must be running)
        try:
            with open(audio_path, "rb") as f:
                response = requests.post(
                    API_URL,
                    files={"file": (audio_path.name, f, f"audio/{suffix[1:] or 'wav'}")},
                )

            if response.status_code != 200:
                print(f"Error {response.status_code}: {response.text}")
                sys.exit(1)

            result = response.json()
            transcript = result.get("transcript", "")
            print("\n--- Transcript ---")
            print(transcript if transcript else "(empty)")
            print("\n--- Full response ---")
            print(result)
        except requests.exceptions.ConnectionError:
            print("Error: Cannot connect. Is the server running? (python run.py)")
            print("Or use --direct to transcribe without the server.")
            sys.exit(1)


if __name__ == "__main__":
    main()
