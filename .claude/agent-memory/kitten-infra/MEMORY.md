# kitten-infra Memory

## AgentCore デプロイ知見
- Gateway 管理 API は `bedrock-agentcore-control`（Control Plane）を使用。`bedrock-agentcore` は Data Plane のみ
- `create-gateway` 必須パラメータ: `--name`, `--role-arn`, `--protocol-type`, `--authorizer-type`
- `interceptor-configurations` フォーマット: `{"interceptor":{"lambda":{"arn":"..."}},"interceptionPoints":["REQUEST","RESPONSE"]}`
- `list-gateways` レスポンスキー: `items`（`gateways` ではない）
- Gateway Target 登録には MCP サーバーエンドポイント URL が必要
- ECR リポジトリは CDK で作成 → CDK deploy を ECR push より先に実行する必要あり

## AWS アカウント情報
- Account: 921563379197, Region: us-west-2
- SreAgentStack: Gateway ID `sre-agent-gateway-vqlzz9mg3j`

## CDK 知見
- CDK bootstrap は `npx cdk bootstrap aws://<account>/<region>` で実行
- development 環境は `--require-approval never` で自動承認

## Docker / ECR 知見
- WSL2 の Docker: `~/.docker/config.json` の `credsStore: desktop.exe` 削除必要（既知）
- ECR login: `aws ecr get-login-password | docker login --username AWS --password-stdin <ECR_BASE>`
- 3 agent (orchestrator/diagnostic/knowledge) すべて python:3.12-slim + Lambda Web Adapter
