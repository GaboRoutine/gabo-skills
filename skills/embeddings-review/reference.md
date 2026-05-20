# Embedding correctness traps

Reference for the `embeddings-review` skill. These are the failure modes that pass
type checks and run cleanly while producing wrong vectors.

## Mean pooling

The `HFPoolingEmbedder` averages token embeddings into one vector per text. Padding
tokens must be excluded:

```python
# correct — masked mean
mask = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
summed = (token_embeddings * mask).sum(dim=1)
counts = mask.sum(dim=1).clamp(min=1e-9)   # avoid divide-by-zero
pooled = summed / counts

# WRONG — averages pad tokens, corrupts padded batches
pooled = token_embeddings.mean(dim=1)
```

Symptom: single-text encoding looks fine, batches give slightly-off vectors that
degrade clustering quality. Easy to miss without a shape-level trace.

## Device selection

- Order: `cuda` → `mps` (Apple) → `cpu`, decided once at `__init__`.
- Move **both** model and inputs: `self.model.to(self.device)` and
  `{k: v.to(self.device) for k, v in inputs.items()}`. A model on MPS with inputs on
  CPU raises at runtime — but only on that hardware, so it slips through CI on CPU.

## Inference hygiene

- Wrap forward passes in `torch.no_grad()`. Without it, autograd retains the graph:
  memory climbs with batch count and throughput drops.
- Call `self.model.eval()` after loading — dropout/batchnorm differ in train mode.

## Batching

- Batch size is a memory/throughput knob, not a correctness one — *unless* batches
  are concatenated wrong. `np.concatenate(batches, axis=0)` must give
  `(len(texts), dim)`. An `axis=1` typo silently produces the wrong shape.
- `truncation=True, max_length=512` — long articles are truncated; that's expected,
  but note it if descriptions are getting cut.

## Caching (`--cache`)

- File name encodes the model: `embeddings_<model>.npy`. The cache key **must**
  include the model name, or switching `--model` returns stale vectors.
- The cache is invalid if the input article set changes. Keying only on the model
  name means adding articles silently reuses an undersized array — guard on length
  at minimum, ideally a content hash.
- Cache files are gitignored (`embeddings/embeddings_*.npy`) — never commit them.

## Backend contract

`EmbeddingModel.encode(texts: list[str]) -> np.ndarray`, shape `(len(texts), dim)`.
Add backends by subclassing and registering in `load_embedder`; never branch on
backend type inside calling code.
