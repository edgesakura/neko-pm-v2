#!/bin/bash
# deploy-all.sh - SRE Agent フルデプロイスクリプト
#
# 実行手順:
#   1. ECR ログイン
#   2. Docker build × 3 (orchestrator, diagnostic, knowledge)
#   3. ECR push
#   4. CDK deploy
#   5. Gateway setup + target registration
#   6. Knowledge seed
#
# 使用例:
#   ./scripts/deploy-all.sh
#   ENVIRONMENT=production ./scripts/deploy-all.sh
#   AWS_REGION=us-west-2 ./scripts/deploy-all.sh

set -euo pipefail

REGION="${AWS_REGION:-us-west-2}"
ENVIRONMENT="${ENVIRONMENT:-development}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_BASE="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

AGENTS=("orchestrator" "diagnostic" "knowledge")

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "================================================"
echo " SRE Agent Full Deploy"
echo " Region:      ${REGION}"
echo " Environment: ${ENVIRONMENT}"
echo " Account:     ${ACCOUNT_ID}"
echo " ECR:         ${ECR_BASE}"
echo "================================================"

# --- 1. ECR ログイン ---
echo ""
echo "[1/6] ECR Login..."
aws ecr get-login-password --region "${REGION}" \
    | docker login --username AWS --password-stdin "${ECR_BASE}"

# --- 2 & 3. Docker build + push ---
echo ""
echo "[2/6] Docker build & push (${#AGENTS[@]} agents)..."

for AGENT in "${AGENTS[@]}"; do
    DOCKERFILE="${PROJECT_ROOT}/agents/${AGENT}/Dockerfile"
    IMAGE_URI="${ECR_BASE}/sre-agent/${AGENT}:latest"

    if [ ! -f "${DOCKERFILE}" ]; then
        echo "  Warning: ${DOCKERFILE} not found, skipping ${AGENT}"
        continue
    fi

    echo "  Building ${AGENT}..."
    docker build -t "${IMAGE_URI}" -f "${DOCKERFILE}" "${PROJECT_ROOT}"

    echo "  Pushing ${AGENT}..."
    docker push "${IMAGE_URI}"
    echo "  Pushed: ${IMAGE_URI}"
done

# --- 4. CDK deploy ---
echo ""
echo "[4/6] CDK Deploy..."
cd "${PROJECT_ROOT}/infra"
npm run build

# 本番環境では承認を要求、それ以外は自動承認
if [ "${ENVIRONMENT}" = "production" ]; then
    APPROVAL="broadening"
else
    APPROVAL="never"
fi
npx cdk deploy --require-approval "${APPROVAL}"

# --- 5. Gateway setup + target registration ---
echo ""
echo "[5/6] Gateway Setup & Target Registration..."
chmod +x "${PROJECT_ROOT}/gateway/setup-gateway.sh"
"${PROJECT_ROOT}/gateway/setup-gateway.sh"

# --- 6. Knowledge seed ---
echo ""
echo "[6/6] Seeding Knowledge Base..."
cd "${PROJECT_ROOT}"
if [ -z "${MEMORY_ID:-}" ]; then
    echo "  Warning: MEMORY_ID not set. Skipping Memory API seed."
    echo "  Set MEMORY_ID env var and re-run: python scripts/seed-knowledge.py"
else
    python scripts/seed-knowledge.py --memory-id "${MEMORY_ID}" --region "${REGION}"
fi

echo ""
echo "================================================"
echo " Deploy Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "  Test: python scripts/trigger-alert.py --scenario api_5xx_spike"
echo "  Logs: aws logs tail /sre-agent/orchestrator --follow"
