"""
Smoke / пример клиента LangGraph Platform API (langgraph dev / облако).

1) Поднять API (из корня репозитория, UTF-8 в консоли Windows при желании):
   $env:PYTHONUTF8=1; py -m langgraph_cli dev --no-browser
   (если Scripts в PATH: langgraph dev)
   По умолчанию: http://127.0.0.1:2024

2) В другом терминале:
   py scripts/langgraph_sdk_smoke.py --list
   py scripts/langgraph_sdk_smoke.py --run rag_graph --input "{\"query\":\"hello\",\"top_k\":1}"

Нужны зависимости: py -m pip install -e ".[langgraph-api]"
Переменная LANGGRAPH_API_URL переопределяет базовый URL.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx


def _default_base_url() -> str:
    return os.environ.get("LANGGRAPH_API_URL", "http://127.0.0.1:2024").rstrip("/")


async def cmd_list() -> int:
    from langgraph_sdk import get_client

    client = get_client(url=_default_base_url())
    try:
        assistants = await client.assistants.search(limit=100)
    except httpx.ConnectError as e:
        print(
            f"Cannot connect to {_default_base_url()}: {e}\n"
            "Start the API: $env:PYTHONUTF8=1; py -m langgraph_cli dev --no-browser",
            file=sys.stderr,
        )
        return 1
    if not assistants:
        print("No assistants (graphs) returned. Is the server running?")
        return 1
    for a in assistants:
        aid = a.get("assistant_id") or a.get("id")
        name = a.get("name", "")
        gid = a.get("graph_id") or (a.get("metadata") or {}).get("graph_id", "")
        print(f"{aid}\tgraph_id={gid}\tname={name}")
    return 0


async def cmd_run(graph_id: str, input_payload: dict, stream: bool) -> int:
    from langgraph_sdk import get_client

    client = get_client(url=_default_base_url())
    found = await client.assistants.search(graph_id=graph_id, limit=5)
    agent = found[0] if found else None
    if not agent:
        print(f"Assistant for graph_id={graph_id!r} not found. Use --list.", file=sys.stderr)
        return 1

    assistant_id = agent.get("assistant_id") or agent.get("id")
    thread = await client.threads.create()

    try:
        if stream:
            async for chunk in client.runs.stream(
                thread["thread_id"],
                assistant_id,
                input=input_payload,
            ):
                print(chunk)
        else:
            result = await client.runs.wait(
                thread["thread_id"],
                assistant_id,
                input=input_payload,
            )
            print(json.dumps(result, indent=2, default=str))
    except httpx.ConnectError as e:
        print(
            f"Cannot connect to {_default_base_url()}: {e}",
            file=sys.stderr,
        )
        return 1

    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="LangGraph SDK smoke client")
    p.add_argument(
        "--list",
        action="store_true",
        help="List assistants (one per graph from langgraph.json)",
    )
    p.add_argument(
        "--run",
        metavar="GRAPH_ID",
        help="Run graph by id (key from langgraph.json), e.g. rag_graph",
    )
    p.add_argument(
        "--input",
        default="{}",
        help='JSON object as input state, default "{}"',
    )
    p.add_argument(
        "--input-file",
        metavar="PATH",
        help="Read input JSON from file (handy on Windows shells)",
    )
    p.add_argument(
        "--stream",
        action="store_true",
        help="Stream run events instead of wait()",
    )
    args = p.parse_args()

    raw_input = args.input
    if args.input_file:
        raw_input = Path(args.input_file).read_text(encoding="utf-8")
    try:
        payload = json.loads(raw_input)
    except json.JSONDecodeError as e:
        print(f"Invalid input JSON: {e}", file=sys.stderr)
        raise SystemExit(2) from e

    if args.list:
        code = asyncio.run(cmd_list())
        raise SystemExit(code)

    if args.run:
        code = asyncio.run(cmd_run(args.run, payload, args.stream))
        raise SystemExit(code)

    p.print_help()
    raise SystemExit(0)


if __name__ == "__main__":
    main()
