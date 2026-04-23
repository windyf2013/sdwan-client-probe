#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨境链路专项测试模块
职责：执行跨境业务目标的连通性、延迟及路径质量检测
"""

import re
import time
import logging
import socket
import subprocess
import platform
import concurrent.futures
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Union

from sdwan_analyzer.core.ping import ping_check
from sdwan_analyzer.modules.app_probe import run_app_probe, detect_mtu
from sdwan_analyzer.models.diagnose import PingResult, AppProbeResult
from sdwan_analyzer.utils.logger import get_logger

logger = get_logger('cross_border_test')


@dataclass
class LinkQualityResult:
    """单个链路的详细测试结果"""
    target: str = ""
    avg_latency: float = 0.0
    min_latency: float = 0.0
    max_latency: float = 0.0
    jitter: float = 0.0
    packet_loss: float = 0.0
    route_hops: int = 0
    stability_score: float = 0.0
    mtu: int = 0  # MTU值
    dns_pollution_detected: bool = False
    issues: List[Dict] = field(default_factory=list)
    
    # 兼容旧版 CrossBorderTestResult 的部分字段，防止 main.py 中其他地方引用出错
    @property
    def is_reachable(self):
        return self.stability_score > 0 and self.packet_loss < 100

    @property
    def loss_rate(self):
        return self.packet_loss


@dataclass
class PrecheckResult:
    """预检测结果"""
    gateway_ping_success: bool = False
    ping_results: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DNSComparisonResult:
    """DNS对比测试结果"""
    target_domain: str = ""
    
    # 1. 网关 DNS
    gateway_dns_status: str = "unknown"
    gateway_resolved_ips: List[str] = field(default_factory=list)
    
    # 2. 系统默认 DNS (新增)
    system_dns_status: str = "unknown"
    system_resolved_ips: List[str] = field(default_factory=list)
    system_dns_server: str = "" # 记录具体的系统DNS IP
    
    # 3. 公共 DNS (8.8.8.8)
    public_dns_status: str = "unknown"
    local_resolved_ips: List[str] = field(default_factory=list) # 保持兼容，指代公共DNS结果
    
    comparison_note: str = ""


@dataclass
class CrossBorderTestResult:
    """跨境测试的整体结果对象 (Main.py 期望的结构)"""
    link_results: List[LinkQualityResult] = field(default_factory=list)
    overall_score: float = 0.0
    summary: str = ""
    precheck: Optional[PrecheckResult] = None
    dns_comparison: Optional[DNSComparisonResult] = None
    
    # 兼容属性：如果 main.py 直接访问这些，可以在此映射
    @property
    def google_dns_reachable(self):
        if self.precheck:
            return self.precheck.gateway_ping_success
        return False


def get_default_gateway() -> Optional[str]:
    """获取系统默认网关 IP 地址"""
    try:
        if platform.system() == "Windows":
            output = subprocess.check_output(["route", "print", "0.0.0.0"], stderr=subprocess.DEVNULL).decode('gbk', errors='ignore')
            for line in output.splitlines():
                if "0.0.0.0" in line and "0.0.0.0" in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        gw = parts[2]
                        if gw != "0.0.0.0" and gw != "On-link":
                            return gw
        else:
            output = subprocess.check_output(["ip", "route", "show", "default"], stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore')
            if output:
                parts = output.split()
                if "via" in parts:
                    idx = parts.index("via")
                    if idx + 1 < len(parts):
                        return parts[idx + 1]
    except Exception as e:
        logger.warning(f"获取默认网关失败: {e}")
    return None

def get_system_primary_dns() -> Optional[str]:
    """
    获取系统当前网卡配置的首选 DNS 服务器 IP
    【增强版】优先返回 IPv4，自动过滤 fe80:: 等链路本地地址
    """
    try:
        if platform.system() == "Windows":
            # 使用 ipconfig /all 获取更详细的 DNS 信息
            output = subprocess.check_output(["ipconfig", "/all"], stderr=subprocess.DEVNULL).decode('gbk', errors='ignore')
            lines = output.splitlines()
            
            collected_dns_v4 = []
            collected_dns_v6 = []
            
            # 状态标记：是否正在读取某个适配器的 DNS 部分
            in_dns_section = False
            
            for line in lines:
                # 检测新的适配器块开始 (例如: "Ethernet adapter Ethernet:")
                if "adapter" in line.lower() and ":" in line:
                    in_dns_section = False # 重置状态，准备读取新适配器的 DNS
                
                # 检测 DNS 服务器行
                if "DNS Servers" in line or "DNS 服务器" in line:
                    in_dns_section = True
                    parts = line.split(":")
                    if len(parts) > 1:
                        ip = parts[1].strip()
                        if ip:
                            _classify_and_store_dns(ip, collected_dns_v4, collected_dns_v6)
                    continue # 继续检查是否有同一行的其他内容（通常没有）
                
                # 检测缩进的后续 DNS 行 (通常以空格开头)
                if in_dns_section and line.startswith(" ") and line.strip():
                    ip = line.strip()
                    # 如果遇到新的非 DNS 字段（如 Default Gateway），则退出 DNS 读取区
                    if ":" in ip and not re.match(r'\s*\d', line): 
                         # 简单的启发式判断：如果包含冒号且不是IP格式，可能是新字段
                         # 但为了稳健，我们只处理看起来像 IP 的行
                         pass
                    
                    if re.match(r'^[\d\.:a-fA-F]+$', ip): # 简单的 IP 格式校验
                         _classify_and_store_dns(ip, collected_dns_v4, collected_dns_v6)
                
                # 如果遇到空行或非缩进行，结束当前适配器的 DNS 读取
                elif in_dns_section and not line.startswith(" ") and line.strip():
                    in_dns_section = False

            # 优先返回 IPv4
            if collected_dns_v4:
                return collected_dns_v4[0]
            # 其次返回非 fe80 的 IPv6
            if collected_dns_v6:
                return collected_dns_v6[0]
                
        else:
            # Linux/Mac: 读取 resolv.conf
            with open("/etc/resolv.conf", "r") as f:
                for line in f:
                    if line.startswith("nameserver"):
                        ip = line.split()[1].strip()
                        if not ip.startswith('fe80') and not ip.startswith('169.254'):
                            return ip
    except Exception as e:
        logger.warning(f"获取系统首选DNS失败: {e}")
    return None

def _classify_and_store_dns(ip: str, v4_list: list, v6_list: list):
    """辅助函数：分类并存储 DNS IP"""
    if not ip:
        return
    # 过滤无效 IP
    if ip.startswith('0.') or ip.startswith('127.') or ip.startswith('169.254.'):
        return
    # 过滤 fe80 开头的 IPv6 链路本地地址
    if ip.lower().startswith('fe80'):
        return
        
    if '.' in ip:
        v4_list.append(ip)
    elif ':' in ip:
        v6_list.append(ip)

def perform_dns_comparison(domain: str = "www.google.com") -> DNSComparisonResult:
    """
    执行三源 DNS 对比测试: 
    1. 默认网关 DNS
    2. 系统配置的首选 DNS
    3. 公共 DNS (8.8.8.8)
    """
    result = DNSComparisonResult(target_domain=domain)
    gateway_ip = get_default_gateway()
    system_dns_ip = get_system_primary_dns()
    
    logger.info(f"[DNS] 开始三源对比测试: {domain}")
    logger.info(f"  - 网关: {gateway_ip}")
    logger.info(f"  - 系统DNS: {system_dns_ip}")
    logger.info(f"  - 公共DNS: 8.8.8.8")

    # 定义 DNS 查询辅助函数
    def query_dns(server: str, label: str) -> tuple[str, list[str]]:
        """返回 (status, ips)"""
        if not server:
            return ("skipped", [])
            
        try:
            cmd = ["nslookup", domain, server]
            proc = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            output = proc.stdout.decode('gbk', errors='ignore')
            
            import re
            ips = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', output)
            
            # 过滤无效 IP
            valid_ips = [
                ip for ip in ips 
                if ip != server and not ip.startswith('0.') and not ip.startswith('127.') and not ip.startswith('169.254.')
            ]
            
            unique_ips = list(dict.fromkeys(valid_ips))
            
            if unique_ips:
                return ("success", unique_ips)
            else:
                return ("failed", [])
                
        except Exception as e:
            logger.warning(f"DNS Query to {server} ({label}) failed: {e}")
            return ("failed", [])

    # 并行执行三个 DNS 查询
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        gw_future = executor.submit(query_dns, gateway_ip, "Gateway") if gateway_ip else None
        sys_future = executor.submit(query_dns, system_dns_ip, "System") if system_dns_ip else None
        pub_future = executor.submit(query_dns, "8.8.8.8", "Public")

        # 获取结果
        gw_status, gw_ips = gw_future.result(timeout=10) if gw_future else ("skipped", [])
        sys_status, sys_ips = sys_future.result(timeout=10) if sys_future else ("skipped", [])
        pub_status, pub_ips = pub_future.result(timeout=10)

    # 填充结果对象
    result.gateway_dns_status = gw_status
    result.gateway_resolved_ips = gw_ips
    
    result.system_dns_status = sys_status
    result.system_resolved_ips = sys_ips
    result.system_dns_server = system_dns_ip or "N/A"
    
    result.public_dns_status = pub_status
    result.local_resolved_ips = pub_ips  # 兼容旧字段名

    # 生成对比结论 (以公共 DNS 8.8.8.8 为基准)
    notes = []
    
    # 1. 检查公共 DNS 是否成功
    if pub_status != "success":
        notes.append("❌ 公共DNS(8.8.8.8)解析失败，国际链路可能受阻")
    
    # 2. 对比网关 DNS
    if gw_status == "success" and pub_status == "success":
        if set(gw_ips) == set(pub_ips):
            notes.append("✅ 网关DNS与公共DNS一致")
        else:
            diff = set(gw_ips) - set(pub_ips)
            if diff:
                notes.append(f"⚠️ 网关DNS存在差异IP: {','.join(list(diff)[:2])}")
    elif gw_status == "failed":
        notes.append("❌ 网关DNS解析失败")
        
    # 3. 对比系统 DNS
    if sys_status == "success" and pub_status == "success":
        if set(sys_ips) == set(pub_ips):
            notes.append("✅ 系统DNS与公共DNS一致")
        else:
            diff = set(sys_ips) - set(pub_ips)
            if diff:
                notes.append(f"⚠️ 系统DNS存在差异IP: {','.join(list(diff)[:2])}")
    elif sys_status == "failed":
        notes.append("❌ 系统DNS解析失败")

    result.comparison_note = "; ".join(notes) if notes else "无有效对比数据"
    logger.info(f"[DNS] 对比完成: {result.comparison_note}")
    
    return result

def _test_single_target(target: str) -> LinkQualityResult:
    """
    内部函数：测试单个目标并返回 LinkQualityResult
    """
    result = LinkQualityResult(target=target)
    logger.info(f"正在测试目标: {target}")
    
    try:
        # 1. Ping 测试
        ping_res = ping_check(target, 10)
        
        if ping_res.is_success:
            result.avg_latency = ping_res.avg_rtt
            result.min_latency = ping_res.min_rtt
            result.max_latency = ping_res.max_rtt
            result.packet_loss = ping_res.loss
            # 简单计算抖动 (如果没有直接提供)
            result.jitter = (ping_res.max_rtt - ping_res.min_rtt) / 2 if ping_res.max_rtt > 0 else 0
        else:
            # 【修复点】当 Ping 失败时，必须显式标记丢包率为 100%，延迟为 0（或极大值，视策略而定）
            result.packet_loss = 100.0
            result.avg_latency = 9999.0  # <--- 修改点：设为极大值
            result.jitter = 0.0
            logger.warning(f"目标 {target} Ping 失败，标记为不可达")
            
        # 2. MTU 探测 (集成在链路测试中)
        # 注意：如果 Ping 已经失败，MTU 探测通常也会失败或返回最小值
        # 为了避免在不可达目标上浪费过多时间，可以加一个判断
        if ping_res.is_success:
            try:
                mtu_val = detect_mtu(target)
                result.mtu = mtu_val if mtu_val > 0 else 0
            except Exception as e:
                logger.debug(f"MTU探测异常: {e}")
                result.mtu = 0
        else:
            # 如果Ping不通，MTU设为0或保持默认，避免误导
            result.mtu = 0

        # 3. 计算稳定性评分 (简化算法)
        score = 100.0
        
        # 【修复点】优先检查是否完全不可达
        if result.packet_loss >= 100.0:
            score = 0.0
        else:
            if result.packet_loss > 0:
                score -= result.packet_loss * 5  # 丢包惩罚
            if result.avg_latency > 300:
                score -= (result.avg_latency - 300) * 0.1 # 高延迟惩罚
            if result.jitter > 50:
                score -= (result.jitter - 50) * 0.2 # 高抖动惩罚
        
        result.stability_score = max(0, min(100, score))
        
    except Exception as e:
        logger.error(f"测试目标 {target} 失败: {e}")
        result.stability_score = 0
        result.packet_loss = 100.0 # 确保异常时也标记为失败
        result.avg_latency = 9999.0 # <--- 异常时也设为极大值
        result.issues.append({"level": "error", "message": str(e)})

    return result


def run_cross_border_test(targets: List[Union[str, Dict[str, str]]], max_workers: int = 3) -> CrossBorderTestResult:
    """
    执行跨境链路专项测试
    
    Args:
        targets: 目标列表。支持字符串列表或字典列表。
        max_workers: 并行线程数
        
    Returns:
        CrossBorderTestResult: 包含所有链路结果的整体对象
    """
    # 1. 解析目标列表
    target_urls = []
    for item in targets:
        if isinstance(item, str):
            target_urls.append(item)
        elif isinstance(item, dict):
            url = item.get("target", "")
            if url:
                target_urls.append(url)
    
    if not target_urls:
        logger.warning("没有有效的测试目标")
        return CrossBorderTestResult(summary="无有效目标")

    logger.info(f"开始跨境链路专项测试，目标数量: {len(target_urls)}")
    
    test_result = CrossBorderTestResult()
    
    # 2. 阶段一：预检测 (8.8.8.8)
    logger.info("[Phase 1] 网关连通性预检测")
    gateway_ip = get_default_gateway()
    precheck = PrecheckResult()
    try:
        gw_ping = ping_check("8.8.8.8")
        precheck.gateway_ping_success = gw_ping.is_success
        precheck.ping_results = {"8.8.8.8": gw_ping.__dict__ if gw_ping else {}}
    except:
        precheck.gateway_ping_success = False
    test_result.precheck = precheck
    
    if not precheck.gateway_ping_success:
        logger.warning("预检测失败：无法访问 8.8.8.8，但将继续执行目标测试")

    # 3. 阶段二：并行链路测试
    logger.info("[Phase 2] 并行链路质量测试")
    results_map = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_target = {executor.submit(_test_single_target, t): t for t in target_urls}
        
        for future in concurrent.futures.as_completed(future_to_target):
            t = future_to_target[future]
            try:
                link_res = future.result(timeout=60)
                results_map[t] = link_res
            except Exception as e:
                logger.error(f"任务 {t} 执行异常: {e}")
                fail_res = LinkQualityResult(target=t, stability_score=0.0)
                fail_res.issues.append({"level": "error", "message": f"Task Error: {str(e)}"})
                results_map[t] = fail_res

    # 按原始顺序整理结果
    for t in target_urls:
        if t in results_map:
            test_result.link_results.append(results_map[t])

    # 4. 阶段三：DNS 对比测试 (执行真实查询)
    logger.info("[Phase 3] DNS 对比测试")
    try:
        # 执行真实的 DNS 对比
        dns_comp = perform_dns_comparison(domain="www.google.com")
        test_result.dns_comparison = dns_comp
    except Exception as e:
        logger.error(f"DNS 对比测试异常: {e}")
        # 即使失败也保留一个基本对象，防止 main.py 报错
        test_result.dns_comparison = DNSComparisonResult(
            target_domain="www.google.com",
            comparison_note=f"测试异常: {str(e)}"
        )

    # 5. 计算总分和总结
    if test_result.link_results:
        scores = [r.stability_score for r in test_result.link_results]
        test_result.overall_score = sum(scores) / len(scores)
        
        if test_result.overall_score >= 80:
            test_result.summary = "跨境链路质量良好"
        elif test_result.overall_score >= 60:
            test_result.summary = "跨境链路质量一般"
        else:
            test_result.summary = "跨境链路质量较差"
    else:
        test_result.summary = "未获取到有效测试数据"

    logger.info(f"测试完成。总体评分: {test_result.overall_score:.1f}")
    return test_result


def get_cross_border_report(results: Union[List[LinkQualityResult], CrossBorderTestResult]) -> Dict[str, Any]:
    """
    生成跨境测试报告摘要 (兼容列表或对象输入)
    """
    link_list = []
    overall_score = 0.0
    summary = ""
    
    if isinstance(results, CrossBorderTestResult):
        link_list = results.link_results
        overall_score = results.overall_score
        summary = results.summary
    elif isinstance(results, list):
        link_list = results
        if link_list:
            scores = [getattr(r, 'stability_score', 0) for r in link_list]
            overall_score = sum(scores) / len(scores)
            summary = "Legacy List Report"

    if not link_list:
        return {"status": "empty", "details": []}
        
    return {
        "status": "completed",
        "overall_score": overall_score,
        "summary": summary,
        "details": [
            {
                "target": r.target,
                "avg_latency": r.avg_latency,
                "packet_loss": r.packet_loss,
                "stability_score": r.stability_score,
                "mtu": r.mtu
            } for r in link_list
        ]
    }