#!/usr/bin/env python3
"""
End-to-end test client for the LLMOps stack.

Routes inference through the Nginx security proxy (Bearer token auth) and
logs every request/response pair to MLflow for quality tracking.
"""

import os
import time
from datetime import datetime, timezone

import mlflow
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

load_dotenv()

# Nginx proxy exposes vLLM on port 8000 with Bearer token auth
NGINX_BASE_URL = os.getenv("NGINX_BASE_URL", "http://localhost:8000/v1")
BEARER_TOKEN = os.getenv("BEARER_TOKEN", "ML expert rules")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
MODEL_NAME = os.getenv("MODEL_HF_NAME") or os.getenv("VLLM_MODEL_NAME", "qwen-4b-instruct")
EXPERIMENT_NAME = "llm-inference-quality"


def build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=MODEL_NAME,
        base_url=NGINX_BASE_URL,
        api_key=BEARER_TOKEN,
        temperature=0.7,
        max_tokens=512,
    )


def log_conversation(
    run_name: str,
    prompt: str,
    response: str,
    latency_s: float,
    metadata: dict | None = None,
) -> None:
    """Log a single inference turn to MLflow for quality tracking."""
    with mlflow.start_run(run_name=run_name):
        mlflow.set_tag("source", "langchain-client")
        mlflow.set_tag("model", MODEL_NAME)
        mlflow.log_param("prompt", prompt)
        mlflow.log_param("endpoint", NGINX_BASE_URL)
        mlflow.log_metric("latency_seconds", latency_s)
        mlflow.log_metric("prompt_length_chars", len(prompt))
        mlflow.log_metric("response_length_chars", len(response))

        if metadata:
            for key, value in metadata.items():
                mlflow.log_param(key, value)

        mlflow.log_text(
            f"=== PROMPT ===\n{prompt}\n\n=== RESPONSE ===\n{response}",
            artifact_file="conversation.txt",
        )


def run_inference(llm: ChatOpenAI, prompt: str) -> tuple[str, float]:
    messages = [
        SystemMessage(content="You are a helpful AI assistant. Be concise."),
        HumanMessage(content=prompt),
    ]
    start = time.perf_counter()
    result = llm.invoke(messages)
    latency = time.perf_counter() - start
    return result.content, latency


def main() -> None:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    llm = build_llm()

    test_prompts = [
        "What is LLMOps and why does it matter for production AI systems?",
        "Explain the difference between TTFT and end-to-end latency in LLM serving.",
        "Write a one-line Python function that checks if a string is a palindrome.",
    ]

    print(f"Tracking URI : {MLFLOW_TRACKING_URI}")
    print(f"Inference URL: {NGINX_BASE_URL}")
    print(f"Model        : {MODEL_NAME}")
    print("-" * 60)

    for i, prompt in enumerate(test_prompts, start=1):
        run_name = f"inference-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{i}"
        print(f"\n[{i}/{len(test_prompts)}] Prompt: {prompt[:80]}...")

        try:
            response, latency = run_inference(llm, prompt)
            print(f"Response ({latency:.2f}s): {response[:200]}...")

            log_conversation(
                run_name=run_name,
                prompt=prompt,
                response=response,
                latency_s=latency,
                metadata={"prompt_index": i},
            )
            print(f"Logged to MLflow run: {run_name}")
        except Exception as exc:
            print(f"ERROR: {exc}")
            with mlflow.start_run(run_name=f"{run_name}-error"):
                mlflow.set_tag("status", "failed")
                mlflow.log_param("prompt", prompt)
                mlflow.log_param("error", str(exc))

    print("\n" + "=" * 60)
    print("Done. View results:")
    print(f"  MLflow UI : {MLFLOW_TRACKING_URI}")
    print("  Grafana   : http://localhost:3000  (admin / admin)")
    print("  Prometheus: http://localhost:9090")


if __name__ == "__main__":
    main()
