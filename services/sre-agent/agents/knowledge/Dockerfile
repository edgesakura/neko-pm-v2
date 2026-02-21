FROM public.ecr.aws/docker/library/python:3.12-slim
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/

WORKDIR /app

# Build context must be sre-agent/ root:
#   docker build -f agents/knowledge/Dockerfile .
COPY agents/knowledge/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY common/ ./common/
COPY mock/ ./mock/

# Copy agent code
COPY agents/knowledge/ ./agents/knowledge/

# 非 root ユーザーで実行
RUN adduser --disabled-password --no-create-home appuser
USER appuser

WORKDIR /app/agents/knowledge
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
