"""
Test chat/transcript files with CoverSight text analysis.
Uses Deepgram Text Intelligence - full results (sentiment, intents, topics, summary).
Usage:
  python scripts/test_chats.py --direct           # Full analysis, no server
  python scripts/test_chats.py --direct --structured  # Strict JSON output only
"""
import json
import sys
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

API_URL = "http://localhost:8000/analyze/text"
ALLOWED = {".txt"}
CHATS_FOLDER = Path(__file__).resolve().parent.parent / "chats"


def get_chat_files():
    """Get .txt files from the chats folder."""
    if not CHATS_FOLDER.exists():
        return []
    return sorted(
        f for f in CHATS_FOLDER.iterdir()
        if f.is_file() and f.suffix.lower() in ALLOWED
    )


def main():
    args = [a for a in sys.argv[1:] if a not in ("--direct", "--structured")]
    if args:
        arg = Path(args[0])
        if arg.is_absolute():
            chat_path = arg
        elif (CHATS_FOLDER / arg.name).exists():
            chat_path = CHATS_FOLDER / arg.name
        else:
            chat_path = arg
    else:
        files = get_chat_files()
        if not files:
            print(f"No chat files in {CHATS_FOLDER}")
            print("Put your .txt files there and run again.")
            sys.exit(1)
        if len(files) == 1:
            chat_path = files[0]
            print(f"Using: {chat_path.name}")
        else:
            print("Files in chats/ folder:")
            for i, f in enumerate(files, 1):
                print(f"  {i}. {f.name}")
            choice = input("Enter number (or filename): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(files):
                chat_path = files[int(choice) - 1]
            else:
                chat_path = CHATS_FOLDER / choice
                if not chat_path.exists():
                    chat_path = Path(choice)

    if not chat_path.exists():
        print(f"Error: File not found: {chat_path}")
        sys.exit(1)

    suffix = chat_path.suffix.lower()
    if suffix not in ALLOWED:
        print(f"Error: Unsupported format. Allowed: {', '.join(ALLOWED)}")
        sys.exit(1)

    print(f"Analyzing: {chat_path}")
    print("...")

    use_direct = "--direct" in sys.argv
    use_structured = "--structured" in sys.argv

    if use_direct:
        # Analyze directly via Deepgram (no server needed)
        try:
            from app.services.transcription_service import analyze_text

            text = chat_path.read_text(encoding="utf-8")
            result = analyze_text(text)

            if use_structured:
                from app.services.structured_analysis import extract_structured_analysis
                structured = extract_structured_analysis(text, result.to_dict())
                print(json.dumps(structured, indent=2, ensure_ascii=True))
            else:
                print("\n--- Transcript (preview) ---")
                preview = result.transcript[:300] + "..." if len(result.transcript) > 300 else result.transcript
                print(preview if preview else "(empty)")

                if result.detected_language is not None:
                    name = result.detected_language_name or result.detected_language
                    print(f"\nDetected language: {name}")

                if getattr(result, "sentiment_average", None):
                    sa = result.sentiment_average
                    print(f"\nSentiment (avg): {sa.get('sentiment', '')} ({sa.get('sentiment_score', 0):.2f})")

                if getattr(result, "sentiment_segments", None) and result.sentiment_segments:
                    print("\nSentiment segments:")
                    for seg in result.sentiment_segments[:5]:
                        txt = seg.get("text", "")
                        txt_preview = txt[:60] + "..." if len(txt) > 60 else txt
                        print(f"  - {seg.get('sentiment', '')} ({seg.get('sentiment_score', 0):.2f}): \"{txt_preview}\"")

                if getattr(result, "intent_segments", None) and result.intent_segments:
                    print("\nIntents:")
                    for seg in result.intent_segments:
                        for i in seg.get("intents", []):
                            txt = seg.get("text", "")
                            txt_preview = txt[:60] + "..." if len(txt) > 60 else txt
                            print(f"  - {i.get('intent', '')} ({i.get('confidence_score', 0):.2f}): \"{txt_preview}\"")

                if getattr(result, "topic_segments", None) and result.topic_segments:
                    print("\nTopics:")
                    for seg in result.topic_segments:
                        for t in seg.get("topics", []):
                            txt = seg.get("text", "")
                            txt_preview = txt[:60] + "..." if len(txt) > 60 else txt
                            print(f"  - {t.get('topic', '')} ({t.get('confidence_score', 0):.2f}): \"{txt_preview}\"")

                if getattr(result, "summary", None) and result.summary.get("short"):
                    print(f"\nSummary: {result.summary.get('short', '')}")

                print("\n--- Full response ---")
                print(json.dumps(result.to_dict(), indent=2, ensure_ascii=True))
        except ValueError as e:
            print(f"Error: {e}")
            print("Set DEEPGRAM_API_KEY in .env")
            sys.exit(1)
    else:
        # Use API (server must be running)
        try:
            with open(chat_path, "rb") as f:
                response = requests.post(
                    API_URL,
                    files={"file": (chat_path.name, f, "text/plain")},
                )

            if response.status_code != 200:
                print(f"Error {response.status_code}: {response.text}")
                sys.exit(1)

            result = response.json()
            transcript = result.get("transcript", "")
            print("\n--- Transcript (preview) ---")
            preview = transcript[:300] + "..." if len(transcript) > 300 else transcript
            print(preview if preview else "(empty)")
            print("\n--- Full response ---")
            print(result)
        except requests.exceptions.ConnectionError:
            print("Error: Cannot connect. Is the server running? (python run.py)")
            print("Or use --direct to analyze without the server.")
            sys.exit(1)


if __name__ == "__main__":
    main()
