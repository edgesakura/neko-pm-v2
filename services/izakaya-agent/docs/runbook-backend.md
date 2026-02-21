# Izakaya Backend Runbook

## Scope
- Service: `izakaya-agent-line-webhook` (Lambda)
- Web endpoint: `https://ok1y8ns08b.execute-api.ap-northeast-1.amazonaws.com/prod/chat`
- Region: `ap-northeast-1`

## Common Symptoms
- Browser: `No 'Access-Control-Allow-Origin' header is present`
- Browser: `TypeError: Failed to fetch` + `net::ERR_FAILED 200 (OK)`
- API: `401 Unauthorized`
- Lambda init/import error (`Runtime.ImportModuleError`)
- AgentCore parameter validation errors

## First Triage
1. Confirm browser origin (`http://localhost:3001` / `http://localhost:3002`).
2. Tail Lambda logs:
```bash
aws logs tail /aws/lambda/izakaya-agent-line-webhook \
  --since 15m --region ap-northeast-1 --format short
```
3. Check if failure is CORS-only or backend runtime/auth.

## Root Cause Map
### CORS blocked with 200
Cause:
- Lambda proxy response lacks CORS headers on POST/error responses.

Fix:
- Add CORS headers in `lambda/handler.py` for all responses.
- Include `OPTIONS` fallback in Lambda handler.

### Unauthorized source
Cause:
- Authorizer claim path mismatch (`claims` vs `jwt.claims`).

Fix:
- Parse both forms and require `sub`.

### Import module error (`pydantic_core._pydantic_core`)
Cause:
- Layer binary mismatch for Lambda runtime.

Fix:
- Rebuild layer with Linux-compatible wheels for Python 3.11.

### AgentCore runtimeSessionId length
Cause:
- Too-short test user/session id.

Fix:
- Use Cognito `sub`-like value (UUID length) in tests.

## Hotfix Deploy (Lambda code only)
From `output/izakaya-agent/lambda`:

```bash
zip -q /tmp/izakaya-agent-lambda.zip handler.py
aws lambda update-function-code \
  --function-name izakaya-agent-line-webhook \
  --region ap-northeast-1 \
  --zip-file fileb:///tmp/izakaya-agent-lambda.zip
aws lambda wait function-updated \
  --function-name izakaya-agent-line-webhook \
  --region ap-northeast-1
```

## Smoke Tests
### 1) CORS header presence (unauthorized path is OK)
```bash
aws lambda invoke \
  --function-name izakaya-agent-line-webhook \
  --region ap-northeast-1 \
  --cli-binary-format raw-in-base64-out \
  --payload '{"httpMethod":"POST","headers":{"origin":"http://localhost:3002"},"body":"{}"}' \
  /tmp/izakaya-agent-smoke.json >/tmp/izakaya-agent-smoke-meta.json
cat /tmp/izakaya-agent-smoke.json
```

Expected:
- `statusCode` may be `401`
- headers include `Access-Control-Allow-Origin: http://localhost:3002`

### 2) Web flow payload
```bash
aws lambda invoke \
  --function-name izakaya-agent-line-webhook \
  --region ap-northeast-1 \
  --cli-binary-format raw-in-base64-out \
  --payload '{"httpMethod":"POST","headers":{"origin":"http://localhost:3002"},"requestContext":{"authorizer":{"claims":{"sub":"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}}},"body":"{\"message\":\"渋谷のおすすめ居酒屋教えて\"}"}' \
  /tmp/izakaya-agent-web-smoke.json >/tmp/izakaya-agent-web-smoke-meta.json
cat /tmp/izakaya-agent-web-smoke.json
```

Expected:
- `statusCode: 200`
- response headers include CORS
- body contains `message` and `response`

## Frontend Notes
- `nomibero-web/app/page.tsx` currently reads `data.response`.
- Backend should keep `response` key for compatibility during transition.

## Escalation
If still failing after above:
1. Attach latest CloudWatch `RequestId` and error line.
2. Include browser origin and exact endpoint.
3. Include request headers/body shape (with secrets/tokens redacted).
