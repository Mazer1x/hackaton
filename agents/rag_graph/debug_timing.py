"""
Замер времени: вызов RAG через HTTP (RAG_SERVICE_URL) и опционально полный граф (search + select_best).

Запуск из корня проекта:
  python -m agents.rag_graph.debug_timing
  python -m agents.rag_graph.debug_timing --full   # с нодой select_best (LLM)

Требуется RAG_SERVICE_URL в .env.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _elapsed(start: float) -> float:
    return time.perf_counter() - start


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--full", action="store_true", help="Run full graph (search + select_best)")
    p.add_argument("--query", default="Where is the Telegram link?", help="Query for RAG")
    args = p.parse_args()

    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")

    url = os.environ.get("RAG_SERVICE_URL", "").strip()
    if not url:
        print("RAG_SERVICE_URL not set. Set it in .env to the RAG HTTP service URL.")
        return

    timings: list[tuple[str, float]] = []

    # --- HTTP request to RAG service
    t0 = time.perf_counter()
    import requests
    r = requests.post(
        f"{url.rstrip('/')}/search",
        json={"query": args.query, "top_k": 5},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    timings.append(("RAG service HTTP /search", _elapsed(t0)))

    # --- Full graph (search + select_best)
    if args.full:
        from agents.rag_graph.main import graph
        t0 = time.perf_counter()
        result = graph.invoke({"query": args.query, "top_k": 5})
        timings.append(("graph.invoke() search + select_best", _elapsed(t0)))

    print("Timings (seconds):")
    print("-" * 60)
    for name, sec in timings:
        print(f"  {sec:8.3f}s  {name}")
    print("-" * 60)


if __name__ == "__main__":
    main()
