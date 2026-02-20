"""Create a test audio file for the /transcribe/audio endpoint.
Downloads a sample with speech from Deepgram's examples, or generates a tone as fallback.
"""
import urllib.request
import wave
import math
import struct
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent.parent / "samples" / "test_audio.wav"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# Sample with actual speech (Apollo 11 spacewalk - public domain)
SAMPLE_URL = "https://github.com/deepgram/deepgram-python-sdk/raw/main/examples/fixtures/audio.wav"


def download_sample():
    """Download sample audio with speech."""
    try:
        urllib.request.urlretrieve(SAMPLE_URL, OUTPUT)
        print(f"Downloaded sample: {OUTPUT}")
        return True
    except Exception as e:
        print(f"Download failed ({e}), creating tone fallback...")
        return False


def create_tone_fallback():
    """Create minimal WAV (tone) - Deepgram may return empty transcript."""
    SAMPLE_RATE, DURATION = 16000, 2
    data = []
    for i in range(SAMPLE_RATE * DURATION):
        t = i / SAMPLE_RATE
        value = int(32767 * 0.3 * math.sin(2 * math.pi * 440 * t))
        data.append(struct.pack("<h", value))
    with wave.open(str(OUTPUT), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"".join(data))
    print(f"Created tone (no speech): {OUTPUT}")
    print("For real testing, record speech or use: python -c \"import urllib.request; urllib.request.urlretrieve('https://github.com/deepgram/deepgram-python-sdk/raw/main/examples/fixtures/audio.wav', 'samples/test_audio.wav')\"")


if __name__ == "__main__":
    if not download_sample():
        create_tone_fallback()
