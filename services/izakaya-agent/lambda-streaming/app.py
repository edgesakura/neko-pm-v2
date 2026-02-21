"""
FastAPI Streaming Endpoint for Izakaya Agent (Lambda Web Adapter)

SSE streaming endpoint with Cognito JWT RS256 verification.
"""
import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, AsyncIterator

import boto3
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from jose import jwt, jwk
from jose.exceptions import JWTError
import httpx

# Structured logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

# Environment variables
RUNTIME_ARN = os.environ.get("RUNTIME_ARN")
MEMORY_ID = os.environ.get("MEMORY_ID")
CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")
COGNITO_REGION = os.environ.get("COGNITO_REGION", "ap-northeast-1")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")

# JWKS キャッシュ（グローバル変数 - Lambda コンテナ再利用）
_jwks_cache: Dict[str, Any] = {}


def _log(level: str, event: str, **kwargs):
    """Emit structured JSON log."""
    record = {"event": event, **kwargs}
    getattr(logger, level)(json.dumps(record, ensure_ascii=False, default=str))


async def get_jwks() -> Dict[str, Any]:
    """
    Fetch Cognito JWKS and cache globally.

    Returns:
        JWKS dictionary with keys
    """
    if _jwks_cache:
        return _jwks_cache

    jwks_url = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url)
            response.raise_for_status()
            jwks_data = response.json()

        _jwks_cache.update(jwks_data)
        _log("info", "jwks_fetched", keys_count=len(jwks_data.get("keys", [])))
        return _jwks_cache

    except Exception as e:
        _log("error", "jwks_fetch_failed", error=type(e).__name__)
        raise HTTPException(status_code=500, detail="JWKS fetch failed")


async def verify_jwt(token: str) -> Dict[str, Any]:
    """
    Verify Cognito JWT (RS256 signature).

    Args:
        token: Bearer token

    Returns:
        Decoded claims

    Raises:
        HTTPException: If verification fails
    """
    try:
        # Get unverified header to find kid
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            raise HTTPException(status_code=401, detail="Missing kid in token")

        # Get JWKS
        jwks_data = await get_jwks()
        keys = jwks_data.get("keys", [])

        # Find matching key
        key = next((k for k in keys if k.get("kid") == kid), None)
        if not key:
            raise HTTPException(status_code=401, detail="Public key not found")

        # Construct RSA public key
        public_key = jwk.construct(key)

        # Verify and decode
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=None,  # Cognito doesn't set aud for User Pool tokens
            options={"verify_aud": False}
        )

        # Validate token_use
        if claims.get("token_use") != "id":
            raise HTTPException(status_code=401, detail="Invalid token_use")

        return claims

    except JWTError as e:
        _log("warning", "jwt_verification_failed", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid token")
    except HTTPException:
        raise
    except Exception as e:
        _log("error", "jwt_verification_error", error=type(e).__name__)
        raise HTTPException(status_code=401, detail="Token verification failed")


def invoke_agentcore_runtime_sync(user_id: str, user_message: str) -> Dict[str, Any]:
    """
    Invoke Bedrock AgentCore Runtime (synchronous boto3 call).

    Returns:
        Dict with 'text' and optional 'restaurants'
    """
    try:
        client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)

        payload_str = json.dumps({"prompt": user_message, "user_id": user_id})

        response = client.invoke_agent_runtime(
            agentRuntimeArn=RUNTIME_ARN,
            runtimeSessionId=user_id,
            payload=payload_str,
        )

        # StreamingBody から読み取り
        result_json = response["response"].read().decode("utf-8")
        response_data = json.loads(result_json)

        # Parse response text
        response_text = "応答を取得できませんでした"
        if isinstance(response_data.get("error"), str):
            response_text = response_data["error"]
        else:
            result = response_data.get("result")
            if isinstance(result, str):
                response_text = result
            elif isinstance(result, dict):
                content = result.get("content", [])
                if content and isinstance(content, list) and isinstance(content[0], dict):
                    response_text = content[0].get("text", response_text)
                elif isinstance(result.get("text"), str):
                    response_text = result["text"]
                else:
                    response_text = str(result)

        # Extract restaurants
        restaurants = response_data.get("restaurants")

        return {"text": response_text, "restaurants": restaurants}

    except Exception as e:
        _log("error", "agentcore_invoke_failed", error_type=type(e).__name__)
        raise


def split_text_into_chunks(text: str, chunk_size: int = 20) -> list[str]:
    """
    Split text into chunks by sentence or fixed size.

    Args:
        text: Full response text
        chunk_size: Approximate character count per chunk

    Returns:
        List of text chunks
    """
    # Split by Japanese sentence delimiters
    sentences = re.split(r'([。！？\n])', text)

    chunks = []
    current_chunk = ""

    for i in range(0, len(sentences), 2):
        sentence = sentences[i]
        delimiter = sentences[i+1] if i+1 < len(sentences) else ""

        segment = sentence + delimiter

        if len(current_chunk) + len(segment) > chunk_size and current_chunk:
            chunks.append(current_chunk)
            current_chunk = segment
        else:
            current_chunk += segment

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


async def stream_agentcore_response(user_id: str, user_message: str) -> AsyncIterator[str]:
    """
    Stream AgentCore response as SSE events.

    Yields:
        SSE formatted event strings
    """
    t_start = time.time()

    try:
        # Invoke AgentCore (同期呼び出しをスレッドプールで実行)
        # Heartbeat を送信しながら待機（ブラウザのコネクション切断を防止）
        loop = asyncio.get_event_loop()
        invoke_task = loop.run_in_executor(
            None,
            invoke_agentcore_runtime_sync,
            user_id,
            user_message
        )

        # 初回 heartbeat を即座に送信
        yield ": heartbeat\n\n"

        # AgentCore 応答待ちの間、5秒ごとに heartbeat を送信
        while not invoke_task.done():
            try:
                result = await asyncio.wait_for(asyncio.shield(invoke_task), timeout=5.0)
                break
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
        else:
            result = invoke_task.result()

        response_text = result["text"]
        restaurants = result.get("restaurants")

        _log("info", "agentcore_response_received",
             user_id=user_id,
             text_length=len(response_text),
             has_restaurants=bool(restaurants))

        # テキストをチャンクに分割（疑似ストリーミング）
        chunks = split_text_into_chunks(response_text, chunk_size=30)

        for chunk in chunks:
            event_data = json.dumps({"content": chunk}, ensure_ascii=False)
            yield f"event: text\ndata: {event_data}\n\n"
            await asyncio.sleep(0.1)  # 100ms 遅延で疑似ストリーミング

        # restaurants イベント送信
        if restaurants:
            restaurants_data = json.dumps({"restaurants": restaurants}, ensure_ascii=False)
            yield f"event: restaurants\ndata: {restaurants_data}\n\n"

        # done イベント送信
        total_ms = round((time.time() - t_start) * 1000)
        done_data = json.dumps({"total_ms": total_ms}, ensure_ascii=False)
        yield f"event: done\ndata: {done_data}\n\n"

    except Exception as e:
        _log("error", "stream_error", error_type=type(e).__name__)
        error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
        yield f"event: error\ndata: {error_data}\n\n"


# FastAPI application
# CORS は Function URL 側で設定済み（二重ヘッダー防止のため CORSMiddleware は使わない）
app = FastAPI(title="Izakaya Agent Streaming API")


@app.post("/chat")
async def chat_endpoint(request: Request):
    """
    POST /chat - SSE streaming endpoint with Cognito JWT auth.

    Request:
        Headers: Authorization: Bearer <jwt>
        Body: {"message": "東京のおすすめ居酒屋"}

    Response:
        SSE stream with text/restaurants/done/error events
    """
    t_start = time.time()

    # Extract JWT from Authorization header
    # フロントエンドは "Bearer <token>" または "<token>" の両形式で送信する
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = auth_header.removeprefix("Bearer ").strip()

    # Verify JWT
    claims = await verify_jwt(token)
    user_id = claims.get("sub")

    if not user_id:
        raise HTTPException(status_code=401, detail="Missing sub in token")

    # Parse request body
    try:
        body = await request.json()
        message = body.get("message")

        if not isinstance(message, str) or not message.strip():
            raise HTTPException(status_code=400, detail="Missing or invalid message")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    _log("info", "chat_request", user_id=user_id, message_length=len(message))

    # Return SSE streaming response
    return StreamingResponse(
        stream_agentcore_response(user_id, message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx buffering 無効化
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "izakaya-agent-streaming"}
