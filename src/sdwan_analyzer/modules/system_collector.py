# modules/system_collector.py
import subprocess
import re
import winreg
from typing import List, Optional
from sdwan_analyzer.models.diagnose import NetworkInterface, SystemEnvironmentResult, Issue
from sdwan_analyzer.modules.route_check import check_gateway_reachable
from sdwan_analyzer.modules.dns_check import check_dns_working

def _run_cmd(cmd: list) -> str:
    """执行命令并返回输出，兼容 GBK/UTF-8"""
    try:
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=10)
        try:
            return out.decode('gbk')
        except UnicodeDecodeError:
            return out.decode('utf-8', errors='ignore')
    except Exception:
        return ""

def collect_system_environment() -> SystemEnvironmentResult:
    result = SystemEnvironmentResult()
    issues = []

    # 1. 一次性获取 ipconfig /all
    ipconfig_out = _run_cmd(["ipconfig", "/all"])
    if not ipconfig_out:
        issues.append(Issue(level="error", category="System", message="无法获取网络配置信息 (ipconfig 执行失败)"))
        result.config_score -= 30
        result.issues = issues
        return result

    # 2. 解析网卡信息 (复用并适配 local_net_config 的逻辑)
    result.interfaces = _parse_ipconfig_to_new_model(ipconfig_out)
    
    # 3. 识别主网卡
    result.primary_interface = _identify_primary_nic(result.interfaces)
    
    if not result.primary_interface:
        issues.append(Issue(level="error", category="Config", message="未找到有效的主网络适配器"))
        result.config_score -= 30
    else:
        # 4. 基于主网卡的静态配置检查
        if not result.primary_interface.ip_addresses:
            issues.append(Issue(level="error", category="Config", message="主网卡无 IPv4 地址"))
            result.config_score -= 20
            
        if not result.primary_interface.gateways:
            issues.append(Issue(level="error", category="Config", message="主网卡无默认网关"))
            result.config_score -= 20
        elif len(set(gw for nic in result.interfaces for gw in nic.gateways)) > 1:
            result.has_multiple_gateways = True
            issues.append(Issue(level="warning", category="Config", message="检测到多个活跃网关，可能存在路由冲突"))
            result.config_score -= 10

        if not result.primary_interface.dns_servers:
            issues.append(Issue(level="error", category="Config", message="主网卡未配置 DNS"))
            result.config_score -= 15

    # 5. 代理检测 (注册表)
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        val, _ = winreg.QueryValueEx(key, "ProxyEnable")
        result.proxy_enabled = bool(val)
        if result.proxy_enabled:
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
            result.proxy_server = server
            issues.append(Issue(level="warning", category="Config", message=f"系统代理已开启: {server}"))
            result.config_score -= 10
        winreg.CloseKey(key)
    except: pass

    # 6. 防火墙检测
    fw_out = _run_cmd(["netsh", "advfirewall", "show", "allprofiles", "state"])
    result.firewall_enabled = "ON" in fw_out.upper()

    # 7. 动态连通性检测 (仅在配置基本正常时执行，加速失败场景)
    if result.primary_interface and result.primary_interface.gateways:
        gw = result.primary_interface.gateways[0]
        
        # 检查默认路由存在性
        route_out = _run_cmd(["route", "print", "0.0.0.0"])
        result.default_route_exists = "0.0.0.0" in route_out
        
        if result.default_route_exists:
            # Ping 网关
            result.gateway_reachable = check_gateway_reachable(gw)
            if not result.gateway_reachable:
                issues.append(Issue(level="error", category="Connectivity", message=f"网关 {gw} 不可达"))
                result.config_score -= 20
        
        # DNS 解析测试
        result.dns_resolution_working = check_dns_working()
        if not result.dns_resolution_working:
            issues.append(Issue(level="error", category="Connectivity", message="DNS 解析失败"))
            result.config_score -= 20

    result.issues = issues
    result.config_score = max(0, result.config_score)
    return result

def _parse_ipconfig_to_new_model(output: str) -> List[NetworkInterface]:
    """
    解析 ipconfig /all 输出，返回新的 NetworkInterface 列表
    逻辑源自 local_net_config.py get_network_adapters，但映射到新模型
    返回所有适配器，包括未启用的
    """
    nics = []
    if not output:
        return nics

    lines = output.splitlines()
    current_nic = None

    for idx, line in enumerate(lines):
        stripped_line = line.strip()
        
        # 1. 识别新网卡开始
        if ("适配器" in stripped_line or "adapter" in stripped_line.lower()) and stripped_line.endswith(":"):
            if current_nic:
                nics.append(current_nic)
            
            # 提取名称
            name_part = stripped_line[:-1].strip()
            for prefix in ["以太网适配器", "无线局域网适配器", "Ethernet adapter", "Wireless LAN adapter"]:
                if name_part.startswith(prefix):
                    name_part = name_part[len(prefix):].strip()
            
            # 初始化新模型
            current_nic = NetworkInterface(
                name=name_part,
                description=name_part,
                mac_address="",
                ip_addresses=[],
                subnet_masks=[], # <--- 初始化子网掩码列表
                gateways=[],
                dns_servers=[],
                is_dhcp=False,
                status="Connected" 
            )
            continue
        
        if not current_nic:
            continue

        # 2. 解析属性
        
        # 媒体状态
        if "媒体状态" in stripped_line or "Media State" in stripped_line:
            if "已断开" in stripped_line or "disconnected" in stripped_line.lower():
                current_nic.status = "Disconnected"
            else:
                current_nic.status = "Connected"

        # DHCP
        if "DHCP" in stripped_line and ("是" in stripped_line or "Yes" in stripped_line):
            current_nic.is_dhcp = True

        # 物理地址 (MAC)
        if "物理地址" in stripped_line or "Physical Address" in stripped_line:
            match = re.search(r'([0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2})', stripped_line)
            if match:
                current_nic.mac_address = match.group(1)

        # IPv4 地址
        if "IPv4 地址" in stripped_line or "IPv4 Address" in stripped_line:
            ips = re.findall(r'(\d+\.\d+\.\d+\.\d+)', stripped_line)
            current_nic.ip_addresses.extend(ips)

        # 【新增】子网掩码
        if "子网掩码" in stripped_line or "Subnet Mask" in stripped_line:
            masks = re.findall(r'(\d+\.\d+\.\d+\.\d+)', stripped_line)
            current_nic.subnet_masks.extend(masks)

        # 默认网关 (支持换行)
        if "默认网关" in stripped_line or "Default Gateway" in stripped_line:
            gws = re.findall(r'(\d+\.\d+\.\d+\.\d+)', stripped_line)
            current_nic.gateways.extend(gws)
            for i in [1, 2]:
                if idx + i < len(lines):
                    next_line = lines[idx + i].strip()
                    if not next_line or "DNS" in next_line or "IPv4" in next_line:
                        break
                    next_gws = re.findall(r'(\d+\.\d+\.\d+\.\d+)', next_line)
                    current_nic.gateways.extend(next_gws)

        # DNS 服务器 (支持换行)
        if "DNS 服务器" in stripped_line or "DNS Servers" in stripped_line:
            dns_ips = re.findall(r'(\d+\.\d+\.\d+\.\d+)', stripped_line)
            current_nic.dns_servers.extend(dns_ips)
            for i in [1, 2]:
                if idx + i < len(lines):
                    next_line = lines[idx + i].strip()
                    if not next_line or "IPv4" in next_line or "网关" in next_line or "Gateway" in next_line:
                        break
                    next_dns = re.findall(r'(\d+\.\d+\.\d+\.\d+)', next_line)
                    current_nic.dns_servers.extend(next_dns)

    if current_nic:
        nics.append(current_nic)
    
    # 返回所有适配器，包括未启用的
    return nics

def _get_all_network_interfaces() -> List[NetworkInterface]:
    """获取所有网络接口，包括未启用的"""
    ipconfig_out = _run_cmd(["ipconfig", "/all"])
    if not ipconfig_out:
        return []
    return _parse_ipconfig_to_new_model(ipconfig_out)

def _get_active_network_interfaces() -> List[NetworkInterface]:
    """获取活跃的网络接口（排除 Disconnected 状态）"""
    all_nics = _get_all_network_interfaces()
    # 过滤：只保留有 MAC 或 IP 且状态非断开的网卡
    valid_nics = [
        nic for nic in all_nics 
        if (nic.ip_addresses or nic.mac_address) and nic.status != "Disconnected"
    ]
    return valid_nics

def _identify_primary_nic(nics: List[NetworkInterface]) -> Optional[NetworkInterface]:
    """
    识别主网卡逻辑，源自 local_net_config.py
    """
    if not nics:
        return None

    # 1. 筛选有网关的网卡
    candidates_with_gw = [nic for nic in nics if nic.gateways]
    
    # 2. 如果没有网关，筛选有 IP 的
    candidates = candidates_with_gw if candidates_with_gw else [nic for nic in nics if nic.ip_addresses]
    
    if not candidates:
        return None
    
    # 3. 排除虚拟网卡
    virtual_keywords = ['vmware', 'virtualbox', 'veth', 'docker', 'bluetooth', 'loopback', 'hyper-v', 'vpn']
    physical_candidates = [
        nic for nic in candidates 
        if not any(kw in nic.description.lower() or kw in nic.name.lower() for kw in virtual_keywords)
    ]
    
    # 4. 返回最佳候选
    if physical_candidates:
        return physical_candidates[0]
    else:
        return candidates[0]