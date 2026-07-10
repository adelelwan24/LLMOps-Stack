#!/usr/bin/env bash
# Verify LLMOps stack health and Prometheus → vLLM metrics connectivity.
set -euo pipefail

COMPOSE_FILES=(-f docker-compose.yml)
RUNTIME="${VLLM_RUNTIME:-cpu}"

case "$RUNTIME" in
  gpu)  COMPOSE_FILES+=(-f docker-compose.gpu.yml) ;;
  cpu)  COMPOSE_FILES+=(-f docker-compose.cpu.yml) ;;
  rocm) COMPOSE_FILES+=(-f docker-compose.rocm.yml) ;;
  *)
    echo "Unknown VLLM_RUNTIME=$RUNTIME (expected gpu, cpu, or rocm)"
    exit 1
    ;;
esac

COMPOSE=(docker compose "${COMPOSE_FILES[@]}")

echo "==> Service status (runtime: $RUNTIME)"
"${COMPOSE[@]}" ps

echo ""
echo "==> vLLM health"
VLLM_STATUS=$("${COMPOSE[@]}" ps vllm --format '{{.Health}}' 2>/dev/null || true)
if [ "$VLLM_STATUS" != "healthy" ]; then
  echo "WARN: vLLM is not healthy (status: ${VLLM_STATUS:-unknown})"
  echo "      Wait for model load: ${COMPOSE[*]} logs -f vllm"
else
  echo "OK: vLLM is healthy"
fi

echo ""
echo "==> Prometheus → vLLM /metrics (in-network scrape path)"
if docker exec prometheus wget -qO- http://vllm:8000/metrics 2>/dev/null | head -5; then
  echo "OK: Prometheus container can reach vllm:8000/metrics"
else
  echo "FAIL: Could not fetch metrics from inside prometheus container"
  echo "      Check: ${COMPOSE[*]} logs vllm prometheus"
  exit 1
fi

echo ""
echo "==> Next steps"
echo "  Prometheus targets: http://localhost:9090/targets  (vllm job should be UP)"
echo "  Grafana dashboard:  http://localhost:3000          (admin / admin)"
echo "  Inference API:      http://localhost:8000/v1       (Bearer token required)"
echo ""
echo "Note: Grafana panels stay empty until you send inference requests."
