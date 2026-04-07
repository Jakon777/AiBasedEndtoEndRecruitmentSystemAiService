# from sentence_transformers import SentenceTransformer
# from sklearn.metrics.pairwise import cosine_similarity
#  # TODO: use GPU for faster computation
# _model: SentenceTransformer | None = None


# def _get_model() -> SentenceTransformer:
#     global _model
#     if _model is None:
#         # Force CPU to keep memory predictable on small hosts.
#         _model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
#         # SentenceTransformer defaults are typically fine, but capping helps
#         # keep tokenization / attention work bounded.
#         if hasattr(_model, "max_seq_length") and _model.max_seq_length:
#             _model.max_seq_length = min(int(_model.max_seq_length), 256)
#     return _model


# def generate_embedding(text: str):
#     """
#     Generate embedding vector for a given text.
#     """
#     # Use a small batch size + no progress bar to reduce per-request RAM.
#     return _get_model().encode(
#         text,
#         batch_size=1,
#         show_progress_bar=False,
#         convert_to_numpy=True,
#         normalize_embeddings=False,
#     )


# def compute_similarity(text1: str, text2: str):
#     """
#     Compute cosine similarity between two texts.
#     """
#     emb1 = generate_embedding(text1)
#     emb2 = generate_embedding(text2)

#     score = cosine_similarity([emb1], [emb2])[0][0]

#     return float(score)  


# from sentence_transformers import SentenceTransformer
# from sklearn.metrics.pairwise import cosine_similarity

# model = None

# def get_model():
#     global model
#     if model is None:
#         # ✅ Force CPU (important for Render free tier)
#         model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

#         # ✅ Reduce memory usage
#         if hasattr(model, "max_seq_length") and model.max_seq_length:
#             model.max_seq_length = min(int(model.max_seq_length), 256)

#     return model


# def generate_embedding(text: str):
#     """
#     Generate embedding vector for a given text.
#     """
#     model = get_model()

#     return model.encode(
#         text,
#         batch_size=1,
#         show_progress_bar=False,
#         convert_to_numpy=True,
#         normalize_embeddings=False,
#     )


# def compute_similarity(text1: str, text2: str):
#     """
#     Compute cosine similarity between two texts.
#     """
#     emb1 = generate_embedding(text1)
#     emb2 = generate_embedding(text2)

#     score = cosine_similarity([emb1], [emb2])[0][0]

#     return float(score)





from sentence_transformers import SentenceTransformer, util

# ✅ Global model (loaded once)
model = None


def get_model():
    global model

    if model is None:
        print("🚀 Loading SentenceTransformer model (only once)...")

        # ✅ Force CPU (Render free tier safe)
        model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

        # ✅ Reduce memory usage
        if hasattr(model, "max_seq_length") and model.max_seq_length:
            model.max_seq_length = min(int(model.max_seq_length), 256)

    return model


def compute_similarity(text1: str, text2: str) -> float:
    """
    🚀 FAST similarity computation
    - Single encode call
    - Uses torch-based cosine similarity (faster than sklearn)
    """

    try:
        if not text1 or not text2:
            return 0.0

        model = get_model()

        # ✅ Encode both texts in ONE call (faster)
        embeddings = model.encode(
            [text1, text2],
            batch_size=2,
            show_progress_bar=False,
            convert_to_tensor=True,   # ✅ IMPORTANT (faster)
            normalize_embeddings=True # ✅ improves cosine quality
        )

        # ✅ Fast cosine similarity
        score = util.cos_sim(embeddings[0], embeddings[1]).item()

        return float(score)

    except Exception as e:
        print("❌ Similarity error:", str(e))
        return 0.0