"""Test the /transcribe/audio endpoint with a sample file."""
import subprocess
import sys
from pathlib import Path

import requests

BASE_URL = "http://localhost:8000"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIO_FILE = PROJECT_ROOT / "samples" / "test_audio.wav"


def main():
    if not AUDIO_FILE.exists():
        print("Creating test audio...")
        subprocess.run(
            [sys.executable, str(Path(__file__).parent / "create_test_audio.py")],
            check=True,
            cwd=str(PROJECT_ROOT),
        )
        print()

    print(f"Testing POST {BASE_URL}/transcribe/audio")
    print(f"Audio file: {AUDIO_FILE}")
    print()

    with open(AUDIO_FILE, "rb") as f:
        files = {"file": (AUDIO_FILE.name, f, "audio/wav")}
        resp = requests.post(f"{BASE_URL}/transcribe/audio", files=files)

    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text}")
        sys.exit(1)

    result = resp.json()
    print("Success!")
    print()
    print("Transcript:", result.get("transcript", "")[:200] + ("..." if len(result.get("transcript", "")) > 200 else ""))


if __name__ == "__main__":
    main()
