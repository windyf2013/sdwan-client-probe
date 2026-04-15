# d:/AI/testing/proj5/sdwan_analyzer/src/sdwan_analyzer/modules/system_diagnose.py

from sdwan_analyzer.models.diagnose import SystemDiagnoseResult
from sdwan_analyzer.modules.dns_check import check_dns_working
from sdwan_analyzer.modules.firewall_check import check_windows_firewall
from sdwan_analyzer.modules.nic_info import get_main_nic_info
from sdwan_analyzer.modules.proxy_check import check_windows_proxy
from sdwan_analyzer.modules.route_check import (
    check_default_route,
    check_gateway_reachable,
)
from sdwan_analyzer.utils.logger import get_logger

logger = get_logger('system_diagnose')

def run_system_diagnose() -> SystemDiagnoseResult:
    """执行完整系统层诊断"""
    logger.info("开始系统层诊断")
    res = SystemDiagnoseResult()

    # 1. 网卡
    res.nic = get_main_nic_info()
    
    # 2. 默认路由
    res.default_route_valid = check_default_route()

    # 3. 网关连通性
    gw = res.nic.gateway[0] if res.nic and res.nic.gateway else ""
    res.gateway_reachable = check_gateway_reachable(gw)

    # 4. DNS
    res.dns_working = check_dns_working()

    # 5. 防火墙
    res.firewall_enabled = check_windows_firewall()

    # 6. 系统代理 (修复：提取布尔值)
    try:
        proxy_info = check_windows_proxy()
        res.proxy_enabled = proxy_info.get('enabled', False)
        res.proxy_server = proxy_info.get('server', '')
    except Exception as e:
        logger.warning(f"代理检测异常: {e}")
        res.proxy_enabled = False

    # 7. 整体健康
    # 注意：代理开启通常不算“不健康”，但算“有风险”。这里暂不把代理作为 all_ok 的否决项，
    # 除非你们策略规定代理开启即为环境不合格。
    res.all_ok = all([
        res.nic is not None,
        res.default_route_valid,
        res.gateway_reachable,
        res.dns_working
    ])
    
    logger.info(f"系统诊断完成: all_ok={res.all_ok}")
    return res