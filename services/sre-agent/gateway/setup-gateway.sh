#!/bin/bash
# Gateway 作成スクリプト（MCP Protocol + Target 登録自動化）
# 再作成可能（冪等性考慮）
# AWS CLI service: bedrock-agentcore-control (Control Plane)

set -euo pipefail

REGION="${AWS_REGION:-us-west-2}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
GATEWAY_NAME="sre-agent-gateway"
INTERCEPTOR_LAMBDA_NAME="sre-agent-interceptor"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/sre-agent-runtime-role"

AGENTS=("diagnostic" "knowledge")

echo "=== SRE Agent Gateway Setup ==="
echo "Region:  ${REGION}"
echo "Account: ${ACCOUNT_ID}"

# 1. Interceptor Lambda ARN 取得
echo "--- Checking Interceptor Lambda ---"
INTERCEPTOR_ARN=$(aws lambda get-function \
    --function-name "${INTERCEPTOR_LAMBDA_NAME}" \
    --region "${REGION}" \
    --query "Configuration.FunctionArn" \
    --output text 2>/dev/null || echo "")

if [ -n "${INTERCEPTOR_ARN}" ] && [ "${INTERCEPTOR_ARN}" != "None" ]; then
    echo "  Interceptor Lambda ARN: ${INTERCEPTOR_ARN}"
else
    echo "  Warning: Interceptor Lambda '${INTERCEPTOR_LAMBDA_NAME}' not found."
    echo "  Deploy via CDK first, then re-run this script."
    INTERCEPTOR_ARN=""
fi

# 2. Gateway 作成/確認
echo "--- Creating/Updating Gateway ---"
EXISTING=$(aws bedrock-agentcore-control list-gateways \
    --region "${REGION}" \
    --query "items[?name=='${GATEWAY_NAME}'].gatewayId" \
    --output text 2>/dev/null || echo "")

if [ -n "${EXISTING}" ] && [ "${EXISTING}" != "None" ]; then
    echo "Gateway already exists: ${EXISTING}"
    GATEWAY_ID="${EXISTING}"
else
    echo "Creating new gateway..."

    # Interceptor 設定（Lambda がある場合のみ）
    INTERCEPTOR_OPT=""
    if [ -n "${INTERCEPTOR_ARN}" ]; then
        INTERCEPTOR_OPT='--interceptor-configurations [{"interceptor":{"lambda":{"arn":"'"${INTERCEPTOR_ARN}"'"}},"interceptionPoints":["REQUEST","RESPONSE"]}]'
    fi

    GATEWAY_ID=$(aws bedrock-agentcore-control create-gateway \
        --region "${REGION}" \
        --name "${GATEWAY_NAME}" \
        --description "SRE Agent Gateway with MCP Protocol" \
        --role-arn "${ROLE_ARN}" \
        --protocol-type MCP \
        --authorizer-type NONE \
        ${INTERCEPTOR_OPT} \
        --query "gatewayId" \
        --output text)
    echo "Gateway created: ${GATEWAY_ID}"

    # Gateway が READY になるまで待機（最大 60 秒）
    echo "  Waiting for gateway to become ready..."
    for i in $(seq 1 12); do
        STATUS=$(aws bedrock-agentcore-control get-gateway \
            --gateway-identifier "${GATEWAY_ID}" \
            --region "${REGION}" \
            --query "status" \
            --output text 2>/dev/null || echo "UNKNOWN")
        if [ "${STATUS}" = "READY" ] || [ "${STATUS}" = "ACTIVE" ] || [ "${STATUS}" = "CREATE_COMPLETE" ]; then
            echo "  Gateway is ready (status: ${STATUS})"
            break
        fi
        echo "  Status: ${STATUS}, waiting 5s... (${i}/12)"
        sleep 5
    done
fi

# 3. Target 登録（Diagnostic / Knowledge Agent）
# NOTE: AgentCore Runtime agents don't have direct endpoints yet.
#       Target registration requires MCP server endpoint or Lambda ARN.
#       Skipping target registration until agents are deployed to AgentCore Runtime.
echo "--- Target Registration ---"
echo "  Note: Target registration requires running MCP server endpoints."
echo "  After deploying agents to AgentCore Runtime, re-run this script"
echo "  or register targets manually with:"
echo "    aws bedrock-agentcore-control create-gateway-target \\"
echo "      --gateway-identifier ${GATEWAY_ID:-<GATEWAY_ID>} \\"
echo "      --name sre-agent-<agent> \\"
echo "      --target-configuration '{\"mcp\":{\"mcpServer\":{\"endpoint\":\"https://<agent-endpoint>\"}}}'"

echo ""
echo "=== Gateway Setup Complete ==="
echo "Gateway ID: ${GATEWAY_ID}"
echo ""
echo "Next steps:"
echo "  1. Deploy agents to AgentCore Runtime (invoke-agent-runtime)"
echo "  2. Register targets with gateway endpoints"
echo "  3. Test: python scripts/trigger-alert.py --scenario api_5xx_spike"
