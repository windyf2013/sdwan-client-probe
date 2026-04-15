import pytest

from sdwan_analyzer.core.mtr import run_mtr
from sdwan_analyzer.core.ping import ping_check
from sdwan_analyzer.core.tracert import run_tracert
from sdwan_analyzer.models.diagnose import MtrResult, PingResult


class TestCoreModules:
    """测试核心模块"""

    def test_ping_check(self):
        """测试ping_check函数"""
        # 测试本地回环地址
        result = ping_check("127.0.0.1")
        assert isinstance(result, PingResult)
        assert result.target == "127.0.0.1"
        assert result.sent > 0
        assert result.received > 0
        assert result.loss < 100
        assert result.is_success

    def test_run_tracert(self):
        """测试run_tracert函数"""
        # 测试本地回环地址
        result = run_tracert("127.0.0.1")
        assert isinstance(result, MtrResult)
        assert result.target == "127.0.0.1"
        assert isinstance(result.hops, list)
        assert isinstance(result.output, list)

    def test_run_mtr(self):
        """测试run_mtr函数"""
        # 测试本地回环地址
        result = run_mtr("127.0.0.1", count=2)
        assert isinstance(result, MtrResult)
        assert result.target == "127.0.0.1"
        assert isinstance(result.hops, list)
        assert isinstance(result.output, list)