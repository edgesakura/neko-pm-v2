---
name: api-retry-helper
description: 外部API呼び出しの汎用リトライロジック（exponential backoff、レート制限対応）
---

# API Retry Helper

外部API呼び出しのための汎用リトライロジック実装パターン集。exponential backoff、レート制限対応、タイムアウト処理を含む包括的なエラーハンドリングを提供します。

## このスキルが適用される場面

| ユースケース | 適用理由 |
|------------|---------|
| 外部API連携（Anthropic, OpenAI, AWS等） | ネットワーク不安定性への対応 |
| HTTP/REST APIクライアント実装 | 一時的なエラーの自動復旧 |
| レート制限のあるサービス連携 | 429エラーの適切な処理 |
| マイクロサービス間通信 | サービス間の可用性向上 |
| データベースクエリ（接続エラー対応） | 接続プールの枯渇対応 |

## 基本概念

### 1. Exponential Backoff（指数バックオフ）

リトライ間隔を指数関数的に増加させる手法：

```
1回目の失敗: 1秒待機
2回目の失敗: 2秒待機
3回目の失敗: 4秒待機
4回目の失敗: 8秒待機
```

**利点**:
- サーバー負荷の軽減
- 一時的な障害からの回復時間を確保
- カスケード障害の防止

### 2. レート制限対応

HTTP 429（Too Many Requests）エラーの特別処理：

```
通常エラー: 標準のexponential backoff
レート制限: 2倍の待機時間（より慎重に）
```

**理由**:
- API提供者の保護
- アカウント停止のリスク軽減
- 公平な利用の実現

### 3. 最大リトライ回数

無限ループを防ぐための上限設定（推奨: 3-5回）

## 実装パターン

### パターン1: 基本的なリトライロジック（TypeScript）

```typescript
/**
 * 基本的なリトライ実装
 *
 * @param fn - リトライする非同期関数
 * @param maxRetries - 最大リトライ回数（デフォルト: 3）
 * @param baseDelay - 基本待機時間（ミリ秒、デフォルト: 1000）
 */
async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000
): Promise<T> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const result = await fn();
      return result;
    } catch (error: any) {
      lastError = error;

      // 最後の試行ではリトライしない
      if (attempt === maxRetries - 1) {
        break;
      }

      // Exponential backoff計算
      const delay = baseDelay * Math.pow(2, attempt);

      console.warn(`リトライ ${attempt + 1}/${maxRetries}: ${delay}ms後に再試行`);
      await sleep(delay);
    }
  }

  throw lastError || new Error('リトライ失敗');
}

/**
 * スリープ関数
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
```

**使用例**:
```typescript
// API呼び出しをリトライ
const data = await retryWithBackoff(async () => {
  const response = await fetch('https://api.example.com/data');
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
});
```

### パターン2: レート制限対応版

```typescript
/**
 * レート制限対応リトライ
 * HTTP 429エラーの場合は待機時間を2倍にする
 */
async function retryWithRateLimitHandling<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000
): Promise<T> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const result = await fn();
      return result;
    } catch (error: any) {
      lastError = error;

      if (attempt === maxRetries - 1) {
        break;
      }

      // レート制限エラーの検出
      const isRateLimit =
        error.status === 429 ||
        error.message?.includes('rate limit') ||
        error.message?.includes('429');

      // レート制限時は待機時間を2倍に
      const multiplier = isRateLimit ? 2 : 1;
      const delay = baseDelay * Math.pow(2, attempt) * multiplier;

      const errorType = isRateLimit ? 'レート制限' : 'エラー';
      console.warn(`${errorType}検出 (試行${attempt + 1}/${maxRetries}): ${delay}ms後に再試行`);

      await sleep(delay);
    }
  }

  throw lastError || new Error('リトライ失敗');
}
```

### パターン3: タイムアウト付きリトライ

```typescript
/**
 * タイムアウト処理付きリトライ
 */
async function retryWithTimeout<T>(
  fn: () => Promise<T>,
  options: {
    maxRetries?: number;
    baseDelay?: number;
    timeout?: number; // 個別リトライのタイムアウト（ミリ秒）
  } = {}
): Promise<T> {
  const {
    maxRetries = 3,
    baseDelay = 1000,
    timeout = 30000, // デフォルト30秒
  } = options;

  let lastError: Error | null = null;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      // タイムアウト処理
      const result = await Promise.race([
        fn(),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error('Timeout')), timeout)
        ),
      ]);

      return result;
    } catch (error: any) {
      lastError = error;

      if (attempt === maxRetries - 1) {
        break;
      }

      const delay = baseDelay * Math.pow(2, attempt);
      console.warn(`リトライ ${attempt + 1}/${maxRetries}: ${delay}ms後に再試行`);
      await sleep(delay);
    }
  }

  throw lastError || new Error('リトライ失敗');
}
```

### パターン4: クラスベース実装（再利用性重視）

```typescript
/**
 * 再利用可能なリトライクラス
 */
class RetryHandler {
  constructor(
    private maxRetries: number = 3,
    private baseDelay: number = 1000
  ) {}

  /**
   * リトライ実行
   */
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        return await fn();
      } catch (error: any) {
        lastError = error;

        if (attempt === this.maxRetries - 1) {
          break;
        }

        const delay = this.calculateDelay(attempt, error);
        await this.sleep(delay);
      }
    }

    throw lastError || new Error('リトライ失敗');
  }

  /**
   * 待機時間を計算（レート制限対応）
   */
  private calculateDelay(attempt: number, error: any): number {
    const isRateLimit =
      error.status === 429 ||
      error.message?.includes('rate limit');

    const multiplier = isRateLimit ? 2 : 1;
    return this.baseDelay * Math.pow(2, attempt) * multiplier;
  }

  /**
   * スリープ
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

// 使用例
const retryHandler = new RetryHandler(3, 1000);
const result = await retryHandler.execute(() => apiCall());
```

## 実践的な使用例

### 例1: Anthropic Claude API（consul-slideman実装）

```typescript
import Anthropic from '@anthropic-ai/sdk';

class LLMModule {
  private client: Anthropic;
  private maxRetries = 3;
  private baseDelay = 1000;

  constructor(apiKey: string) {
    if (!apiKey) {
      throw new Error('ANTHROPIC_API_KEY not configured');
    }
    this.client = new Anthropic({ apiKey });
  }

  /**
   * Claude APIをリトライロジック付きで呼び出す
   */
  private async callClaudeWithRetry(
    params: Anthropic.MessageCreateParams & { stream?: false }
  ): Promise<Anthropic.Message> {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        const response = await this.client.messages.create({
          ...params,
          stream: false,
        });
        return response;
      } catch (error: any) {
        lastError = error;

        if (attempt === this.maxRetries - 1) {
          break;
        }

        // レート制限エラーの場合はより長い間隔で待機
        const isRateLimit = error.status === 429 || error.message?.includes('rate limit');
        const delay = isRateLimit
          ? this.baseDelay * Math.pow(2, attempt) * 2
          : this.baseDelay * Math.pow(2, attempt);

        console.warn(`⚠️  API呼び出し失敗（試行${attempt + 1}/${this.maxRetries}）: ${error.message}`);
        console.warn(`   ${delay}ms後にリトライします...`);

        await this.sleep(delay);
      }
    }

    throw lastError || new Error('Claude API呼び出しに失敗しました');
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * スライド構成を生成
   */
  async generateOutline(theme: string): Promise<any> {
    return await this.callClaudeWithRetry({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 4096,
      messages: [{ role: 'user', content: `テーマ: ${theme}` }],
    });
  }
}
```

### 例2: Tavily Web検索API

```typescript
class WebSearchModule {
  private apiKey: string;
  private maxRetries = 3;
  private baseDelay = 1000;

  constructor(apiKey: string) {
    if (!apiKey) {
      console.warn('⚠️  TAVILY_API_KEY未設定: フォールバックモードで動作');
    }
    this.apiKey = apiKey;
  }

  /**
   * Tavily APIで検索（リトライ付き）
   */
  private async searchWithTavilyAPI(query: string): Promise<any[]> {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        const response = await fetch('https://api.tavily.com/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            api_key: this.apiKey,
            query,
            max_results: 5,
          }),
        });

        if (!response.ok) {
          throw new Error(`Tavily API error: ${response.status}`);
        }

        const data = await response.json();
        return data.results || [];
      } catch (error: any) {
        lastError = error;

        if (attempt === this.maxRetries - 1) {
          break;
        }

        const isRateLimit = error.message?.includes('429');
        const delay = isRateLimit
          ? this.baseDelay * Math.pow(2, attempt) * 2
          : this.baseDelay * Math.pow(2, attempt);

        console.warn(`⚠️  検索失敗（試行${attempt + 1}/${this.maxRetries}）: ${delay}ms後に再試行`);
        await this.sleep(delay);
      }
    }

    throw lastError || new Error('Tavily API検索に失敗');
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Web検索実行（フォールバック対応）
   */
  async search(query: string): Promise<any[]> {
    try {
      return await this.searchWithTavilyAPI(query);
    } catch (error: any) {
      console.warn(`⚠️  API検索失敗: ${error.message}`);
      console.warn('   フォールバックモードに切り替えます');
      return this.getFallbackResults(query);
    }
  }

  private getFallbackResults(query: string): any[] {
    // モックデータを返す
    return [
      {
        title: `${query}に関する情報`,
        url: 'https://example.com',
        content: `${query}についての参考情報`,
        score: 0.8,
      },
    ];
  }
}
```

### 例3: AWS SDK（Datadog監視設定）

```typescript
import { CloudWatchClient, PutMetricAlarmCommand } from '@aws-sdk/client-cloudwatch';

class DatadogAWSIntegration {
  private client: CloudWatchClient;
  private retryHandler: RetryHandler;

  constructor() {
    this.client = new CloudWatchClient({ region: 'us-east-1' });
    this.retryHandler = new RetryHandler(3, 1000);
  }

  /**
   * CloudWatchアラーム作成（リトライ付き）
   */
  async createAlarm(config: any): Promise<void> {
    await this.retryHandler.execute(async () => {
      const command = new PutMetricAlarmCommand(config);
      await this.client.send(command);
    });
  }
}
```

### 例4: データベースクエリ（Supabase）

```typescript
import { createClient, SupabaseClient } from '@supabase/supabase-js';

class DatabaseRepository {
  private client: SupabaseClient;
  private maxRetries = 3;
  private baseDelay = 500; // データベースは短めの間隔

  constructor(url: string, key: string) {
    this.client = createClient(url, key);
  }

  /**
   * リトライ付きクエリ実行
   */
  async queryWithRetry<T>(
    queryFn: (client: SupabaseClient) => Promise<{ data: T | null; error: any }>
  ): Promise<T> {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        const { data, error } = await queryFn(this.client);

        if (error) {
          throw new Error(error.message);
        }

        if (!data) {
          throw new Error('No data returned');
        }

        return data;
      } catch (error: any) {
        lastError = error;

        if (attempt === this.maxRetries - 1) {
          break;
        }

        // 接続エラーの場合は少し長めに待機
        const isConnectionError = error.message?.includes('connection');
        const delay = isConnectionError
          ? this.baseDelay * Math.pow(2, attempt) * 1.5
          : this.baseDelay * Math.pow(2, attempt);

        console.warn(`⚠️  クエリ失敗（試行${attempt + 1}/${this.maxRetries}）: ${delay}ms後に再試行`);
        await this.sleep(delay);
      }
    }

    throw lastError || new Error('データベースクエリ失敗');
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * ユーザー取得
   */
  async getUser(id: string): Promise<any> {
    return await this.queryWithRetry(async (client) => {
      return await client.from('users').select('*').eq('id', id).single();
    });
  }
}
```

## ベストプラクティス

### 1. 適切な最大リトライ回数の設定

| サービスタイプ | 推奨回数 | 理由 |
|-------------|---------|------|
| 外部API（Claude, OpenAI等） | 3-5回 | ネットワーク不安定性を考慮 |
| 内部マイクロサービス | 2-3回 | 早期の障害検出が重要 |
| データベースクエリ | 2-3回 | 長時間のリトライは他への影響大 |
| バッチ処理 | 5-10回 | 時間的余裕がある |

### 2. 基本待機時間の設定

```typescript
// ✅ GOOD: サービスの特性に応じて調整
const llmRetry = new RetryHandler(3, 1000);      // LLM: 1秒
const dbRetry = new RetryHandler(3, 500);        // DB: 0.5秒
const batchRetry = new RetryHandler(5, 2000);    // バッチ: 2秒

// ❌ BAD: すべて同じ設定
const retry = new RetryHandler(3, 1000);
```

### 3. エラーログの記録

```typescript
// ✅ GOOD: 構造化ログで詳細を記録
console.warn(JSON.stringify({
  level: 'warn',
  message: 'API呼び出し失敗',
  attempt: attempt + 1,
  maxRetries: this.maxRetries,
  error: error.message,
  isRateLimit,
  nextRetryIn: delay,
}));

// ❌ BAD: 情報不足
console.warn('エラー');
```

### 4. フォールバック処理の実装

```typescript
// ✅ GOOD: リトライ失敗後のフォールバック
async function searchWithFallback(query: string): Promise<any[]> {
  try {
    return await searchWithRetry(query);
  } catch (error) {
    console.warn('API検索失敗、フォールバックモードに切り替え');
    return getFallbackResults(query);
  }
}

// ❌ BAD: エラーをそのまま投げる
async function search(query: string): Promise<any[]> {
  return await searchWithRetry(query); // 失敗したら例外
}
```

### 5. Jitter（ジッター）の追加

複数クライアントが同時にリトライする場合の衝突を防ぐ：

```typescript
function calculateDelayWithJitter(attempt: number, baseDelay: number): number {
  const exponentialDelay = baseDelay * Math.pow(2, attempt);

  // ±20%のランダムなジッターを追加
  const jitter = exponentialDelay * 0.2 * (Math.random() - 0.5);

  return Math.floor(exponentialDelay + jitter);
}
```

### 6. 最大待機時間の上限設定

```typescript
function calculateDelay(attempt: number, baseDelay: number): number {
  const exponentialDelay = baseDelay * Math.pow(2, attempt);

  // 最大30秒に制限
  const maxDelay = 30000;

  return Math.min(exponentialDelay, maxDelay);
}
```

## トラブルシューティング

### Q1: リトライが多すぎてタイムアウトする

**症状**: 全リトライが完了する前にクライアント側でタイムアウト

**解決策**:
```typescript
// 個別リトライのタイムアウトを設定
const result = await retryWithTimeout(apiCall, {
  maxRetries: 3,
  baseDelay: 1000,
  timeout: 10000, // 各リトライ10秒まで
});
```

### Q2: レート制限に引っかかり続ける

**症状**: 何度リトライしてもHTTP 429エラー

**解決策**:
```typescript
// レート制限時の待機時間を大幅に増やす
const isRateLimit = error.status === 429;
const delay = isRateLimit
  ? this.baseDelay * Math.pow(2, attempt) * 5 // 5倍に
  : this.baseDelay * Math.pow(2, attempt);
```

### Q3: カスケード障害が発生する

**症状**: リトライが上流のサービス障害を悪化させる

**解決策**:
```typescript
// サーキットブレーカーパターンを追加
class CircuitBreaker {
  private failureCount = 0;
  private threshold = 5;
  private isOpen = false;

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.isOpen) {
      throw new Error('Circuit breaker is open');
    }

    try {
      const result = await fn();
      this.failureCount = 0; // 成功したらリセット
      return result;
    } catch (error) {
      this.failureCount++;
      if (this.failureCount >= this.threshold) {
        this.isOpen = true;
        setTimeout(() => { this.isOpen = false; }, 60000); // 1分後に再開
      }
      throw error;
    }
  }
}
```

### Q4: メモリリークが発生する

**症状**: 長時間稼働後にメモリ使用量が増加

**解決策**:
```typescript
// Promise.race でタイムアウト処理を適切に実装
async function retryWithProperTimeout<T>(
  fn: () => Promise<T>,
  timeout: number
): Promise<T> {
  const timeoutPromise = new Promise<never>((_, reject) => {
    const timer = setTimeout(() => {
      reject(new Error('Timeout'));
    }, timeout);

    // タイムアウト後にタイマーをクリア
    timeoutPromise.finally(() => clearTimeout(timer));
  });

  return Promise.race([fn(), timeoutPromise]);
}
```

## アンチパターン

### ❌ 無限リトライ

```typescript
// BAD: 終わりがない
while (true) {
  try {
    return await apiCall();
  } catch (error) {
    await sleep(1000);
  }
}
```

### ❌ 固定間隔リトライ

```typescript
// BAD: サーバー負荷が下がらない
for (let i = 0; i < 10; i++) {
  try {
    return await apiCall();
  } catch (error) {
    await sleep(1000); // 常に1秒
  }
}
```

### ❌ エラーの種類を無視

```typescript
// BAD: すべてのエラーを同じように扱う
catch (error) {
  // 401 Unauthorized も429 Rate Limit も同じリトライ
  await sleep(1000);
}

// GOOD: エラーの種類に応じた処理
catch (error) {
  if (error.status === 401) {
    throw error; // 認証エラーはリトライ不要
  }
  if (error.status === 429) {
    await sleep(delay * 2); // レート制限は長めに
  } else {
    await sleep(delay);
  }
}
```

## テスト方法

### ユニットテスト例（Vitest）

```typescript
import { describe, it, expect, vi } from 'vitest';

describe('RetryHandler', () => {
  it('成功するまでリトライする', async () => {
    let callCount = 0;
    const mockFn = vi.fn().mockImplementation(() => {
      callCount++;
      if (callCount < 3) {
        throw new Error('API Error');
      }
      return Promise.resolve('success');
    });

    const handler = new RetryHandler(3, 100);
    const result = await handler.execute(mockFn);

    expect(result).toBe('success');
    expect(callCount).toBe(3);
  });

  it('最大リトライ回数を超えたらエラーを投げる', async () => {
    const mockFn = vi.fn().mockRejectedValue(new Error('API Error'));

    const handler = new RetryHandler(3, 100);

    await expect(handler.execute(mockFn)).rejects.toThrow('API Error');
    expect(mockFn).toHaveBeenCalledTimes(3);
  });

  it('レート制限エラーの場合は待機時間を2倍にする', async () => {
    let callCount = 0;
    const mockFn = vi.fn().mockImplementation(() => {
      callCount++;
      if (callCount < 2) {
        const error: any = new Error('Rate limit');
        error.status = 429;
        throw error;
      }
      return Promise.resolve('success');
    });

    const handler = new RetryHandler(3, 100);
    const result = await handler.execute(mockFn);

    expect(result).toBe('success');
    expect(callCount).toBe(2);
  });
});
```

## 参考実装

### consul-slideman プロジェクト

- **LLMモジュール**: `projects/consul-slideman/src/modules/llm.ts`
  - Anthropic Claude APIのリトライロジック実装
  - テストカバレッジ: 96.53%

- **Web検索モジュール**: `projects/consul-slideman/src/modules/search.ts`
  - Tavily APIのリトライロジック実装
  - フォールバック対応
  - テストカバレッジ: 99.25%

### テストファイル

- `projects/consul-slideman/src/__tests__/llm.test.ts`
- `projects/consul-slideman/src/__tests__/search.test.ts`

## まとめ

### 使用時のチェックリスト

- [ ] 適切な最大リトライ回数を設定（3-5回推奨）
- [ ] Exponential backoffを実装
- [ ] レート制限エラー（429）の特別処理
- [ ] エラーログの記録（構造化ログ推奨）
- [ ] フォールバック処理の実装
- [ ] タイムアウト処理の追加
- [ ] テストカバレッジ80%以上
- [ ] エラーの種類に応じた処理分岐

### コスト・パフォーマンス最適化

- **コスト削減**: フォールバックモードでAPI呼び出し回数を削減
- **レスポンス時間**: 最大待機時間の上限設定で過度な遅延を防止
- **可用性向上**: リトライロジックで一時的な障害を自動復旧

---

**このスキルは consul-slideman プロジェクトで実装・テスト済みです（テストカバレッジ87.08%）。**
