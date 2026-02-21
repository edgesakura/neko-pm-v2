"""
Unit tests for agents/diagnostic/tools/ 各ツール
_clamp_duration / _clamp_limit の境界値テスト、メトリクスツールの正常系確認。
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../agents/diagnostic"))

# strands の @tool デコレータを mock してからインポート
_mock_tool = MagicMock(side_effect=lambda fn: fn)
with patch.dict("sys.modules", {"strands": MagicMock(tool=_mock_tool)}):
    from agents.diagnostic.tools.query_metrics import (
        _clamp_duration,
        query_cpu_metrics,
        query_memory_metrics,
        query_disk_metrics,
        query_network_metrics,
        query_latency_metrics,
    )
    from agents.diagnostic.tools.query_logs import _clamp_limit


class TestClampDuration(unittest.TestCase):
    """_clamp_duration の境界値テスト"""

    def test_normal_value(self):
        """正常値はそのまま返ること"""
        self.assertEqual(_clamp_duration(30), 30)

    def test_minimum_boundary(self):
        """1 はそのまま返ること"""
        self.assertEqual(_clamp_duration(1), 1)

    def test_maximum_boundary(self):
        """1440 はそのまま返ること"""
        self.assertEqual(_clamp_duration(1440), 1440)

    def test_below_minimum_clamped_to_1(self):
        """0 は 1 にクランプされること"""
        self.assertEqual(_clamp_duration(0), 1)

    def test_negative_clamped_to_1(self):
        """負数は 1 にクランプされること"""
        self.assertEqual(_clamp_duration(-10), 1)

    def test_above_maximum_clamped_to_1440(self):
        """1441 は 1440 にクランプされること"""
        self.assertEqual(_clamp_duration(1441), 1440)

    def test_large_value_clamped(self):
        """非常に大きい値は 1440 にクランプされること"""
        self.assertEqual(_clamp_duration(99999), 1440)


class TestClampLimit(unittest.TestCase):
    """_clamp_limit の境界値テスト"""

    def test_normal_value(self):
        """正常値はそのまま返ること"""
        self.assertEqual(_clamp_limit(20), 20)

    def test_minimum_boundary(self):
        """1 はそのまま返ること"""
        self.assertEqual(_clamp_limit(1), 1)

    def test_maximum_boundary(self):
        """1000 はそのまま返ること"""
        self.assertEqual(_clamp_limit(1000), 1000)

    def test_below_minimum_clamped_to_1(self):
        """0 は 1 にクランプされること"""
        self.assertEqual(_clamp_limit(0), 1)

    def test_negative_clamped_to_1(self):
        """負数は 1 にクランプされること"""
        self.assertEqual(_clamp_limit(-5), 1)

    def test_above_maximum_clamped_to_1000(self):
        """1001 は 1000 にクランプされること"""
        self.assertEqual(_clamp_limit(1001), 1000)


class TestQueryCpuMetrics(unittest.TestCase):
    """query_cpu_metrics の正常系テスト"""

    def test_returns_required_fields(self):
        """必須フィールドが全て含まれること"""
        result = query_cpu_metrics("test-service", 5)
        self.assertEqual(result["service"], "test-service")
        self.assertEqual(result["metric"], "cpu.utilization")
        self.assertEqual(result["unit"], "percent")
        self.assertEqual(result["duration_minutes"], 5)
        self.assertIn("data_points", result)
        self.assertIn("summary", result)
        self.assertIn("source", result)

    def test_data_points_count(self):
        """data_points の数が duration_minutes + 1 であること"""
        result = query_cpu_metrics("svc", 10)
        self.assertEqual(len(result["data_points"]), 11)

    def test_summary_contains_stats(self):
        """summary に avg/max/min/current が含まれること"""
        result = query_cpu_metrics("svc", 5)
        summary = result["summary"]
        for key in ("avg", "max", "min", "current"):
            self.assertIn(key, summary)

    def test_values_in_valid_range(self):
        """CPU 値が 0-100% の範囲内であること"""
        result = query_cpu_metrics("svc", 5)
        for dp in result["data_points"]:
            self.assertGreaterEqual(dp["value"], 0.0)
            self.assertLessEqual(dp["value"], 100.0)

    def test_clamped_duration(self):
        """0 分指定時にクランプされて 1 分で実行されること"""
        result = query_cpu_metrics("svc", 0)
        self.assertEqual(result["duration_minutes"], 1)


class TestQueryMemoryMetrics(unittest.TestCase):
    """query_memory_metrics の正常系テスト"""

    def test_returns_required_fields(self):
        """必須フィールドが含まれること"""
        result = query_memory_metrics("test-service", 5)
        self.assertEqual(result["service"], "test-service")
        self.assertEqual(result["metric"], "memory.utilization")
        self.assertIn("memory_limit_mib", result)
        self.assertIn("trend", result)

    def test_data_points_contain_mib(self):
        """data_points に value_mib が含まれること"""
        result = query_memory_metrics("svc", 3)
        for dp in result["data_points"]:
            self.assertIn("value_mib", dp)


class TestQueryDiskMetrics(unittest.TestCase):
    """query_disk_metrics の正常系テスト"""

    def test_returns_required_fields(self):
        """必須フィールドが含まれること"""
        result = query_disk_metrics("test-service", 5)
        self.assertEqual(result["metric"], "disk.io")
        self.assertIn("disk_usage_percent", result)

    def test_data_points_contain_io_fields(self):
        """data_points に read_mbps/write_mbps が含まれること"""
        result = query_disk_metrics("svc", 3)
        for dp in result["data_points"]:
            self.assertIn("read_mbps", dp)
            self.assertIn("write_mbps", dp)
            self.assertIn("read_iops", dp)
            self.assertIn("write_iops", dp)


class TestQueryNetworkMetrics(unittest.TestCase):
    """query_network_metrics の正常系テスト"""

    def test_returns_required_fields(self):
        """必須フィールドが含まれること"""
        result = query_network_metrics("test-service", 5)
        self.assertEqual(result["metric"], "network.throughput")

    def test_data_points_contain_network_fields(self):
        """data_points にネットワークフィールドが含まれること"""
        result = query_network_metrics("svc", 3)
        for dp in result["data_points"]:
            self.assertIn("bytes_in_mbps", dp)
            self.assertIn("bytes_out_mbps", dp)
            self.assertIn("tcp_errors", dp)
            self.assertIn("active_connections", dp)


class TestQueryLatencyMetrics(unittest.TestCase):
    """query_latency_metrics の正常系テスト"""

    def test_default_percentiles(self):
        """デフォルトで p50/p95/p99 が含まれること"""
        result = query_latency_metrics("svc", 5)
        self.assertEqual(result["percentiles"], ["p50", "p95", "p99"])

    def test_custom_percentiles(self):
        """指定パーセンタイルのみ含まれること"""
        result = query_latency_metrics("svc", 5, percentiles=["p95", "p99"])
        self.assertEqual(result["percentiles"], ["p95", "p99"])
        for dp in result["data_points"]:
            self.assertIn("p95_ms", dp)
            self.assertIn("p99_ms", dp)
            self.assertNotIn("p50_ms", dp)

    def test_slo_status_present(self):
        """SLO ステータスが含まれること"""
        result = query_latency_metrics("svc", 5)
        self.assertIn("slo", result)
        self.assertIn("status", result["slo"])
        self.assertIn(result["slo"]["status"], ["OK", "BREACHING"])

    def test_summary_contains_current_and_max(self):
        """summary に current/max が含まれること"""
        result = query_latency_metrics("svc", 5)
        self.assertIn("current", result["summary"])
        self.assertIn("max", result["summary"])


if __name__ == "__main__":
    unittest.main()
