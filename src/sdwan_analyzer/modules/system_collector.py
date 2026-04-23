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

def _parse_ipconfig_to_new_model(ipconfig_out: str) -> List[NetworkInterface]:
    """
    解析 ipconfig /all 输出，提取所有网卡信息（包括未连接/禁用的）
    """
    interfaces = []
    # 使用正则分割不同的适配器块
    # 注意：ipconfig 输出中，适配器之间通常由空行或新的 "Adapter" 标题分隔
    blocks = re.split(r'\n\s*\n', ipconfig_out)
    
    for block in blocks:
        if not block.strip():
            continue
            
        # 提取适配器名称 (例如: Ethernet adapter Ethernet0:)
        name_match = re.search(r'^(.*?adapter\s+(.+?)):', block, re.IGNORECASE | re.MULTILINE)
        if not name_match:
            continue
            
        full_header = name_match.group(1)
        nic_name = name_match.group(2).strip()
        
        # 初始化当前网卡对象
        current_nic = NetworkInterface(
            name=nic_name,
            description="",
            mac_address="",
            ip_addresses=[],
            subnet_masks=[], # 初始化
            gateways=[],
            dns_servers=[],
            is_dhcp=False,
            status="Unknown"
        )
        
        # 1. 提取描述 (Description)
        desc_match = re.search(r'Description\.?\.?\s*:\s*(.+)', block)
        if desc_match:
            current_nic.description = desc_match.group(1).strip()
            
        # 2. 提取物理地址 (MAC)
        mac_match = re.search(r'Physical Address\.?\.?\s*:\s*(.+)', block)
        if mac_match:
            current_nic.mac_address = mac_match.group(1).strip()
            
        # 3. 提取 DHCP 状态
        dhcp_match = re.search(r'DHCP Enabled\.?\.?\s*:\s*(.+)', block)
        if dhcp_match:
            current_nic.is_dhcp = "yes" in dhcp_match.group(1).lower()
            
        # 4. 提取 IP 地址 和 子网掩码 (可能有多组 IPv4/IPv6)
        # 匹配模式： IPv4 Address . . . . . . . . . . . : 192.168.1.100
        #           Subnet Mask . . . . . . . . . . . : 255.255.255.0
        lines = block.split('\n')
        temp_ips = []
        temp_masks = []
        
        for line in lines:
            # 匹配 IP
            ip_match = re.search(r'(?:IPv4|IP) Address\.?\.?\s*:\s*(.+?)(?:\(Preferred\)|\(Duplicate\))?', line)
            if ip_match:
                temp_ips.append(ip_match.group(1).strip())
            
            # 匹配子网掩码 (通常在 IP 下方附近，或者同一块中)
            mask_match = re.search(r'Subnet Mask\.?\.?\s*:\s*(.+)', line)
            if mask_match:
                temp_masks.append(mask_match.group(1).strip())
                
        # 简单对齐：如果 IP 和 Mask 数量一致，则一一对应；否则只保留 IP
        if len(temp_ips) == len(temp_masks):
            current_nic.ip_addresses = temp_ips
            current_nic.subnet_masks = temp_masks
        else:
            current_nic.ip_addresses = temp_ips
            # 如果数量不匹配，尝试填充或留空，这里保守处理，只保留解析到的
            current_nic.subnet_masks = temp_masks if temp_masks else [""] * len(temp_ips)

        # 5. 提取默认网关
        gw_matches = re.findall(r'Default Gateway\.?\.?\s*:\s*(.+)', block)
        for gw in gw_matches:
            gw_val = gw.strip()
            if gw_val and gw_val != "0.0.0.0":
                current_nic.gateways.append(gw_val)
                
        # 6. 提取 DNS
        dns_matches = re.findall(r'DNS Servers\.?\.?\s*:\s*(.+)', block)
        current_nic.dns_servers = [d.strip() for d in dns_matches if d.strip()]
        
        # 7. 判断状态 (Connected / Disconnected / Media Disconnected)
        if "Media disconnected" in block:
            current_nic.status = "Media disconnected"
        elif "Connection-specific DNS Suffix" in block or current_nic.ip_addresses:
            # 如果有 IP 或特定后缀，通常意味着已连接
            current_nic.status = "Connected"
        else:
            # 检查是否有 "Status" 字段 (某些版本 ipconfig 有)
            status_match = re.search(r'Media State\.?\.?\s*:\s*(.+)', block)
            if status_match:
                state = status_match.group(1).strip()
                if "disconnected" in state.lower():
                    current_nic.status = "Disconnected"
                else:
                    current_nic.status = "Connected" # 假设其他状态为连接
            else:
                # 如果没有明确断开标志，且有 IP，视为连接
                current_nic.status = "Connected" if current_nic.ip_addresses else "Disconnected"

        interfaces.append(current_nic)
        
    return interfaces

def _is_relevant_interface(name: str, description: str) -> bool:
    """
    判断网卡是否属于需要展示的类型：以太网、WLAN、VPN。
    """
    combined_text = f"{name} {description}".lower()
    include_keywords = [
        'ethernet', 'pci', 'gbe', 'family', 'controller',
        'wireless', 'wi-fi', 'wlan', '802.11',
        'vpn', 'tunnel', 'ppp', 'l2tp', 'tap-windows', 'wintun', 'zerotier'
    ]
    exclude_keywords = [
        'bluetooth', 'bt', '个人区域网',
        'loopback', 'microsoft loopback',
        'teredo', 'isatap', '6to4',
        'vmware network adapter vmnet', 'virtualbox host-only',
        'hyper-v', 'vswitch'
    ]

    for kw in exclude_keywords:
        if kw in combined_text:
            return False
    for kw in include_keywords:
        if kw in combined_text:
            return True
    return False

def _identify_primary_nic(interfaces: List[NetworkInterface]) -> Optional[NetworkInterface]:
    """
    识别主网卡：优先选择状态为 Connected 且有默认网关的以太网/WLAN 网卡
    """
    # 1. 优先找 Connected 且有 Gateway 的
    connected_with_gw = [
        nic for nic in interfaces 
        if nic.status == "Connected" and nic.gateways and _is_relevant_interface(nic.name, nic.description)
    ]
    if connected_with_gw:
        # 简单策略：返回第一个，或者可以根据 Metric 排序
        return connected_with_gw[0]
        
    # 2. 其次找 Connected 的
    connected = [
        nic for nic in interfaces 
        if nic.status == "Connected" and _is_relevant_interface(nic.name, nic.description)
    ]
    if connected:
        return connected[0]
        
    # 3. 最后兜底：返回第一个相关网卡
    relevant = [nic for nic in interfaces if _is_relevant_interface(nic.name, nic.description)]
    if relevant:
        return relevant[0]
        
    return None

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

    # 2. 解析所有网卡
    all_parsed_interfaces = _parse_ipconfig_to_new_model(ipconfig_out)
    
    # 3. 【关键修改】不再在这里过滤 interfaces，而是保留所有解析到的网卡
    # 这样前端可以显示“未启用”或“未连接”的网卡
    result.interfaces = all_parsed_interfaces
    
    # 4. 识别主网卡 (内部会使用 _is_relevant_interface 进行优选)
    result.primary_interface = _identify_primary_nic(all_parsed_interfaces)
    
    if not result.primary_interface:
        issues.append(Issue(level="error", category="Config", message="未找到有效的主网络适配器"))
        result.config_score -= 30
    else:
        # 标记主网卡
        for nic in result.interfaces:
            if nic.name == result.primary_interface.name:
                nic.is_primary = True
                break

        # 静态配置检查
        if not result.primary_interface.ip_addresses:
            issues.append(Issue(level="error", category="Config", message=f"主网卡 '{result.primary_interface.name}' 无 IPv4 地址"))
            result.config_score -= 20
            
        if not result.primary_interface.gateways:
            issues.append(Issue(level="error", category="Config", message="主网卡无默认网关"))
            result.config_score -= 20
            
        # 多网关检查 (仅针对已连接且有网关的网卡)
        active_gateways = set()
        for nic in result.interfaces:
            if nic.status == "Connected" and nic.gateways:
                for gw in nic.gateways:
                    active_gateways.add(gw)
        
        if len(active_gateways) > 1:
            result.has_multiple_gateways = True
            issues.append(Issue(level="warning", category="Config", message="检测到多个活跃网关，可能存在路由冲突"))
            result.config_score -= 10

        if not result.primary_interface.dns_servers:
            issues.append(Issue(level="error", category="Config", message="主网卡未配置 DNS"))
            result.config_score -= 15

    # 6. 代理检测 (注册表)
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