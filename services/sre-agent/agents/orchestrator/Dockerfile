FROM public.ecr.aws/docker/library/python:3.12-slim

# Lambda Web Adapter (AgentCore Runtime 用)
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/

WORKDIR /app

# Build context must be sre-agent/ root:
#   docker build -f agents/orchestrator/Dockerfile .
COPY requirements-base.txt .
COPY agents/orchestrator/requirements.txt ./agents-requirements.txt
RUN pip install --no-cache-dir -r requirements-base.txt -r agents-requirements.txt

# Copy shared modules
COPY common/ ./common/

# Copy agent code
COPY agents/orchestrator/ ./agents/orchestrator/

# 非 root ユーザーで実行
RUN adduser --disabled-password --no-create-home appuser
USER appuser

# AgentCore Runtime はポート 8080 を待受
ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "agents.orchestrator.main"]
