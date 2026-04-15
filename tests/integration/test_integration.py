import pytest

from sdwan_analyzer.core.mtr import run_mtr
from sdwan_analyzer.core.ping import ping_check
from sdwan_analyzer.core.tracert import run_tracert
from sdwan_analyzer.modules.app_probe import run_app_probe
from sdwan_analyzer.modules.sdwan_check import check_sdwan_features
from sdwan_analyzer.modules.system_diagnose import run_system_diagnose


class TestIntegration:
    """集成测试"""

    def test_full_diagnosis_flow(self):
        """测试完整的诊断流程"""
        # 1. 系统层诊断
        sys_res = run_system_diagnose()
        assert sys_res is not None
        
        # 2. SD-WAN特征识别
        gw_ip = ""
        if sys_res and sys_res.nic and sys_res.nic.gateway:
            gw_ip = sys_res.nic.gateway[0]
        
        sdwan_result = check_sdwan_features(gw_ip)
        assert sdwan_result is not None
        
        # 3. 业务目标检测
        targets = ["baidu.com", "127.0.0.1"]
        for target in targets:
            # Ping测试
            ping_result = ping_check(target)
            assert ping_result is not None
            
            # Traceroute测试
            tracert_result = run_tracert(target)
            assert tracert_result is not None
            
            # MTR测试
            mtr_result = run_mtr(target, count=2)
            assert mtr_result is not None
            
            # 应用层探测
            app_result = run_app_probe(target)
            assert app_result is not None