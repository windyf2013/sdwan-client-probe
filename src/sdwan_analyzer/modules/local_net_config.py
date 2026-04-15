# sdwan_analyzer/modules/local_net_config.py
"""本地网络配置检测模块 - 聚焦主网卡与环境配置合理性"""

import subprocess
import re
import winreg
from typing import List, Optional
from sdwan_analyzer.models.diagnose import LocalConfigCheckResult, NicDetail

def _run_cmd(cmd: list[str]) -> str:
    """执行命令并返回输出"""
    try:
        # 确保使用 GBK 解码，因为 ipconfig 在中文 Windows 下输出 GBK
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=10)
        try:
            return output.decode('gbk')
        except UnicodeDecodeError:
            return output.decode('utf-8', errors='ignore')
    except Exception:
        return ""

def get_network_adapters() -> List[NicDetail]:
    """
    使用稳健的逐行解析法获取所有网络适配器
    参考 nic_info.py 的实现，确保与系统层检测的一致性
    """
    nics = []
    output = _run_cmd(["ipconfig", "/all"])
    if not output:
        return nics

    lines = output.splitlines()
    current_nic = None

    for idx, line in enumerate(lines):
        stripped_line = line.strip()
        
        # 1. 识别新网卡开始
        # 匹配类似 "以太网适配器 Ethernet:" 或 "Wireless LAN adapter Wi-Fi:"
        if ("适配器" in stripped_line or "adapter" in stripped_line.lower()) and stripped_line.endswith(":"):
            if current_nic:
                nics.append(current_nic)
            
            # 提取名称
            name_part = stripped_line[:-1].strip() # 去掉冒号
            # 清理常见前缀，保留具体名称
            for prefix in ["以太网适配器", "无线局域网适配器", "Ethernet adapter", "Wireless LAN adapter"]:
                if name_part.startswith(prefix):
                    name_part = name_part[len(prefix):].strip()
            
            current_nic = NicDetail(
                name=name_part,
                description=name_part,
                status="Up" # 默认假设出现即存在，后续可通过媒体状态判断
            )
            continue
        
        if not current_nic:
            continue

        # 2. 解析当前网卡的属性
        # 注意：ipconfig 的属性通常在下一行缩进，或者在同一行
        
        # 媒体状态 (判断是否断开)
        if "媒体状态" in stripped_line or "Media State" in stripped_line:
            if "已断开" in stripped_line or "disconnected" in stripped_line.lower():
                current_nic.status = "Disconnected"
            else:
                current_nic.status = "Connected"

        # 物理地址 (MAC)
        if "物理地址" in stripped_line or "Physical Address" in stripped_line:
            match = re.search(r'([0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2})', stripped_line)
            if match:
                current_nic.mac_address = match.group(1)

        # IPv4 地址
        if "IPv4 地址" in stripped_line or "IPv4 Address" in stripped_line:
            ips = re.findall(r'(\d+\.\d+\.\d+\.\d+)', stripped_line)
            current_nic.ip_addresses.extend(ips)

        # 默认网关 (支持换行情况)
        if "默认网关" in stripped_line or "Default Gateway" in stripped_line:
            # 先取当前行
            gws = re.findall(r'(\d+\.\d+\.\d+\.\d+)', stripped_line)
            current_nic.gateways.extend(gws)
            # 兼容网关在下一行的情况 (常见于中文 Windows)
            for i in [1, 2]:
                if idx + i < len(lines):
                    next_line = lines[idx + i].strip()
                    # 如果下一行是空行或新的属性头，停止
                    if not next_line or "DNS" in next_line or "IPv4" in next_line:
                        break
                    # 提取 IP
                    next_gws = re.findall(r'(\d+\.\d+\.\d+\.\d+)', next_line)
                    current_nic.gateways.extend(next_gws)

        # DNS 服务器 (支持换行情况)
        if "DNS 服务器" in stripped_line or "DNS Servers" in stripped_line:
            # 先取当前行
            dns_ips = re.findall(r'(\d+\.\d+\.\d+\.\d+)', stripped_line)
            current_nic.dns_servers.extend(dns_ips)
            # 兼容 DNS 在下一行的情况
            for i in [1, 2]:
                if idx + i < len(lines):
                    next_line = lines[idx + i].strip()
                    # 如果遇到空行或新的属性头，停止
                    if not next_line or "IPv4" in next_line or "网关" in next_line or "Gateway" in next_line:
                        break
                    next_dns = re.findall(r'(\d+\.\d+\.\d+\.\d+)', next_line)
                    current_nic.dns_servers.extend(next_dns)

    # 添加最后一个网卡
    if current_nic:
        nics.append(current_nic)

    # 过滤：只保留有 MAC 地址或 IP 地址的有效网卡，且状态不是明确断开的
    valid_nics = [
        nic for nic in nics 
        if (nic.ip_addresses or nic.mac_address) and nic.status != "Disconnected"
    ]
    
    return valid_nics

def identify_primary_nic(nics: List[NicDetail]) -> Optional[NicDetail]:
    """
    识别主网卡：
    1. 优先选择有默认网关的网卡
    2. 其次选择有 IP 的网卡
    3. 排除虚拟网卡
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
        # 如果全是虚拟网卡，也返回第一个，总比没有好
        return candidates[0]

def run_local_net_config_check() -> LocalConfigCheckResult:
    """执行完整的本地网络配置检测"""
    result = LocalConfigCheckResult()
    
    # 1. 网卡识别
    result.all_nics = get_network_adapters()
    result.primary_nic = identify_primary_nic(result.all_nics)
    
    if not result.primary_nic:
        result.issues.append({
            "level": "error",
            "category": "system",
            "message": "未找到活跃的主网络适配器",
            "detail": "请检查网线或 Wi-Fi 连接",
            "suggestion": "确保至少有一个网卡处于连接状态并获取了 IP"
        })
        result.config_score -= 25

    # 2. 代理检测
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        result.proxy_enabled = bool(proxy_enable)
        if result.proxy_enabled:
            try:
                server, _ = winreg.QueryValueEx(key, "ProxyServer")
                result.issues.append({
                    "level": "warning", 
                    "category": "proxy", 
                    "message": "系统代理已开启", 
                    "detail": server, 
                    "suggestion": "建议关闭代理测试"
                })
                result.config_score -= 10
            except: pass
        winreg.CloseKey(key)
    except: pass

    # 3. 防火墙检测
    try:
        out = _run_cmd(["netsh", "advfirewall", "show", "allprofiles", "state"])
        if "ON" in out.upper():
            result.firewall_enabled = True
    except: pass

    # 4. 路由检测 (多网关)
    gateways = []
    for nic in result.all_nics:
        gateways.extend(nic.gateways)
    unique_gws = list(set(gateways))
    
    if len(unique_gws) > 1:
        result.has_multiple_gateways = True
        result.issues.append({
            "level": "warning", 
            "category": "route", 
            "message": "检测到多个活跃网关", 
            "detail": str(unique_gws), 
            "suggestion": "可能导致路由冲突"
        })
        result.config_score -= 10
    elif len(unique_gws) == 0 and result.primary_nic:
        result.issues.append({
            "level": "error", 
            "category": "route", 
            "message": "无默认网关", 
            "detail": "", 
            "suggestion": "检查网络连接"
        })
        result.config_score -= 25

    # 5. DNS 检测
    if result.primary_nic:
        if not result.primary_nic.dns_servers:
            result.dns_config_reasonable = False
            result.issues.append({
                "level": "error", 
                "category": "dns", 
                "message": "主网卡无 DNS", 
                "detail": result.primary_nic.name, 
                "suggestion": "配置 DNS"
            })
            result.config_score -= 25
        else:
            bad_dns = [d for d in result.primary_nic.dns_servers if d.startswith('169.254.') or d == '0.0.0.0']
            if bad_dns:
                result.dns_config_reasonable = False
                result.issues.append({
                    "level": "warning", 
                    "category": "dns", 
                    "message": "存在无效 DNS", 
                    "detail": str(bad_dns), 
                    "suggestion": "检查 DHCP"
                })
                result.config_score -= 10

    result.config_score = max(0, result.config_score)
    return result

def print_local_config_report(result: LocalConfigCheckResult):
    """打印报告"""
    print("\n" + "=" * 60)
    print("📋 本地网络配置检测报告")
    print("=" * 60)
    
    print("\n🖥️ 【主网络适配器】")
    if result.primary_nic:
        print(f"  名称：{result.primary_nic.name}")
        print(f"  状态：{result.primary_nic.status}")
        print(f"  IP地址：{', '.join(result.primary_nic.ip_addresses)}")
        print(f"  网关：{', '.join(result.primary_nic.gateways)}")
        print(f"  DNS：{', '.join(result.primary_nic.dns_servers)}")
    else:
        print("  ⚠️ 未检测到有效的主网络适配器")
        if result.all_nics:
            print(f"  ℹ️ 检测到的其他网卡: {[n.name for n in result.all_nics]}")
        
    print("\n🔌【系统代理】")
    print(f"  状态：{'开启 ⚠️' if result.proxy_enabled else '关闭 ✅'}")
    
    print("\n🛡️  【防火墙】")
    print(f"  状态：{'开启' if result.firewall_enabled else '关闭'}")
    
    print("\n📊 【配置健康评分】")
    score = result.config_score
    status = "✅ 配置良好" if score >= 80 else ("⚠️ 存在配置问题" if score >= 60 else "❌ 配置问题严重")
    print(f"  评分：{score:.1f} {status}")
    
    if result.issues:
        print("\n⚠️  【发现的问题】")
        for i, issue in enumerate(result.issues, 1):
            level_icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(issue["level"], "•")
            print(f"  {level_icon} {i}. {issue['message']}")
            if issue.get('detail'): print(f"      详情：{issue['detail']}")
            print(f"      建议：{issue['suggestion']}")
    else:
        print("\n✅ 未发现明显配置问题")
    print("=" * 60)