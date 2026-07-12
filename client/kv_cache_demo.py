#!/usr/bin/env python3
"""
Demonstrate vLLM KV cache reuse via automatic prefix caching.

How it works
------------
vLLM stores attention KV tensors in a KV cache while generating tokens.
With --enable-prefix-caching, a shared prompt *prefix* (e.g. a long system
prompt or document) is hashed and reused across requests. The second request
skips recomputing those prompt tokens → lower time-to-first-token (TTFT).

You cannot "call" the KV cache from the client. You utilize it by:
  1. Enabling prefix caching on the server (compose includes --enable-prefix-caching)
  2. Sending requests that share a long identical prefix
  3. Observing faster TTFT and rising vllm:kv_cache_usage_perc in Grafana

Usage (stack must be running):
  cd client
  uv run python kv_cache_demo.py
"""

from __future__ import annotations

import os
import time
import urllib.request

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_URL = os.getenv("NGINX_BASE_URL", "http://localhost:8000/v1")
API_KEY = os.getenv("BEARER_TOKEN", "ML expert rules")
MODEL = os.getenv("VLLM_MODEL_NAME") or os.getenv("VLLM_SERVED_MODEL_NAME", "qwen-0.5b")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")

# Long shared prefix — keep this identical across requests so vLLM can reuse KV.
SHARED_CONTEXT = """
You are a technical assistant for LLMOps. Use only the knowledge below.

=== DOCUMENT (shared prefix for KV cache reuse) ===
LLMOps covers packaging, serving, monitoring, and iterating on LLM systems.
vLLM is a high-throughput inference engine with PagedAttention for efficient
GPU/CPU memory use. The KV cache stores key/value attention tensors for tokens
already processed so decoding does not recompute them. Automatic prefix caching
reuses KV blocks when a new request shares a token prefix with a previous one.
Prometheus scrapes /metrics; Grafana visualizes TTFT, latency, and kv_cache_usage.
Nginx authenticates public API traffic; internal scrapes and healthchecks bypass it.
""" * 3  # repeat to make the prefix long enough to matter


def kv_cache_usage() -> float | None:
    """Read current KV cache utilization from Prometheus (0.0–1.0)."""
    query = "vllm:kv_cache_usage_perc"
    url = f"{PROMETHEUS_URL}/api/v1/query?query={query}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = resp.read().decode()
        # Minimal parse without extra deps: look for "value":[ts,"x.xx"]
        marker = '"value":['
        i = data.find(marker)
        if i < 0:
            return None
        rest = data[i + len(marker) :]
        # value is [timestamp, "number"]
        quote = rest.find('"')
        if quote < 0:
            return None
        end = rest.find('"', quote + 1)
        return float(rest[quote + 1 : end])
    except Exception:
        return None


def chat_ttft(client: OpenAI, user_message: str) -> tuple[str, float, float]:
    """
    Stream one completion; return (text, ttft_s, total_s).

    TTFT ≈ time until the first streamed token — the metric prefix caching improves.
    """
    messages = [
        {"role": "system", "content": SHARED_CONTEXT.strip()},
        {"role": "user", "content": user_message},
    ]

    t0 = time.perf_counter()
    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=64,
        temperature=0.0,
        stream=True,
    )

    ttft: float | None = None
    chunks: list[str] = []
    for event in stream:
        delta = event.choices[0].delta.content or ""
        if delta and ttft is None:
            ttft = time.perf_counter() - t0
        chunks.append(delta)

    total = time.perf_counter() - t0
    return "".join(chunks), (ttft if ttft is not None else total), total


def main() -> None:
    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

    questions = [
        "In one sentence, what is the KV cache?",
        "In one sentence, why does prefix caching help TTFT?",
        "In one sentence, what scrapes vLLM metrics?",
    ]

    print(f"Endpoint : {BASE_URL}")
    print(f"Model    : {MODEL}")
    print(f"Prefix   : ~{len(SHARED_CONTEXT.split())} words (identical on every request)")
    print("-" * 64)

    before = kv_cache_usage()
    if before is not None:
        print(f"KV cache usage before: {before:.1%}")

    results: list[tuple[str, float, float]] = []
    for i, q in enumerate(questions, start=1):
        text, ttft, total = chat_ttft(client, q)
        results.append((q, ttft, total))
        print(f"\n[{i}] {q}")
        print(f"    TTFT={ttft:.3f}s  total={total:.3f}s")
        print(f"    {text.strip()[:160]}")

    after = kv_cache_usage()
    if after is not None:
        print(f"\nKV cache usage after:  {after:.1%}")

    if len(results) >= 2:
        first_ttft = results[0][1]
        later = [r[1] for r in results[1:]]
        avg_later = sum(later) / len(later)
        print("-" * 64)
        print(f"First request TTFT : {first_ttft:.3f}s  (prefix computed + cached)")
        print(f"Later avg TTFT     : {avg_later:.3f}s  (shared prefix reused from KV cache)")
        if avg_later < first_ttft:
            print(f"Speedup            : {first_ttft / avg_later:.2f}x on TTFT (prefix hit)")
        else:
            print(
                "Note: later TTFT was not faster. Check that vLLM was started with "
                "--enable-prefix-caching and that the system prompt is identical."
            )

    print("\nGrafana panel 'KV Cache Usage' should rise while requests run.")
    print("  http://localhost:3000")


if __name__ == "__main__":
    main()
