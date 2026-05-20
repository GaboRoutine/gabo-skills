---
name: embeddings-review
description: Review changes to gabo's embeddings module (embedder.py, the EmbeddingModel backends, the encode/cache path) for correctness traps specific to transformer embeddings — device selection, mean pooling, batching, cache keying. Use when editing anything under embeddings/, adding an embedding backend, or asked to "review the embedder", "check the pooling", "is this embedding code right".
allowed-tools: Read, Grep, Glob
globs:
  - "embeddings/**"
  - "gabo/embeddings/**"
---

# Embeddings review

The embedder is the one place in gabo where a change can be silently *wrong* — it
runs, produces an array of the right shape, and the vectors are subtly garbage.
Tests rarely catch this. Review against the traps in `reference.md` (in this skill
directory); the high-frequency ones:

1. **Mean pooling must mask padding.** Pooling over `last_hidden_state` without
   multiplying by `attention_mask` averages in pad tokens and corrupts every vector
   in a padded batch. Confirm the mask is expanded, applied, and the denominator is
   `clamp(min=1e-9)` — never a bare `.mean(dim=1)`.
2. **Device selection order is CUDA → MPS → CPU**, chosen at init, and inputs must be
   moved to the same device as the model (`{k: v.to(self.device) ...}`).
3. **`torch.no_grad()` around inference** — otherwise memory grows and it's slower.
4. **Cache key must include the model name.** `--cache` writes `embeddings_<model>.npy`;
   a key that ignores the model returns one model's vectors for another. Also invalidate
   when the input set changes, not just the model.
5. **New backend = new `EmbeddingModel` subclass**, not a branch inside a caller. The
   only contract is `encode(texts: list[str]) -> np.ndarray` of shape
   `(len(texts), dim)`. Register it in `load_embedder`'s dispatch.

## How to review

- Read the changed file(s) and locate the pooling, device, and cache logic.
- Walk each trap in `reference.md` against the diff. For pooling, trace the tensor
  shapes by hand — this is where bugs hide.
- Report findings as `[blocking] / [non-blocking] / [nit]` with the file:line and the
  concrete fix. A wrong pooling or cache key is always `[blocking]`.
