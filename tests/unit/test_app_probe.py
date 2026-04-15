import pytest

from sdwan_analyzer.models.diagnose import AppProbeResult
from sdwan_analyzer.modules.app_probe import detect_mtu, http_probe, run_app_probe, tcping


class TestAppProbe:
    """测试应用层探测模块"""

    def test_tcping(self):
        """测试tcping函数"""
        # 测试本地回环地址的80端口
        result = tcping("127.0.0.1", 80)
        assert isinstance(result, bool)

    def test_http_probe(self):
        """测试http_probe函数"""
        # 测试百度网站
        result = http_probe("baidu.com")
        assert isinstance(result, bool)

    def test_detect_mtu(self):
        """测试detect_mtu函数"""
        # 测试本地回环地址
        result = detect_mtu("127.0.0.1")
        assert isinstance(result, int)
        assert 576 <= result <= 1500

    def test_run_app_probe(self):
        """测试run_app_probe函数"""
        # 测试百度网站
        result = run_app_probe("baidu.com")
        assert isinstance(result, AppProbeResult)
        assert result.target == "baidu.com"
        assert result.tcp_port == 443
        assert isinstance(result.tcp_open, bool)
        assert isinstance(result.http_available, bool)
        assert isinstance(result.detected_mtu, int)
        assert isinstance(result.mtu_normal, bool)