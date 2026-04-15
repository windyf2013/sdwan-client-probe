import pytest

from sdwan_analyzer.models.diagnose import SystemDiagnoseResult
from sdwan_analyzer.modules.system_diagnose import run_system_diagnose


class TestSystemDiagnose:
    """测试系统诊断模块"""

    def test_run_system_diagnose(self):
        """测试run_system_diagnose函数"""
        # 测试函数能正常执行
        result = run_system_diagnose()
        assert isinstance(result, SystemDiagnoseResult)
        # 检查返回结果的属性
        assert hasattr(result, 'nic')
        assert hasattr(result, 'default_route_valid')
        assert hasattr(result, 'gateway_reachable')
        assert hasattr(result, 'dns_working')
        assert hasattr(result, 'firewall_enabled')
        assert hasattr(result, 'all_ok')
        # 检查属性类型
        assert isinstance(result.default_route_valid, bool)
        assert isinstance(result.gateway_reachable, bool)
        assert isinstance(result.dns_working, bool)
        assert isinstance(result.firewall_enabled, bool)
        assert isinstance(result.all_ok, bool)