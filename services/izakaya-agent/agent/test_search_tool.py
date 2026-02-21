#!/usr/bin/env python3
"""
search_restaurants ツールの直接実行テスト
ホットペッパー API と Google Places API のどちらが失敗しているか特定
"""
import sys
import os

# agent ディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.search_restaurants import search_restaurants

def main():
    print("=" * 60)
    print("search_restaurants ツール直接実行テスト")
    print("=" * 60)

    # 渋谷の座標でテスト
    print("\n📍 テスト条件:")
    print("  - 座標: 渋谷 (35.6595, 139.7004)")
    print("  - 半径: 500m")
    print("  - 件数: 10件")

    try:
        print("\n🔍 search_restaurants 実行中...")
        result = search_restaurants(
            lat=35.6595,
            lon=139.7004,
            radius=500,
            limit=10
        )

        print("\n✅ 実行結果:")
        print(f"  - 結果型: {type(result)}")
        print(f"  - 結果長: {len(result) if isinstance(result, list) else 'N/A'}")
        print(f"  - 内容:\n{result}")

    except Exception as e:
        print(f"\n❌ エラー発生:")
        print(f"  - エラー型: {type(e).__name__}")
        print(f"  - エラーメッセージ: {e}")
        import traceback
        print(f"\n🔍 スタックトレース:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
