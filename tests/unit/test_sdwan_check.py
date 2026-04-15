import pytest
from sdwan_analyzer.modules.sdwan_check import (
    check_sdwan_features,
    ping_target,
    detect_multi_default_gateway,
    detect_ipsec_ports,
    detect_real_sdwan_policy_routes
)

from sdwan_analyzer.models.diagnose import SDWANCheckResult


class TestSDWANCheck:
    """测试SD-WAN检查模块"""

    def test_ping_target(self):
        """测试ping_target函数"""
        # 测试空IP
        assert not ping_target("")
        # 测试有效IP（这里使用本地回环地址，应该可通）
        assert ping_target("127.0.0.1")

    def test_detect_multi_default_gateway(self):
        """测试detect_multi_default_gateway函数"""
        # 这个函数会返回实际的网关状态，我们只测试它能正常执行
        result = detect_multi_default_gateway()
        assert isinstance(result, bool)

    def test_detect_ipsec_ports(self):
        """测试detect_ipsec_ports函数"""
        # 测试空IP
        open_flag, ports = detect_ipsec_ports("")
        assert not open_flag
        assert ports == []
        # 测试本地回环地址
        open_flag, ports = detect_ipsec_ports("127.0.0.1")
        assert isinstance(open_flag, bool)
        assert isinstance(ports, list)

    def test_detect_real_sdwan_policy_routes(self):
        """测试detect_real_sdwan_policy_routes函数"""
        # 测试函数能正常执行
        result = detect_real_sdwan_policy_routes()
        assert isinstance(result, bool)

    def test_check_sdwan_features(self):
        """测试check_sdwan_features函数"""
        # 测试空IP
        result = check_sdwan_features("")
        assert isinstance(result, SDWANCheckResult)
        assert result.cpe_ip == ""
        # 测试本地回环地址
        result = check_sdwan_features("127.0.0.1")
        assert isinstance(result, SDWANCheckResult)
        assert result.cpe_ip == "127.0.0.1"
        assert isinstance(result.cpe_reachable, bool)
        assert isinstance(result.is_multi_gateway, bool)
        assert isinstance(result.ipsec_port_open, bool)
        assert isinstance(result.open_ports, list)
        assert isinstance(result.has_policy_route, bool)
        assert isinstance(result.is_likely_sdwan_enabled, bool)
        assert 0 <= result.sdwan_health_score <= 100