"""Policy RAG: embed policy text, store locally, retrieve and check violations."""
import json
import logging
from pathlib import Path
from typing import List, Optional

import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)

EMBED_MODEL = "models/gemini-embedding-001"
LLM_MODEL = "gemini-1.5-flash"
CHUNK_SIZE = 300
TOP_K = 5


def _get_genai_client():
    """Get Google GenAI client."""
    from google import genai
    settings = get_settings()
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY required for policy RAG")
    return genai.Client(api_key=settings.google_api_key)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    """Split text into chunks by sentences."""
    sentences = text.replace("\n", " ").split(".")
    chunks = []
    current = ""

    for sentence in sentences:
        s = sentence.strip()
        if not s:
            continue
        if len(current) + len(s) + 1 < chunk_size:
            current += s + ". "
        else:
            if current.strip():
                chunks.append(current.strip())
            current = s + ". "

    if current.strip():
        chunks.append(current.strip())
    return chunks


def embed_text(text_list: List[str]) -> np.ndarray:
    """Generate embeddings via Gemini."""
    if not text_list:
        return np.array([]).astype("float32")

    client = _get_genai_client()
    response = client.models.embed_content(
        model=EMBED_MODEL,
        contents=text_list,
    )

    embeddings = []
    for emb in response.embeddings:
        if hasattr(emb, "values"):
            embeddings.append(emb.values)
        elif isinstance(emb, dict) and "values" in emb:
            embeddings.append(emb["values"])
        else:
            embeddings.append(list(emb))

    return np.array(embeddings).astype("float32")


def _get_policy_path() -> Path:
    """Get absolute path for policy embeddings file."""
    settings = get_settings()
    path = Path(settings.policy_storage_path)
    if not path.is_absolute():
        from app.config import PROJECT_ROOT
        path = PROJECT_ROOT / path
    return path


def store_policy_in_supabase(policy_text: str) -> dict:
    """
    Chunk policy, generate embeddings, store locally.
    Returns {chunks_count, stored, storage, file_path}.
    """
    chunks = chunk_text(policy_text)
    if not chunks:
        return {"chunks_count": 0, "stored": True, "storage": "local", "file_path": None}

    embeddings = embed_text(chunks)

    payload = {
        "chunks": chunks,
        "embeddings": [emb.tolist() for emb in embeddings],
    }

    path = _get_policy_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    logger.info(
        "Policy embeddings created: %d chunks, %d dimensions (storage: local '%s')",
        len(chunks),
        embeddings.shape[1],
        str(path),
    )

    return {
        "chunks_count": len(chunks),
        "stored": True,
        "storage": "local",
        "file_path": str(path),
    }


def _load_policy_from_supabase() -> tuple[List[str], np.ndarray]:
    """Load policy chunks and embeddings from local file."""
    path = _get_policy_path()
    if not path.exists():
        raise ValueError("No policy loaded. POST /policy first with policy text.")

    payload = json.loads(path.read_text(encoding="utf-8"))
    chunks = payload.get("chunks", [])
    embeddings = np.array(payload.get("embeddings", [])).astype("float32")

    if not chunks or len(embeddings) == 0:
        raise ValueError("No policy loaded. POST /policy first with policy text.")

    return chunks, embeddings


def _build_faiss_index(embeddings: np.ndarray):
    """Build FAISS index for similarity search."""
    import faiss
    faiss.normalize_L2(embeddings)
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)
    return index


def retrieve_relevant_policy(
    index, policy_chunks: List[str], embeddings: np.ndarray,
    transcript_chunk: str, top_k: int = TOP_K,
) -> List[str]:
    """Retrieve top-k relevant policy chunks for transcript chunk."""
    import faiss
    query_vec = embed_text([transcript_chunk])
    faiss.normalize_L2(query_vec)
    scores, indices = index.search(query_vec, min(top_k, len(policy_chunks)))
    return [policy_chunks[i] for i in indices[0] if i < len(policy_chunks)]


def _normalize_violation(val) -> bool:
    """Normalize violation field from LLM (may be bool or string)."""
    if val is True:
        return True
    if isinstance(val, str) and val.lower() in ("true", "yes", "1"):
        return True
    return False


def check_violation(transcript_chunk: str, relevant_policy_chunks: List[str]) -> dict:
    """Use LLM to check if transcript chunk violates policy."""
    if not relevant_policy_chunks:
        return {"violation": False, "reason": "No policy context retrieved", "violated_policy_excerpt": ""}

    client = _get_genai_client()
    policy_context = "\n\n".join(relevant_policy_chunks)

    prompt = f"""You are a strict compliance auditor. Be conservative: when in doubt, flag as violation.

Company Policy:
{policy_context}

Transcript Segment:
{transcript_chunk}

Does this segment violate ANY part of the policy above? Consider: PII disclosure, fraud, unauthorized sharing, rule breaches.

Return ONLY valid JSON (no markdown):
{{
  "violation": true or false,
  "reason": "brief explanation",
  "violated_policy_excerpt": "exact policy text that was violated, or empty string if none"
}}
"""

    try:
        response = client.models.generate_content(
            model=LLM_MODEL,
            contents=prompt,
            config={"temperature": 0, "response_mime_type": "application/json"},
        )
        text = (response.text or "").strip()
        # Strip markdown code blocks if present
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        data = json.loads(text)
        # Normalize violation to bool
        data["violation"] = _normalize_violation(data.get("violation", False))
        return data
    except Exception as e:
        logger.warning("check_violation failed: %s", e)
        return {"violation": False, "reason": str(e), "violated_policy_excerpt": ""}


def run_policy_rag(transcript_text: str) -> List[dict]:
    """
    Run RAG pipeline: load policy, chunk transcript, retrieve relevant policy,
    check violations per chunk. Returns list of {transcript_chunk, analysis}.
    """
    policy_chunks, embeddings = _load_policy_from_supabase()
    index = _build_faiss_index(embeddings)

    transcript_chunks = chunk_text(transcript_text)
    results = []

    for chunk in transcript_chunks:
        if not chunk.strip():
            continue
        relevant_policy = retrieve_relevant_policy(
            index, policy_chunks, embeddings, chunk
        )
        analysis = check_violation(chunk, relevant_policy)
        results.append({"transcript_chunk": chunk, "analysis": analysis})

    return results


def run_policy_rag_safe(transcript_text: str) -> Optional[List[dict]]:
    """Run RAG if policy is loaded; return None otherwise."""
    try:
        return run_policy_rag(transcript_text)
    except ValueError:
        return None
    except Exception:
        return None
