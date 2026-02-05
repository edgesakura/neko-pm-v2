# Modern Web UI Skill

モダンでかっこいいWebアプリケーションUIを構築するためのデザインパターン集。

## 概要

このスキルは以下の最新UIトレンドを実装するためのテンプレートとガイドを提供します：

1. **ガラスモーフィズム（Glassmorphism）** - 半透明でぼかし効果のあるモダンなUI
2. **ネオンアクセント** - サイバーパンク風のグラデーションとグロー効果
3. **スムーズアニメーション** - cubic-bezier と CSS transitionsによる滑らかな動き
4. **CSS変数によるデザイントークン** - 統一的な色・影・トランジション管理
5. **ダークモード基調** - 目に優しいダークテーマ

## 適用シーン

- チャットアプリケーション
- ダッシュボード
- 管理画面
- ランディングページ
- モバイルアプリ風のWebアプリ

## デザイントークン（CSS変数）

```css
:root {
  /* Colors */
  --bg-gradient-start: #1a1a2e;
  --bg-gradient-end: #16213e;
  --glass-bg: rgba(255, 255, 255, 0.05);
  --glass-border: rgba(255, 255, 255, 0.1);
  --accent-cyan: #00f5ff;
  --accent-purple: #a855f7;
  --accent-blue: #3b82f6;
  --text-primary: #e0e0e0;
  --text-secondary: #909090;
  --text-dim: #505050;

  /* Shadows */
  --shadow-glow-cyan: 0 0 20px rgba(0, 245, 255, 0.3);
  --shadow-glow-purple: 0 0 20px rgba(168, 85, 247, 0.3);
  --shadow-glass: 0 8px 32px rgba(0, 0, 0, 0.3);

  /* Transitions */
  --transition-smooth: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  --transition-fast: all 0.2s ease;
}
```

### カラーパレット説明

| 変数 | 用途 |
|------|------|
| `--bg-gradient-start` / `--bg-gradient-end` | 背景グラデーション（ダークブルー系） |
| `--glass-bg` | ガラスモーフィズム背景（半透明白） |
| `--glass-border` | ガラスモーフィズムボーダー |
| `--accent-cyan` | プライマリアクセント（シアン） |
| `--accent-purple` | セカンダリアクセント（パープル） |
| `--text-primary` | メインテキスト（明るいグレー） |
| `--text-secondary` | サブテキスト（ミディアムグレー） |
| `--text-dim` | 補助テキスト（暗めグレー） |

## 実装パターン

### 1. ガラスモーフィズム

半透明背景とぼかし効果を組み合わせた透明感のあるUI。

```css
.glass {
  background: var(--glass-bg);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  box-shadow: var(--shadow-glass);
}
```

**使用例:**
```html
<div class="card glass">
  <h2>ガラスカード</h2>
  <p>背景が透けて見える半透明カード</p>
</div>
```

### 2. ネオングロー効果

グラデーションとシャドウを組み合わせたネオン風の光る効果。

```css
.glow-cyan {
  box-shadow: var(--shadow-glow-cyan);
}

.glow-purple {
  box-shadow: var(--shadow-glow-purple);
}

.gradient-accent {
  background: linear-gradient(135deg, var(--accent-cyan) 0%, var(--accent-purple) 100%);
}
```

**使用例:**
```html
<button class="btn gradient-accent glow-cyan">
  送信
</button>
```

### 3. スムーズアニメーション

#### フェードイン

```css
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.fade-in {
  animation: fadeIn 0.5s ease-out;
}
```

#### スライドイン

```css
@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.slide-in {
  animation: slideIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
```

#### パルスアニメーション

```css
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(0.9); }
}

.pulse {
  animation: pulse 2s ease-in-out infinite;
}
```

### 4. ボトムナビゲーション

モバイルアプリ風のボトムナビゲーションバー。

```html
<nav class="bottom-nav glass">
  <button class="nav-item active">
    <svg><!-- アイコン --></svg>
    <span>ホーム</span>
  </button>
  <button class="nav-item">
    <svg><!-- アイコン --></svg>
    <span>設定</span>
  </button>
</nav>
```

```css
.bottom-nav {
  display: flex;
  justify-content: space-around;
  padding: 0.75rem;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 100;
}

.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.5rem 1.5rem;
  background: transparent;
  border: none;
  border-radius: 1rem;
  color: var(--text-secondary);
  cursor: pointer;
  transition: var(--transition-fast);
}

.nav-item.active {
  background: linear-gradient(135deg, rgba(0, 245, 255, 0.2) 0%, rgba(168, 85, 247, 0.2) 100%);
  color: var(--accent-cyan);
  box-shadow: var(--shadow-glow-cyan);
}
```

### 5. タブ切り替え

フェードアニメーション付きのタブ切り替え。

```html
<div class="tab-content-wrapper">
  <div id="tab1" class="tab-content active">
    コンテンツ1
  </div>
  <div id="tab2" class="tab-content">
    コンテンツ2
  </div>
</div>
```

```css
.tab-content-wrapper {
  position: relative;
  flex: 1;
  overflow: hidden;
}

.tab-content {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.tab-content.active {
  opacity: 1;
  pointer-events: auto;
}
```

```javascript
// タブ切り替え関数
function switchTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(tab => {
    tab.classList.remove('active');
  });
  document.getElementById(tabId).classList.add('active');
}
```

## LocalStorage活用パターン

ユーザーデータの永続化（最大件数制限付き）。

```javascript
// 設定
const MAX_ITEMS = 100;
const STORAGE_KEY = 'app_data';

// 保存
function saveData(newItem) {
  try {
    let data = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    data.push(newItem);

    // 最大件数制限
    if (data.length > MAX_ITEMS) {
      data = data.slice(-MAX_ITEMS);
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (error) {
    console.error('Failed to save data:', error);
  }
}

// 読み込み
function loadData() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
  } catch (error) {
    console.error('Failed to load data:', error);
    return [];
  }
}

// クリア
function clearData() {
  if (confirm('データを削除しますか？')) {
    localStorage.removeItem(STORAGE_KEY);
    console.log('Data cleared');
  }
}
```

## 導入手順

### ステップ1: CSS変数を定義

```css
/* styles.css */
@import url('templates/modern-ui.css');

/* カスタマイズが必要な場合は変数を上書き */
:root {
  --accent-cyan: #00d4ff; /* カスタムシアン */
}
```

### ステップ2: HTMLにガラスモーフィズムを適用

```html
<div class="container">
  <header class="header glass">
    <h1>アプリタイトル</h1>
  </header>

  <main class="content glass">
    <!-- コンテンツ -->
  </main>

  <nav class="bottom-nav glass">
    <!-- ナビゲーション -->
  </nav>
</div>
```

### ステップ3: 背景グラデーションを設定

```css
body {
  background: linear-gradient(135deg, var(--bg-gradient-start) 0%, var(--bg-gradient-end) 100%);
  background-attachment: fixed;
  color: var(--text-primary);
  min-height: 100vh;
}
```

### ステップ4: アニメーションを追加

```html
<div class="card glass fade-in">
  <p>フェードインで表示されるカード</p>
</div>
```

## レスポンシブデザイン

```css
/* モバイル: デフォルト */
.container {
  max-width: 100%;
}

/* タブレット: 768px以上 */
@media (min-width: 768px) {
  .container {
    max-width: 768px;
    margin: 0 auto;
    border-left: 1px solid var(--glass-border);
    border-right: 1px solid var(--glass-border);
  }
}

/* デスクトップ: 1024px以上 */
@media (min-width: 1024px) {
  .container {
    max-width: 900px;
  }
}
```

## ブラウザ互換性

| 機能 | 対応ブラウザ |
|------|-------------|
| backdrop-filter | Chrome 76+, Safari 14+, Firefox 103+ |
| CSS変数 | すべてのモダンブラウザ |
| CSS Grid/Flexbox | すべてのモダンブラウザ |
| cubic-bezier | すべてのモダンブラウザ |

**注意:** backdrop-filterはiOS Safari 9+では `-webkit-` プレフィックスが必要。

## カスタマイズ例

### テーマカラーの変更

```css
:root {
  /* グリーン系テーマ */
  --accent-cyan: #00ff88;
  --accent-purple: #00cc66;
  --bg-gradient-start: #0f2027;
  --bg-gradient-end: #203a43;
}
```

### ライトモード対応

```css
body.light-mode {
  --bg-gradient-start: #f5f5f5;
  --bg-gradient-end: #e0e0e0;
  --glass-bg: rgba(0, 0, 0, 0.05);
  --glass-border: rgba(0, 0, 0, 0.1);
  --text-primary: #1a1a1a;
  --text-secondary: #606060;
  --text-dim: #909090;
}
```

## ベストプラクティス

1. **CSS変数を活用** - 色や値の一元管理で保守性向上
2. **backdrop-filterにフォールバック** - 非対応ブラウザ用に背景色を設定
3. **アニメーションは控えめに** - パフォーマンスとUX考慮
4. **レスポンシブ設計** - モバイルファーストで設計
5. **アクセシビリティ** - 十分なコントラスト比を確保

## トラブルシューティング

### backdrop-filterが効かない

```css
/* Safariプレフィックスを追加 */
.glass {
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}
```

### パフォーマンス問題

```css
/* will-changeで最適化 */
.animated-element {
  will-change: transform, opacity;
  transition: var(--transition-smooth);
}
```

### 透明度が効きすぎる

```css
/* 背景色の透明度を調整 */
:root {
  --glass-bg: rgba(255, 255, 255, 0.08); /* 0.05 → 0.08 */
}
```

## 参考資料

- [実装例: chat-app](../../neko-pm/output/chat-app/) - 本スキルを使用した実装例
- [Glassmorphism CSS Generator](https://hype4.academy/tools/glassmorphism-generator)
- [CSS Gradient Generator](https://cssgradient.io/)
- [Cubic Bezier Generator](https://cubic-bezier.com/)

## 更新履歴

- **2026-01-31**: 初版作成（chat-app UIリニューアルから抽出）

## ライセンス

MIT License - 自由に使用・改変可能
