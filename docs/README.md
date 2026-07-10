# LLMOps Stack Documentation

Guides for each service in the unified inference and monitoring stack.

## Architecture

```mermaid
flowchart LR
    Client["Client / LangChain"] -->|Bearer auth :8000| Nginx
    Nginx --> vLLM["vLLM :8000 internal"]
    Prometheus["Prometheus :9090"] -->|/metrics no auth| vLLM
    Grafana["Grafana :3000"] --> Prometheus
    Client -->|experiments| MLflow["MLflow :5000"]
    vLLM --> HFCache[(huggingface_cache volume)]
```

## Quick start

| Runtime | Command |
|---------|---------|
| CPU | `docker compose -f docker-compose.yml -f docker-compose.cpu.yml up -d` |
| NVIDIA GPU | `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d` |
| AMD ROCm | `docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d` |

Copy `.env.example` to `.env` before starting. Default model: **Qwen/Qwen2.5-0.5B** (cached in `huggingface_cache`).

## Service guides

| Service | Doc | Host port | Role |
|---------|-----|-----------|------|
| Nginx | [nginx.md](nginx.md) | 8000 | Authenticated API gateway |
| Prometheus | [prometheus.md](prometheus.md) | 9090 | Metrics collection |
| Grafana | [grafana.md](grafana.md) | 3000 | Dashboards |
| Deployment | [deployment.md](deployment.md) | — | CPU / GPU / ROCm setup |

## Other services

- **vLLM** — OpenAI-compatible inference engine (internal only, not published to host)
- **MLflow** — Experiment tracking at http://localhost:5000

## Verification

```bash
VLLM_RUNTIME=cpu ./scripts/verify-stack.sh
```

## Further reading

- Root [README.md](../README.md) — quick start and troubleshooting
- [vLLM metrics](https://docs.vllm.ai/en/latest/usage/metrics/) — upstream metric reference
