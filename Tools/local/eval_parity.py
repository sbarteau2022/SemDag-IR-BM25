"""`swegemma eval` with the scorer's context management switched on.

The scoring notebook (`scripts/inference.py`, HARNESS_README §7.2) builds the ADK App with
events compaction and context caching. The `swegemma eval` CLI has no flag for either, and
`EvalConfig` defaults both to None, so plain local runs never compact (docs/SCORER_PARITY.md,
GAP 1). This wrapper sets the documented values on every EvalConfig, then runs the
unmodified CLI with the same arguments.

    eval_parity.py eval --tasks ... (same arguments as `swegemma eval`)

SWEGEMMA_PARITY=0 turns the injection off (plain CLI behaviour) for A/B checks.
SWEGEMMA_COMPACTION_THRESHOLD=<tokens> overrides token_threshold. Use it only for the gate
that proves compaction fires locally; scored-parity runs keep the scorer's 14,336.
The summarizer is left as None: ADK then builds LlmEventSummarizer from the root agent's
own model (google/adk/apps/compaction.py), i.e. the same E4B.
"""
from __future__ import annotations

import os
import sys

# Scorer values, HARNESS_README.md §7.2 (scripts/inference.py).
COMPACTION = {"compaction_interval": 15, "overlap_size": 2, "token_threshold": 14336,
              "event_retention_size": 5}
CONTEXT_CACHE = {"min_tokens": 2048, "ttl_seconds": 1800, "cache_intervals": 10}


def install() -> None:
    """Patch EvalConfig so every instance carries the scorer's compaction and cache configs."""
    from google.adk.agents.context_cache_config import ContextCacheConfig
    from google.adk.apps._configs import EventsCompactionConfig

    from swegemma import config as swe_config

    cls = swe_config.EvalConfig
    if getattr(cls, "_parity_installed", False):
        return
    original = cls.__post_init__

    def __post_init__(self) -> None:
        if self.events_compaction_config is None:
            self.events_compaction_config = EventsCompactionConfig(**COMPACTION)
        if self.context_cache_config is None:
            self.context_cache_config = ContextCacheConfig(**CONTEXT_CACHE)
        original(self)

    cls.__post_init__ = __post_init__
    cls._parity_installed = True


def main(argv: list[str] | None = None) -> int:
    if os.environ.get("SWEGEMMA_PARITY", "1") != "0":
        if os.environ.get("SWEGEMMA_COMPACTION_THRESHOLD"):
            COMPACTION["token_threshold"] = int(os.environ["SWEGEMMA_COMPACTION_THRESHOLD"])
        install()
        print("eval_parity: events compaction "
              + ", ".join(f"{k}={v}" for k, v in COMPACTION.items())
              + "; context cache " + ", ".join(f"{k}={v}" for k, v in CONTEXT_CACHE.items()),
              file=sys.stderr, flush=True)
    from swegemma import cli
    return cli.main(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
