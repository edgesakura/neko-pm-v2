"""
LINE Webhook Handler for Izakaya Agent

This Lambda function handles LINE Messaging API webhooks,
verifies signatures, and invokes Bedrock AgentCore Runtime.
"""
import base64
import json
import logging
import os
import time
from typing import Any, Dict

import boto3
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)

# Structured logging setup
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
RUNTIME_ARN = os.environ.get("RUNTIME_ARN")
REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
CORS_ALLOWED_ORIGINS = {
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001,http://localhost:3002"
    ).split(",")
    if origin.strip()
}

# Secrets Manager client
secrets_client = boto3.client("secretsmanager", region_name=REGION)


def _log(level: str, event: str, **kwargs):
    """Emit structured JSON log for CloudWatch Insights."""
    record = {"event": event, **kwargs}
    getattr(logger, level)(json.dumps(record, ensure_ascii=False, default=str))


def get_secret(secret_name: str) -> str:
    """
    Retrieve secret from AWS Secrets Manager

    Args:
        secret_name: Secret name or ARN

    Returns:
        Secret string value

    Raises:
        Exception: If secret retrieval fails
    """
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return response["SecretString"]
    except Exception as e:
        _log("error", "secret_retrieval_failed", secret=secret_name, error=type(e).__name__)
        raise


# Initialize LINE Bot API components
CHANNEL_SECRET = get_secret("izakaya-agent/line-channel-secret")
CHANNEL_ACCESS_TOKEN = get_secret("izakaya-agent/line-channel-access-token")

handler = WebhookHandler(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)


def _extract_origin(event: Dict[str, Any]) -> str | None:
    headers = event.get("headers") or {}
    return headers.get("origin") or headers.get("Origin")


def build_cors_headers(event: Dict[str, Any]) -> Dict[str, str]:
    """Build CORS headers for browser-based Web API access."""
    origin = _extract_origin(event)

    headers: Dict[str, str] = {
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "OPTIONS,POST",
        "Vary": "Origin",
    }

    if origin and origin in CORS_ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"

    return headers


def make_response(status_code: int, body: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Lambda proxy response with CORS headers."""
    return {
        "statusCode": status_code,
        "headers": build_cors_headers(event),
        "body": json.dumps(body, ensure_ascii=False),
    }


def validate_event_source(event: Dict[str, Any]) -> str:
    """
    Validate event source (API Gateway + Cognito or LINE Webhook)

    Returns:
        Event source type: "web_api" or "line_webhook"

    Raises:
        ValueError: If event source is invalid or unauthorized
    """
    # API Gateway + Cognito経由の場合
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})
    claims = authorizer.get("claims") or authorizer.get("jwt", {}).get("claims")
    if claims and claims.get("sub"):
        return "web_api"

    # Function URL経由（LINE Webhook）の場合
    headers = event.get("headers") or {}
    signature = headers.get("x-line-signature") or headers.get("X-Line-Signature")
    if signature:
        return "line_webhook"

    raise ValueError("Unauthorized: Invalid event source")


def parse_request(event: Dict[str, Any], source: str) -> Dict[str, Any]:
    """
    Parse incoming request (LINE Webhook or Web API format)

    Returns:
        Normalized request with message, user_id, source, reply_token (if LINE)

    Raises:
        ValueError: If request format is invalid
    """
    body = event.get("body", "")
    if not body:
        raise ValueError("Missing request body")

    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")

    body_json = json.loads(body)

    # Web API format (Cognito認証済み)
    if source == "web_api":
        claims = (
            event.get("requestContext", {})
            .get("authorizer", {})
            .get("claims")
            or event.get("requestContext", {})
            .get("authorizer", {})
            .get("jwt", {})
            .get("claims", {})
        )
        user_id = claims.get("sub")
        message = body_json.get("message")

        if not user_id:
            raise ValueError("Missing Cognito user sub")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Missing or invalid message")

        return {
            "message": message,
            "user_id": user_id,
            "source": "web",
        }

    # LINE Webhook format
    if source == "line_webhook":
        events = body_json.get("events")
        if not isinstance(events, list) or not events:
            raise ValueError("Invalid LINE Webhook format")

        line_event = events[0]
        message = line_event.get("message", {}).get("text")
        user_id = line_event.get("source", {}).get("userId")
        reply_token = line_event.get("replyToken")

        if not isinstance(message, str) or not isinstance(user_id, str) or not isinstance(reply_token, str):
            raise ValueError("Invalid LINE message payload")

        return {
            "message": message,
            "user_id": user_id,
            "source": "line",
            "reply_token": reply_token,
        }

    raise ValueError("Invalid source type")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda entrypoint for LINE Webhook and Web API
    """
    t_start = time.time()
    request_id = getattr(context, "aws_request_id", "unknown")

    try:
        # CORS preflight fallback
        if event.get("httpMethod") == "OPTIONS":
            return make_response(200, {"status": "ok"}, event)

        # Validate event source
        try:
            source = validate_event_source(event)
        except ValueError as e:
            _log("warning", "unauthorized_access", request_id=request_id, error=str(e))
            return make_response(401, {"error": "Unauthorized"}, event)

        # LINE Webhook: Verify signature
        if source == "line_webhook":
            headers = event.get("headers") or {}
            signature = headers.get("x-line-signature") or headers.get("X-Line-Signature")
            body = event.get("body", "")

            if not signature:
                return make_response(401, {"error": "Missing LINE signature"}, event)

            if event.get("isBase64Encoded"):
                body = base64.b64decode(body).decode("utf-8")

            try:
                handler.handle(body, signature)
            except InvalidSignatureError:
                _log("warning", "invalid_line_signature", request_id=request_id)
                return make_response(401, {"error": "Invalid signature"}, event)

        # Parse request format
        request = parse_request(event, source)

        _log("info", "request_received",
             request_id=request_id, source=request["source"],
             user_id=request["user_id"],
             message_length=len(request["message"]))

        # Invoke AgentCore Runtime
        t0 = time.time()
        agent_result = invoke_agentcore_runtime(request["user_id"], request["message"])
        agentcore_ms = round((time.time() - t0) * 1000)
        response_text = agent_result["text"]

        _log("info", "agentcore_response",
             request_id=request_id,
             response_length=len(response_text),
             has_restaurants=bool(agent_result.get("restaurants")),
             agentcore_ms=agentcore_ms)

        # Send response based on source
        if request["source"] == "line":
            send_line_reply(request["reply_token"], response_text)
            total_ms = round((time.time() - t_start) * 1000)
            _log("info", "request_complete",
                 request_id=request_id, source="line", total_ms=total_ms)
            return make_response(200, {"status": "ok"}, event)

        # Web: Return text + structured restaurant data
        web_response = {
            "message": response_text,
            "response": response_text,
            "status": "success",
        }
        if agent_result.get("restaurants"):
            web_response["restaurants"] = agent_result["restaurants"]

        total_ms = round((time.time() - t_start) * 1000)
        _log("info", "request_complete",
             request_id=request_id, source="web", total_ms=total_ms)

        return make_response(200, web_response, event)

    except ValueError as e:
        total_ms = round((time.time() - t_start) * 1000)
        _log("warning", "invalid_request",
             request_id=request_id, error=str(e), total_ms=total_ms)
        return make_response(400, {"error": str(e)}, event)
    except Exception as e:
        total_ms = round((time.time() - t_start) * 1000)
        _log("error", "unhandled_error",
             request_id=request_id, error_type=type(e).__name__, total_ms=total_ms)
        return make_response(500, {"error": "Internal server error"}, event)


def invoke_agentcore_runtime(user_id: str, user_message: str) -> Dict[str, Any]:
    """
    Invoke Bedrock AgentCore Runtime using boto3 client

    Returns:
        Dict with 'text' (response string) and optional 'restaurants' (structured data)
    """
    try:
        client = boto3.client("bedrock-agentcore", region_name=REGION)

        payload = json.dumps({"prompt": user_message, "user_id": user_id})

        response = client.invoke_agent_runtime(
            agentRuntimeArn=RUNTIME_ARN,
            runtimeSessionId=user_id,
            payload=payload,
        )

        result_json = response["response"].read().decode("utf-8")
        response_data = json.loads(result_json)

        # Extract result message
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

        # Extract structured restaurant data if present
        restaurants = response_data.get("restaurants")

        return {"text": response_text, "restaurants": restaurants}

    except Exception as e:
        _log("error", "agentcore_invoke_failed", error_type=type(e).__name__)
        raise


def send_line_reply(reply_token: str, message: str) -> None:
    """
    Send reply message via LINE Messaging API
    """
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=message)],
                )
            )
        _log("info", "line_reply_sent", message_length=len(message))

    except Exception as e:
        _log("error", "line_reply_failed", error_type=type(e).__name__)
        raise
