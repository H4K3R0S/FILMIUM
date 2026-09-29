from __future__ import annotations


def bucket_for(token_estimate: int, buckets: tuple[int, ...]) -> int:
    """Najmanji baket koji pokriva estimate; ako nijedan, najveci."""
    for b in sorted(buckets):
        if token_estimate <= b:
            return b
    return max(buckets)


def plan_context(t_prompt: int, t_rag: int, *, t_buffer: int = 800,
                 buckets: tuple[int, ...]) -> int:
    """JIT proracun num_ctx zaokruzen na baket (izbegava Ollama reload thrash)."""
    return bucket_for(t_prompt + t_rag + t_buffer, buckets)
