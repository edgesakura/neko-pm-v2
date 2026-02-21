# Secrets Manager セットアップ手順

このドキュメントでは、LINE Bot「イザカヤくん」で使用するAPIキーの取得からAWS Secrets Managerへの登録までの手順を説明します。

## 概要

### 必要なAPIキー

本アプリケーションは以下の4つのシークレットを必要とします：

| シークレット名 | 用途 | 提供元 |
|-------------|------|--------|
| `izakaya-agent/hotpepper-api-key` | 居酒屋情報の検索 | リクルート Webサービス |
| `izakaya-agent/google-places-api-key` | 居酒屋のレビュー・評価取得 | Google Cloud Platform |
| `izakaya-agent/line-channel-secret` | LINE Webhookの署名検証 | LINE Developers |
| `izakaya-agent/line-channel-access-token` | LINE Messaging APIの呼び出し | LINE Developers |

### Secrets Managerに保存する理由

1. **セキュリティ**: APIキーをソースコードに含めず、安全に管理
2. **環境分離**: 開発・本番環境で異なるAPIキーを使用可能
3. **権限管理**: IAMロールベースのアクセス制御
4. **監査**: CloudTrailでアクセスログを記録
5. **ローテーション**: 定期的なキー更新が容易

## APIキー取得手順

### 1. Hotpepper API

#### 1.1 リクルートWebサービスへの登録

1. [リクルートWebサービス](https://webservice.recruit.co.jp/) にアクセス
2. 「新規登録」からアカウントを作成
3. メールアドレス認証を完了

#### 1.2 APIキーの発行

1. ログイン後、「Web API」→「グルメサーチAPI」を選択
2. 「APIキーを発行する」をクリック
3. 利用規約に同意
4. APIキーが表示されるので、安全な場所に保存

**制限事項**:
- 1日あたり3,000リクエストまで（無料プラン）
- APIキーは再表示できないため、発行時に必ず保存

#### 1.3 APIキーのテスト

```bash
# テストリクエスト（東京・居酒屋で検索）
curl "http://webservice.recruit.co.jp/hotpepper/gourmet/v1/?key=YOUR_API_KEY&keyword=居酒屋&large_area=Z011&format=json"
```

レスポンスに `results` が含まれていれば成功です。

### 2. Google Places API

#### 2.1 Google Cloud Consoleでの設定

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 新規プロジェクトを作成（既存プロジェクトでも可）
3. 「APIとサービス」→「ライブラリ」を選択

#### 2.2 Places APIの有効化

1. 検索ボックスで「Places API」を検索
2. 「Places API」をクリック
3. 「有効にする」をクリック

#### 2.3 APIキーの作成

1. 「APIとサービス」→「認証情報」を選択
2. 「認証情報を作成」→「APIキー」をクリック
3. APIキーが表示されるので、安全な場所に保存

#### 2.4 APIキーの制限設定（推奨）

セキュリティ強化のため、APIキーに制限を設定します：

1. 作成したAPIキーの「編集」をクリック
2. 「アプリケーションの制限」:
   - 「IPアドレス」を選択
   - Lambda実行環境のIPアドレス範囲を追加
3. 「APIの制限」:
   - 「キーを制限」を選択
   - 「Places API」のみを選択
4. 「保存」をクリック

#### 2.5 APIキーのテスト

```bash
# テストリクエスト（渋谷の居酒屋を検索）
curl "https://maps.googleapis.com/maps/api/place/textsearch/json?query=居酒屋+渋谷&key=YOUR_API_KEY"
```

レスポンスに `results` 配列が含まれていれば成功です。

## Secrets Manager設定手順

### 前提条件

- AWS CLIがインストール済み
- 適切なIAM権限（`secretsmanager:CreateSecret`）を持つプロファイルで認証済み

### シークレットの作成

以下のコマンドを実行して、4つのシークレットを作成します：

```bash
# リージョンを設定（東京リージョン）
REGION="ap-northeast-1"

# 1. Hotpepper API Key
aws secretsmanager create-secret \
  --name izakaya-agent/hotpepper-api-key \
  --description "Hotpepper Gourmet API key for izakaya search" \
  --secret-string "YOUR_HOTPEPPER_API_KEY" \
  --region $REGION

# 2. Google Places API Key
aws secretsmanager create-secret \
  --name izakaya-agent/google-places-api-key \
  --description "Google Places API key for restaurant reviews" \
  --secret-string "YOUR_GOOGLE_PLACES_API_KEY" \
  --region $REGION

# 3. LINE Channel Secret
aws secretsmanager create-secret \
  --name izakaya-agent/line-channel-secret \
  --description "LINE Bot channel secret for signature verification" \
  --secret-string "YOUR_LINE_CHANNEL_SECRET" \
  --region $REGION

# 4. LINE Channel Access Token
aws secretsmanager create-secret \
  --name izakaya-agent/line-channel-access-token \
  --description "LINE Bot channel access token for messaging API" \
  --secret-string "YOUR_LINE_CHANNEL_ACCESS_TOKEN" \
  --region $REGION
```

**注意**: `YOUR_*` 部分は実際のAPIキーに置き換えてください。

### シークレットの更新（既に存在する場合）

既にシークレットが存在する場合は、`put-secret-value` を使って更新します：

```bash
aws secretsmanager put-secret-value \
  --secret-id izakaya-agent/hotpepper-api-key \
  --secret-string "NEW_HOTPEPPER_API_KEY" \
  --region ap-northeast-1
```

## 設定確認コマンド

### シークレットの存在確認

```bash
# 4つのシークレットがすべて存在するか確認
for secret in hotpepper-api-key google-places-api-key line-channel-secret line-channel-access-token; do
  echo "Checking: izakaya-agent/$secret"
  aws secretsmanager describe-secret \
    --secret-id "izakaya-agent/$secret" \
    --region ap-northeast-1 \
    --query '[Name, Description, LastAccessedDate]' \
    --output table
done
```

### シークレットの値を取得（テスト用）

**警告**: 本番環境では、シークレットの値を平文で表示しないでください。

```bash
# Hotpepper API Keyの値を取得
aws secretsmanager get-secret-value \
  --secret-id izakaya-agent/hotpepper-api-key \
  --region ap-northeast-1 \
  --query SecretString \
  --output text
```

### シークレットが空でないことを確認

```bash
# 値の長さを確認（空の場合は警告）
SECRET_VALUE=$(aws secretsmanager get-secret-value \
  --secret-id izakaya-agent/hotpepper-api-key \
  --region ap-northeast-1 \
  --query SecretString \
  --output text)

if [ -z "$SECRET_VALUE" ]; then
  echo "⚠️ WARNING: Secret is empty!"
else
  echo "✅ Secret is set (length: ${#SECRET_VALUE} characters)"
fi
```

## トラブルシューティング

### シークレットが見つからない場合

**エラー**: `ResourceNotFoundException: Secrets Manager can't find the specified secret.`

**原因**:
- シークレット名が間違っている
- リージョンが間違っている
- シークレットが削除されている

**対処法**:
```bash
# 存在するシークレットの一覧を確認
aws secretsmanager list-secrets \
  --region ap-northeast-1 \
  --query 'SecretList[?contains(Name, `izakaya-agent`)].Name'

# 正しいシークレット名で再作成
aws secretsmanager create-secret \
  --name izakaya-agent/hotpepper-api-key \
  --secret-string "YOUR_API_KEY" \
  --region ap-northeast-1
```

### IAM権限不足の場合

**エラー**: `AccessDeniedException: User is not authorized to perform: secretsmanager:GetSecretValue`

**原因**:
- 実行ロールに `secretsmanager:GetSecretValue` 権限がない
- リソースポリシーで特定のシークレットへのアクセスが拒否されている

**対処法**:

#### Lambda実行ロールに権限を追加

```bash
# IAMポリシーJSONを作成
cat > /tmp/secrets-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "IzakayaAgentSecretsAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:ap-northeast-1:*:secret:izakaya-agent/*"
      ]
    }
  ]
}
EOF

# Lambda実行ロールに権限を追加（ロール名は環境に応じて変更）
aws iam put-role-policy \
  --role-name IzakayaAgentLambdaExecutionRole \
  --policy-name SecretsManagerAccess \
  --policy-document file:///tmp/secrets-policy.json
```

#### AgentCore Runtimeのロールに権限を追加

```bash
# AgentCore Runtime用のポリシーJSON
cat > /tmp/agentcore-secrets-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "IzakayaAgentSecretsAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:ap-northeast-1:*:secret:izakaya-agent/*"
      ]
    }
  ]
}
EOF

# AgentCore Runtimeのロールに権限を追加
# ロール名は `aws iam list-roles | grep AmazonBedrockAgentCoreSDKRuntime` で確認
aws iam put-role-policy \
  --role-name AmazonBedrockAgentCoreSDKRuntime-ap-northeast-1-XXXXXXXX \
  --policy-name IzakayaAgentSecretsAccess \
  --policy-document file:///tmp/agentcore-secrets-policy.json
```

### 空のシークレット値の場合

**エラー**: API呼び出しが失敗し、`401 Unauthorized` または `403 Forbidden` が返る

**原因**:
- シークレットが作成されているが、値が空（`""`）
- シークレット作成時に `--secret-string` を指定し忘れた

**対処法**:
```bash
# シークレットの値を更新
aws secretsmanager put-secret-value \
  --secret-id izakaya-agent/hotpepper-api-key \
  --secret-string "YOUR_ACTUAL_API_KEY" \
  --region ap-northeast-1

# 値が正しく設定されたか確認
aws secretsmanager get-secret-value \
  --secret-id izakaya-agent/hotpepper-api-key \
  --region ap-northeast-1 \
  --query SecretString \
  --output text
```

### 検証ロジックでの防止策

アプリケーションコードに、シークレット値が空でないことを検証するロジックを追加することを推奨します：

```python
import boto3
import sys

def validate_secrets():
    """すべてのシークレットが設定されているか検証"""
    client = boto3.client('secretsmanager', region_name='ap-northeast-1')
    secrets = [
        'izakaya-agent/hotpepper-api-key',
        'izakaya-agent/google-places-api-key',
        'izakaya-agent/line-channel-secret',
        'izakaya-agent/line-channel-access-token'
    ]

    for secret_name in secrets:
        try:
            response = client.get_secret_value(SecretId=secret_name)
            value = response['SecretString']
            if not value or value.strip() == '':
                print(f"❌ ERROR: Secret '{secret_name}' is empty")
                sys.exit(1)
            print(f"✅ Secret '{secret_name}' is set")
        except Exception as e:
            print(f"❌ ERROR: Failed to retrieve '{secret_name}': {e}")
            sys.exit(1)

    print("✅ All secrets are properly configured")

if __name__ == '__main__':
    validate_secrets()
```

## セキュリティのベストプラクティス

1. **最小権限の原則**: IAMロールには必要最小限の権限のみ付与
2. **ワイルドカードの回避**: `izakaya-agent/*` ではなく、個別のシークレット名を指定
3. **ローテーションの設定**: 定期的なAPIキーの更新を検討
4. **監査ログの有効化**: CloudTrailでシークレットアクセスをモニタリング
5. **平文での保存禁止**: APIキーをコード・ログ・環境変数に含めない

## 参考リンク

- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [リクルートWebサービス API仕様](https://webservice.recruit.co.jp/doc/hotpepper/)
- [Google Places API Documentation](https://developers.google.com/maps/documentation/places/web-service)
- [LINE Messaging API Documentation](https://developers.line.biz/ja/docs/messaging-api/)
