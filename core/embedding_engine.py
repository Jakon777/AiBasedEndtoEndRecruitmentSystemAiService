import logging
import os
from pathlib import Path
import time
from typing import List, Optional, Tuple

from dotenv import load_dotenv
import numpy as np

# Load environment variables
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from core.logging_config import get_logger

logger = get_logger("ai_hr.core.EmbeddingEngine")


# Lazy-loaded client singleton
_client = None

# Model candidates to try for embedding generation
_DEFAULT_EMBEDDING_MODELS: Tuple[str, ...] = (
    "gemini-embedding-001",
    "gemini-embedding-2",
    "gemini-embedding-2-preview",
)

_last_ok_model: Optional[str] = None
_last_dim: int = 3072


def _get_api_key() -> Optional[str]:
    """Retrieve embedding or Gemini API key from environment, stripping whitespace/quotes."""
    key = os.getenv("EMBEDDING_API_KEY") or os.getenv("GEMINI_API_KEY")
    if key:
        return key.strip().strip('"').strip("'")
    return None


def _get_client():
    """Lazily initialize Google GenAI client to avoid crash on import if key is missing."""
    global _client
    if _client is not None:
        return _client

    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError(
            "Neither EMBEDDING_API_KEY nor GEMINI_API_KEY is set. "
            "Please configure it in your Render environment variables or .env file."
        )

    from google import genai
    _client = genai.Client(api_key=api_key)
    return _client


def _model_candidates() -> List[str]:
    """Get prioritized list of embedding model names."""
    seen = set()
    models: List[str] = []

    def add(m: Optional[str]):
        if m and m not in seen:
            seen.add(m)
            models.append(m)

    global _last_ok_model
    add(_last_ok_model)
    env_model = os.getenv("EMBEDDING_MODEL", "").strip()
    add(env_model or None)
    for m in _DEFAULT_EMBEDDING_MODELS:
        add(m)

    return models


def generate_embedding(text: str) -> np.ndarray:
    """
    Generate an embedding vector for given text using external Google GenAI API.
    Returns 1D numpy array of float32.
    """
    global _last_dim, _last_ok_model

    if not text or not text.strip():
        logger.warning("Empty text passed to generate_embedding; returning zero vector.")
        return np.zeros(_last_dim, dtype=np.float32)

    client = _get_client()
    candidates = _model_candidates()
    last_error: Optional[Exception] = None

    # Limit text length to avoid token limits / memory overhead
    truncated_text = text[:8000]

    for model_id in candidates:
        for attempt in range(2):
            try:
                response = client.models.embed_content(
                    model=model_id,
                    contents=truncated_text,
                )
                if response.embeddings and len(response.embeddings) > 0:
                    values = response.embeddings[0].values
                    vec = np.array(values, dtype=np.float32)
                    _last_ok_model = model_id
                    _last_dim = len(vec)
                    return vec
            except Exception as e:
                err_msg = str(e)
                logger.warning(
                    "Embedding attempt %d failed with model '%s': %s",
                    attempt + 1,
                    model_id,
                    err_msg,
                )
                last_error = e
                # Brief backoff if rate limited before retrying or switching models
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    time.sleep(1.0)
                else:
                    break  # Non-transient error, try next candidate model

    raise RuntimeError(
        f"Embedding API failed for all models: {candidates}. Last error: {last_error}"
    )


def compute_similarity(text1: str, text2: str) -> float:
    """
    Compute cosine similarity between two texts using external embeddings.
    Returns a float in [0.0, 1.0]. Never crashes callers on API failures.
    """
    global _last_dim, _last_ok_model

    t1 = (text1 or "").strip()
    t2 = (text2 or "").strip()

    if not t1 or not t2:
        return 0.0

    try:
        client = _get_client()
    except Exception as e:
        logger.error("Cannot initialize embedding client: %s. Returning 0.0 similarity.", e)
        return 0.0

    candidates = _model_candidates()
    last_error: Optional[Exception] = None

    t1_trunc = t1[:8000]
    t2_trunc = t2[:8000]

    # Try batch embedding both texts in a single API call for lower latency and quota efficiency
    for model_id in candidates:
        for attempt in range(2):
            try:
                response = client.models.embed_content(
                    model=model_id,
                    contents=[t1_trunc, t2_trunc],
                )
                if response.embeddings and len(response.embeddings) >= 2:
                    v1 = np.array(response.embeddings[0].values, dtype=np.float32)
                    v2 = np.array(response.embeddings[1].values, dtype=np.float32)

                    _last_ok_model = model_id
                    _last_dim = len(v1)

                    if v1.shape != v2.shape:
                        logger.warning("Embedding shapes mismatch (%s vs %s); returning 0.0", v1.shape, v2.shape)
                        return 0.0

                    norm1 = float(np.linalg.norm(v1))
                    norm2 = float(np.linalg.norm(v2))
                    if norm1 == 0.0 or norm2 == 0.0:
                        return 0.0

                    cos_sim = float(np.dot(v1, v2) / (norm1 * norm2))
                    return max(0.0, min(1.0, cos_sim))
            except Exception as e:
                err_msg = str(e)
                logger.warning(
                    "Batch embedding attempt %d failed with model '%s': %s",
                    attempt + 1,
                    model_id,
                    err_msg,
                )
                last_error = e
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    time.sleep(1.0)
                else:
                    break

    # Fallback to separate generate_embedding calls if batching was unsupported
    try:
        emb1 = generate_embedding(t1_trunc)
        emb2 = generate_embedding(t2_trunc)

        if emb1.shape != emb2.shape:
            logger.warning("Embedding shapes mismatch (%s vs %s); returning 0.0", emb1.shape, emb2.shape)
            return 0.0

        norm1 = float(np.linalg.norm(emb1))
        norm2 = float(np.linalg.norm(emb2))
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0

        cos_sim = float(np.dot(emb1, emb2) / (norm1 * norm2))
        return max(0.0, min(1.0, cos_sim))
    except Exception as e:
        logger.error(
            "Failed to compute similarity (API or network issue): %s. Falling back to 0.0.",
            e,
        )
        return 0.0