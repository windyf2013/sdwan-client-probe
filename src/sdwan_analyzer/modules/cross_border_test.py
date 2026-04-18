# sdwan_analyzer/modules/cross_border_test.py
"""跨境链路专项测试模块 - 检测影响跨境业务的网络质量"""

import subprocess
import re
import time
import concurrent.futures
import logging
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# 假设这些模块存在，保持导入
from sdwan_analyzer.core.ping import ping_check
from sdwan_analyzer.utils.logger import get_logger

# 新增模块导入 - 报告生成相关
try:
    from sdwan_analyzer.modules.report import export_report_to_file, _collect_routing_info
except ImportError:
    export_report_to_file = None
    _collect_routing_info = None

logger = get_logger('cross_border_test')

@dataclass
class LinkQualityResult:
    """链路质量测试结果"""
    target: str = ""
    avg_latency: float = 0.0
    min_latency: float = 0.0
    max_latency: float = 0.0
    jitter: float = 0.0
    packet_loss: float = 0.0
    route_hops: int = 0
    dns_pollution_detected: bool = False
    stability_score: float = 0.0
    issues: List[Dict] = field(default_factory=list)


@dataclass
class DNSComparisonResult:
    """DNS对比测试结果"""
    target_domain: str = ""
    gateway_dns_result: str = ""
    gateway_dns_status: str = ""  # success/failed
    gateway_resolved: bool = False
    gateway_resolved_ips: List[str] = None
    gateway_dns_servers: List[str] = None
    public_dns_result: str = ""
    public_dns_status: str = ""  # success/failed
    local_resolved: bool = False  # public DNS used as local
    local_resolved_ips: List[str] = None
    local_dns_servers: List[str] = None
    comparison_note: str = ""  # 对比分析说明

    def __init__(self, target_domain: str = ""):
        self.target_domain = target_domain
        self.gateway_resolved_ips = []
        self.gateway_dns_servers = []
        self.local_resolved_ips = []
        self.local_dns_servers = []


@dataclass
class CrossBorderTestPrecheck:
    """跨境测试预检测结果"""
    gateway_ping_success: bool = False
    ping_results: Dict = field(default_factory=dict)  # 8.8.8.8 ping详细结果
    dns_comparison: Optional[DNSComparisonResult] = None
    precondition_passed: bool = False


@dataclass
class CrossBorderTestResult:
    """跨境测试完整结果"""
    link_results: List[LinkQualityResult] = field(default_factory=list)
    overall_score: float = 0.0
    summary: str = ""
    precheck: Optional[CrossBorderTestPrecheck] = None  # 新增预检测结果
    dns_comparison_results: List[DNSComparisonResult] = field(default_factory=list)  # DNS对比测试结果
    test_start_time: str = ""
    test_duration: float = 0.0
    enhanced_report_available: bool = False


def measure_jitter(target: str, count: int = 20, timeout: int = 10) -> float:
    """
    测量网络抖动
    优化：减少ping次数以加快速度，移除shell=True
    """
    rtt_list = []
    try:
        # Windows ping: -n count, -w timeout(ms)
        cmd = ["ping", "-n", str(count), "-w", "1000", target]
        
        # 使用 subprocess.run 替代 check_output 以便更好地控制超时和错误
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout, # 整个命令的最大执行时间
            creationflags=subprocess.CREATE_NO_WINDOW # Windows专用，隐藏弹窗，加速执行
        )
        
        if result.returncode != 0 and not result.stdout:
            return 0.0
            
        output = result.stdout.decode('gbk', errors='ignore')
        
        # 匹配所有往返时间
        # 示例输出: 来自 1.1.1.1 的回复: 字节=32 时间=15ms TTL=58
        pattern = r'时间[=<](\d+)ms'
        matches = re.findall(pattern, output)
        
        for match in matches:
            rtt_list.append(int(match))
        
        if len(rtt_list) < 2:
            return 0.0
        
        # 计算抖动 (平均差值)
        jitter_sum = sum(abs(rtt_list[i] - rtt_list[i-1]) for i in range(1, len(rtt_list)))
        jitter = jitter_sum / (len(rtt_list) - 1)
        
        return float(jitter)
        
    except subprocess.TimeoutExpired:
        logger.warning(f"Jitter test timeout for {target}")
        return 0.0
    except Exception as e:
        logger.warning(f"Jitter test error for {target}: {e}")
        return 0.0


def check_dns_pollution(target: str, timeout: int = 3) -> Dict[str, str]:
    """
    检测 DNS 污染
    :return: 字典 {dns_server_ip: resolved_ip}，如果解析失败则不包含该键
    """
    dns_servers = ["8.8.8.8", "1.1.1.1", "223.5.5.5"]
    results = {}
    
    for dns_ip in dns_servers:
        try:
            # nslookup target dns_server
            cmd = ["nslookup", target, dns_ip]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                output = result.stdout.decode('gbk', errors='ignore')
                ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
                ips = re.findall(ip_pattern, output)
                
                # 过滤掉DNS服务器本身的IP和非标准IP
                resolved_ips = [ip for ip in ips if ip != dns_ip and not ip.startswith('0.') and not ip.startswith('127.')]
                
                if resolved_ips:
                    results[dns_ip] = resolved_ips[0]
                    
        except Exception:
            continue
    
    return results


def get_route_hops(target: str, timeout: int = 15) -> int:
    """
    获取路由跳数
    优化：严格限制跳数(-h)和等待时间(-w)，防止tracert卡死
    """
    try:
        # -d: 不解析主机名(加速)
        # -h 15: 最大15跳(跨境通常够用，减少等待)
        # -w 1000: 每跳等待1秒
        cmd = ["tracert", "-d", "-h", "15", "-w", "1000", target]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout, # 总超时15秒
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        output = result.stdout.decode('gbk', errors='ignore')
        lines = output.split("\n")
        hop_count = 0
        for line in lines:
            # 匹配行首为数字的行，例如 "  1    <1 ms    <1 ms    <1 ms  192.168.1.1"
            if re.match(r'\s*\d+\s+', line):
                hop_count += 1
        
        return hop_count
        
    except subprocess.TimeoutExpired:
        logger.warning(f"Tracert timeout for {target}")
        return -1 # 返回-1表示超时/失败
    except Exception as e:
        logger.warning(f"Tracert error for {target}: {e}")
        return 0


def dns_lookup_with_details(domain: str, dns_server: str) -> Tuple[str, str, List[str], str]:
    """
    执行详细的DNS查询，返回状态、结果、详细信息和错误原因
    :return: (状态, 解析IP, 详情信息列表, 错误原因)
    """
    try:
        cmd = ["nslookup", domain, dns_server]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,  # 商业级: 15秒超时，支持高延迟网络
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result.returncode == 0:
            output = result.stdout.decode('gbk', errors='ignore')
            
            # 解析IP地址
            ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
            ips = re.findall(ip_pattern, output)
            
            # 过滤掉DNS服务器本身的IP和非标准IP
            resolved_ips = [ip for ip in ips if ip != dns_server and not ip.startswith('0.') and not ip.startswith('127.')]
            
            if resolved_ips:
                # 提取详细信息
                lines = output.split('\n')
                details = []
                for line in lines:
                    if '服务器' in line or 'Address' in line or '名称' in line or 'Name' in line:
                        details.append(line.strip())
                
                return ("success", resolved_ips[0], details, "")
            else:
                return ("failed", "", ["DNS查询成功但未解析到有效IP"], "no_valid_ip")
        else:
            return ("failed", "", [f"DNS查询失败，返回码: {result.returncode}"], f"return_code_{result.returncode}")
            
    except subprocess.TimeoutExpired:
        return ("timeout", "", ["DNS查询超时(15s)，建议检查网络延迟或DNS服务器响应"], "timeout_15s")
    except Exception as e:
        return ("error", "", [f"DNS查询异常: {str(e)}"], "exception")


def perform_8888_precheck(gateway_ip: str) -> CrossBorderTestPrecheck:
    """
    执行8.8.8.8预检测
    1. 对8.8.8.8执行ping测试（发4个包）
    2. 记录详细结果并标记
    3. 网关IP用于后续DNS对比测试
    """
    precheck = CrossBorderTestPrecheck()
    
    print("\n" + "=" * 60)
    print("[预检测] 8.8.8.8 连通性测试")
    print("=" * 60)
    
    # 1. 执行8.8.8.8 ping测试
    try:
        print("正在测试到 8.8.8.8 的连通性...")
        ping_result = ping_check("8.8.8.8", count=4)  # 发4个包
        
        precheck.ping_results = {
            "target": "8.8.8.8",
            "sent": ping_result.sent,
            "received": ping_result.received,
            "loss": ping_result.loss,
            "min_rtt": ping_result.min_rtt,
            "max_rtt": ping_result.max_rtt,
            "avg_rtt": ping_result.avg_rtt,
            "is_success": ping_result.is_success
        }
        
        precheck.gateway_ping_success = ping_result.is_success
        
        # 显示结果并标记
        if ping_result.is_success:
            print(f"[OK] 8.8.8.8 连通性测试通过")
            print(f"  数据包: 已发送 = 4，已接收 = {ping_result.received}，丢失 = {ping_result.loss}%")
            print(f"  延迟: 最短 = {ping_result.min_rtt}ms，最长 = {ping_result.max_rtt}ms，平均 = {ping_result.avg_rtt}ms")
        else:
            print(f"[FAIL] 8.8.8.8 连通性测试失败")
            print(f"  数据包丢失率: {ping_result.loss}%")
            
    except Exception as e:
        print(f"[FAIL] 8.8.8.8 连通性测试异常: {e}")
        precheck.gateway_ping_success = False
        precheck.ping_results = {"error": str(e)}
    
    return precheck


def perform_dual_dns_comparison(domain: str, gateway_ip: str) -> DNSComparisonResult:
    """
    双线程执行DNS对比测试
    - 线程1: nslookup www.google.com [网关IP]
    - 线程2: nslookup www.google.com 8.8.8.8
    
    :return: DNSComparisonResult对象
    """
    result = DNSComparisonResult(target_domain=domain)
    
    def run_dns_lookup(domain: str, dns_server: str) -> Tuple[str, str, List[str], str]:
        """执行DNS查询的辅助函数"""
        return dns_lookup_with_details(domain, dns_server)
    
    print(f"\n[DNS对比测试] 域名: {domain}")
    print("-" * 50)
    
    # 使用ThreadPoolExecutor实现双线程并行执行
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # 提交两个DNS查询任务
        gateway_future = executor.submit(run_dns_lookup, domain, gateway_ip)
        public_future = executor.submit(run_dns_lookup, domain, "8.8.8.8")
        
        # 等待两个任务完成，接收新的4元组返回值
        gateway_status, gateway_ip_result, gateway_details, gateway_error_reason = gateway_future.result(timeout=20)
        public_status, public_ip_result, public_details, public_error_reason = public_future.result(timeout=20)
    
    # 更新网关DNS结果
    result.gateway_dns_status = gateway_status
    result.gateway_dns_result = gateway_ip_result if gateway_status == "success" else f"查询失败({gateway_error_reason})"
    
    # 更新公共DNS结果
    result.public_dns_status = public_status
    result.public_dns_result = public_ip_result if public_status == "success" else f"查询失败({public_error_reason})"
    
    # 串口输出结果
    print(f"使用网关DNS ({gateway_ip}):")
    print(f"  状态: {'[OK] 成功' if gateway_status == 'success' else '[FAIL] 失败'}")
    if gateway_status == "success":
        print(f"  解析结果: {gateway_ip_result}")
        print(f"  所有解析IP地址: {'，'.join(gateway_details) if gateway_details else '无详细IP信息'}")
        if gateway_details:
            for i, detail in enumerate(gateway_details, 1):
                print(f"    {i}. {detail}")
    
    print(f"\n使用公共DNS (8.8.8.8):")
    print(f"  状态: {'[OK] 成功' if public_status == 'success' else '[FAIL] 失败'}")
    if public_status == "success":
        print(f"  解析结果: {public_ip_result}")
        print(f"  所有解析IP地址: {'，'.join(public_details) if public_details else '无详细IP信息'}")
        if public_details:
            for i, detail in enumerate(public_details, 1):
                print(f"    {i}. {detail}")
    
    # 对比分析 - 增加详细对比告警
    if gateway_status == "success" and public_status == "success":
        # 获取所有解析的IP进行对比
        gateway_ips = gateway_details if gateway_details else []
        public_ips = public_details if public_details else []
        
        if set(gateway_ips) == set(public_ips):
            result.comparison_note = "网关DNS和公共DNS解析结果完全一致"
        else:
            # 找出差异IP
            diff_gateway = set(gateway_ips) - set(public_ips)
            diff_public = set(public_ips) - set(gateway_ips)
            
            warning_msg = "[WARNING] DNS解析存在差异"
            if diff_gateway:
                warning_msg += f" | 网关DNS独有IP: {', '.join(diff_gateway)}"
            if diff_public:
                warning_msg += f" | 公共DNS独有IP: {', '.join(diff_public)}"
            
            result.comparison_note = warning_msg
            print(f"\n[WARN] DNS解析对比发现差异:")
            if diff_gateway:
                print(f"  - 网关DNS独有IP地址: {', '.join(diff_gateway)}")
            if diff_public:
                print(f"  - 公共DNS独有IP地址: {', '.join(diff_public)}")
    elif gateway_status == "success":
        result.comparison_note = "网关DNS解析成功，公共DNS解析失败"
    elif public_status == "success":
        result.comparison_note = "公共DNS解析成功，网关DNS解析失败"
    else:
        result.comparison_note = "网关DNS和公共DNS均解析失败"
    
    print(f"\n对比分析: {result.comparison_note}")
    
    return result


def calculate_stability_score(link_result: LinkQualityResult, dns_results: Dict[str, str] = None) -> float:
    """计算链路稳定性评分"""
    score = 100.0
    
    # 延迟评分
    if link_result.avg_latency > 400:
        score -= 40
    elif link_result.avg_latency > 300:
        score -= 30
    elif link_result.avg_latency > 200:
        score -= 20
    
    # 抖动评分
    if link_result.jitter > 100:
        score -= 30
    elif link_result.jitter > 50:
        score -= 20
    
    # 丢包评分
    if link_result.packet_loss > 10:
        score -= 40
    elif link_result.packet_loss > 5:
        score -= 20
    elif link_result.packet_loss > 1:
        score -= 5
        
    # DNS 污染评分逻辑
    is_polluted = False
    if dns_results and len(dns_results) > 1:
        unique_ips = set(dns_results.values())
        if len(unique_ips) > 1:
            is_polluted = True
            score -= 10 # 降低扣分权重，因为CDN差异很常见
            
    # 更新 link_result 中的标记，供后续生成 Issue 使用
    link_result.dns_pollution_detected = is_polluted
            
    # 5. 路由追踪 (优化：区分“完全不可达”和“部分隐藏”)
    if link_result.route_hops == -1:
        # 如果 Ping 通但 Tracert 超时，通常是因为防火墙拦截 ICMP，而非链路中断
        if link_result.avg_latency > 0 and link_result.packet_loss < 100:
            score -= 5  # 仅轻微扣分，表示“路由信息不全”
        else:
            score -= 30 # 只有当 Ping 也不通时，才认为路由严重故障
    
    return max(0.0, min(100.0, score))


def test_single_target(target: str) -> LinkQualityResult:
    """测试单个目标的链路质量"""
    logger.info(f"Starting test for target: {target}")
    result = LinkQualityResult(target=target)
    
    # 1. Ping 测试 (基础连通性)
    try:
        # 假设 ping_check 是快速的，如果不是，建议也加上超时保护
        ping_result = ping_check(target, is_crossborder=True)
        result.avg_latency = ping_result.avg_rtt
        result.min_latency = ping_result.min_rtt
        result.max_latency = ping_result.max_rtt
        result.packet_loss = ping_result.loss
    except Exception as e:
        logger.error(f"Ping failed for {target}: {e}")
        result.issues.append({
            "level": "error",
            "category": "ping",
            "message": f"Ping 测试失败",
            "detail": str(e),
            "suggestion": "检查目标地址是否正确或网络是否中断"
        })
        # 如果Ping都失败，后续测试可能无意义，但为了完整性继续执行轻量级测试
    
    # 2. 并行执行耗时操作 (Jitter, DNS, Tracert)
    # 注意：这里是在线程中串行调用，但相对于主线程的其他目标是并行的
    # 如果想进一步优化单个目标内部的速度，可以在这三个函数之间也用 ThreadPoolExecutor
    
    result.jitter = measure_jitter(target)
    # 获取详细的 DNS 解析结果
    dns_results = check_dns_pollution(target)
    result.route_hops = get_route_hops(target)
    
    result.stability_score = calculate_stability_score(result, dns_results)

    # --- DNS 污染详细报告 ---
    if result.dns_pollution_detected:
        unique_ips = set(dns_results.values())
        detail_msg = f"不同DNS解析结果不一致: {dns_results}"
        result.issues.append({
            "level": "warning",
            "category": "dns_pollution",
            "message": f"检测到 DNS 解析差异 ({len(unique_ips)} 个不同IP)",
            "detail": detail_msg,
            "suggestion": "如果是国内CDN域名，不同DNS返回不同IP属正常现象；若访问异常，请尝试更换本地DNS为 223.5.5.5 或 114.114.114.114"
        })
        logger.warning(f"DNS Pollution Detected for {target}: {dns_results}")

    # 生成问题建议
    if result.avg_latency > 300:
        result.issues.append({
            "level": "warning",
            "category": "latency",
            "message": f"跨境延迟较高 ({result.avg_latency:.0f}ms)",
            "suggestion": "跨境链路固有延迟，若影响业务可考虑加速通道"
        })
    
    if result.packet_loss > 5:
        result.issues.append({
            "level": "error",
            "category": "packet_loss",
            "message": f"丢包率过高 ({result.packet_loss:.1f}%)",
            "suggestion": "检查本地网络拥塞或联系运营商"
        })
        
    if result.route_hops == -1:
         result.issues.append({
            "level": "error",
            "category": "route",
            "message": "路由追踪超时",
            "suggestion": "中间节点可能禁用了ICMP，或网络严重拥塞"
        })

    logger.info(f"--- [{target}] 详细得分拆解 ---")
    logger.info(f"Latency: {result.avg_latency}ms (Loss: {result.packet_loss}%, Jitter: {result.jitter}ms)")
    logger.info(f"DNS Pollution: {result.dns_pollution_detected}")
    logger.info(f"Route Hops: {result.route_hops} (-1 means timeout)")
    logger.info(f"Final Score: {result.stability_score}")
    logger.info(f"Issues: {result.issues}")

    logger.info(f"Finished test for target: {target}, Score: {result.stability_score}")
    return result


def run_cross_border_test(targets: List[str], max_workers: int = 3) -> CrossBorderTestResult:
    """
    执行跨境链路专项测试 (集成优化版)
    新增功能: 
      1. 8.8.8.8预检测逻辑
      2. 双线程DNS对比测试  
      3. 专项测试报告生成
      4. 原有测试流程保持不变
    """
    test_result = CrossBorderTestResult()
    
    # 商业级测试启动界面 (ASCII兼容)
    print("\n[状态] 初始化测试环境...")
    
    start_time = time.time()
    
    # ===================== 新增功能1: 8.8.8.8预检测 =====================
    print("\n" + "=" * 50)
    print("[NET] 阶段1: 网关连通性预检测")
    print("=" * 50)
    gateway_ip = get_default_gateway()
    print(f"[GW] 检测到网络网关: {gateway_ip}")
    print("[PROC] 测试Google DNS(8.8.8.8)连通性...")
    
    precheck_result = perform_8888_precheck(gateway_ip)
    test_result.precheck = precheck_result
    
    # 根据预检测结果决定是否继续
    if not precheck_result.gateway_ping_success:
        print("\n[FAIL] **预检测结果**: 网关连通性异常")
        print("   [CHECK] 检测项目: 8.8.8.8不可访问")
        print("   [TIPS] 行动建议: 网络连接存在异常，建议优先进行故障排查")
        # 如果失败，则中断流程
        logger.error("网关连通性预检测失败，终止跨境链路测试流程")
        test_result.overall_score = 0
        return test_result
    else:
        print("\n[OK] **预检测结果**: 网关连通性正常")
        print("   [CHECK] 检测项目: 8.8.8.8可达")
    print("- - - - - - - - - - - - - - - - - - - - - - - - -")
    
    # ===================== 新增功能2: 双线程DNS对比测试 =====================
    print("\n" + "=" * 50)
    print("[DNS] 阶段2: DNS解析对比测试")
    print("=" * 50)
    dns_domain = "www.google.com"
    print(f"[DOMAIN] 测试域名: {dns_domain}")
    print("[PROC] 启动双线程DNS对比测试(超时: 15秒)...")
    dns_comparison = perform_dual_dns_comparison(dns_domain, gateway_ip)
    test_result.dns_comparison = dns_comparison

    # ===================== 原有功能: 保持现有的测试流程 =====================
    print("\n" + "=" * 50)
    print("[PERF] 阶段3: 跨境链路性能测试")
    print("=" * 50)
    completed_count = 0
    total_count = len(targets)
    print(f"[TARGET] 测试目标数量: {total_count}个")
    print("[START] 开始并行测试流程...")
    
    results_map = {}

    # 使用 ThreadPoolExecutor 进行并行测试
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交任务
        future_to_target = {executor.submit(test_single_target, target): target for target in targets}
        
        # 处理完成的任务
        for future in concurrent.futures.as_completed(future_to_target):
            target = future_to_target[future]
            try:
                # 获取结果，如果异常会在这里抛出
                link_result = future.result(timeout=60) # 每个任务最多等60秒，防止个别卡死
                results_map[target] = link_result
                completed_count += 1
                
                # 实时打印进度
                status_icon = "[OK]" if link_result.stability_score >= 80 else ("[WARN]" if link_result.stability_score >= 60 else "[ERROR]")
                print(f"[{completed_count}/{total_count}] {target:<25} | 评分: {link_result.stability_score:.1f} {status_icon} | 延迟: {link_result.avg_latency:.0f}ms")
                
            except concurrent.futures.TimeoutError:
                completed_count += 1
                print(f"[{completed_count}/{total_count}] {target:<25} | [ERROR] 任务超时")
                fail_result = LinkQualityResult(target=target, stability_score=0.0)
                fail_result.issues.append({"level": "error", "message": "测试任务超时"})
                results_map[target] = fail_result
            except Exception as e:
                completed_count += 1
                print(f"[{completed_count}/{total_count}] {target:<25} | [ERROR] 异常: {str(e)[:30]}")
                logger.error(f"Target {target} test exception: {e}", exc_info=True)
                fail_result = LinkQualityResult(target=target, stability_score=0.0)
                fail_result.issues.append({"level": "error", "message": f"测试异常: {str(e)}"})
                results_map[target] = fail_result

    # 按原始顺序整理结果
    for target in targets:
        if target in results_map:
            test_result.link_results.append(results_map[target])

    end_time = time.time()
    duration = end_time - start_time
    
    # 计算整体评分
    if test_result.link_results:
        scores = [r.stability_score for r in test_result.link_results]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        test_result.overall_score = avg_score
        
        if avg_score >= 80:
            test_result.summary = "跨境链路质量良好"
        elif avg_score >= 60:
            test_result.summary = "跨境链路质量一般"
        else:
            test_result.summary = "跨境链路质量较差"
    
    # ===================== 增强收尾：商业级用户体验 =====================
    print("\n" + "─" * 60)
    print("[SUMMARY] 测试任务执行摘要")
    print("─" * 60)
    print(f"[TIME] 总执行时间: {duration:.2f} 秒 (商业级效率)")
    
    # 性能评分分级显示
    if test_result.overall_score >= 85:
        score_icon = "[EXCELLENT]"
        score_desc = "优秀"
    elif test_result.overall_score >= 70:
        score_icon = "[GOOD]"
        score_desc = "良好"
    elif test_result.overall_score >= 60:
        score_icon = "[ACCEPTABLE]"
        score_desc = "可接受"
    else:
        score_icon = "[POOR]"
        score_desc = "需改进"
    
    print(f"{score_icon} 网络质量评分: {test_result.overall_score:.1f}/100 ({score_desc})")
    
    # DNS对比测试摘要
    if hasattr(test_result, 'dns_comparison') and test_result.dns_comparison:
        dns_stats = test_result.dns_comparison
        if dns_stats.gateway_resolved and dns_stats.local_resolved:
            dns_status = "[OK] 解析一致性正常"
        elif not dns_stats.gateway_resolved:
            dns_status = "[WARN] 网关DNS查询超时"
        else:
            dns_status = "[WARN] DNS解析存在差异"
        print(f"[DNS] DNS对比测试: {dns_status}")
    
    print("─" * 60)
    
    # 智能测试建议
    print("\n[SUGGEST] 测试建议:")
    if test_result.overall_score >= 80:
        print("   - 网络质量优秀，可满足商业运营需求")
        print("   - 建议定期监控维护当前配置")
    elif test_result.overall_score >= 60:
        print("   - 网络基本可用，建议优化DNS配置")
        print("   - 可考虑调整路由策略提升稳定性")  
    else:
        print("   - 网络存在明显问题，需要故障排查")
        print("   - 建议检查网关连通性和DNS设置")
    
    # 生成详细报告
    print("\n" + "=" * 50)
    print("[REPORT] 阶段4: 生成绩效分析报告")
    print("=" * 50)
    print("[BUILD] 正在生成商业级测试报告...")
    full_report = generate_cross_border_report(test_result)
    print("\n" + "=" * 30 + " 测试报告开始 " + "=" * 30)
    print(full_report)
    print("=" * 30 + " 测试报告结束 " + "=" * 30)
    
    return test_result


def get_default_gateway() -> str:
    """获取默认网关IP地址"""
    try:
        # 在Windows上使用ipconfig获取默认网关
        result = subprocess.run(['ipconfig'], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                if '默认网关' in line or 'Default Gateway' in line:
                    parts = line.split(':')
                    if len(parts) > 1:
                        gateway_ip = parts[1].strip()
                        # 验证是否为有效的IPv4地址
                        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
                        if re.match(ip_pattern, gateway_ip):
                            return gateway_ip
    except Exception as e:
        print(f"获取默认网关失败: {e}")
    
    # 如果无法获取，提供一个常见的网关地址
    return "192.168.1.1"


def get_cross_border_report(test_result: CrossBorderTestResult) -> Dict:
    """生成跨境测试报告数据"""
    report_data = {
        "overall_score": test_result.overall_score,
        "summary": test_result.summary,
        "targets": [
            {
                "target": r.target,
                "avg_latency": r.avg_latency,
                "jitter": r.jitter,
                "packet_loss": r.packet_loss,
                "stability_score": r.stability_score,
                "issues": r.issues
            }
            for r in test_result.link_results
        ]
    }
    
    # 添加新增功能的报告数据
    if hasattr(test_result, 'precheck') and test_result.precheck:
        report_data['precheck'] = {
            'gateway_ping_success': test_result.precheck.gateway_ping_success,
            'ping_results': test_result.precheck.ping_results
        }
    
    if hasattr(test_result, 'dns_comparison') and test_result.dns_comparison:
        report_data['dns_comparison'] = {
            'target_domain': test_result.dns_comparison.target_domain,
            'gateway_dns_result': test_result.dns_comparison.gateway_dns_result,
            'gateway_dns_status': test_result.dns_comparison.gateway_dns_status,
            'public_dns_result': test_result.dns_comparison.public_dns_result,
            'public_dns_status': test_result.dns_comparison.public_dns_status,
            'comparison_note': test_result.dns_comparison.comparison_note
        }
    
    return report_data


def generate_cross_border_report(result: CrossBorderTestResult) -> str:
    """
    生成跨境链路专项测试报告
    包括预检测结果、DNS对比测试结果和原有测试结果
    """
    report_content = ""
    
    # 1. 报告头部信息
    report_content += "=" * 70 + "\n"
    report_content += "                 跨境网络质量分析报告 - Commercial Edition\n"
    report_content += "=" * 70 + "\n"
    report_content += f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    report_content += f"测试质量评分: {result.overall_score:.1f}%\n"
    
    # 测试环境信息
    report_content += "-" * 40 + "\n"
    report_content += "测试环境信息\n"
    report_content += "-" * 40 + "\n"
    
    # 从预检测结果获取网关信息，或从link_results获取测试目标
    if hasattr(result, 'precheck') and result.precheck:
        gateway_ip = result.precheck.gateway_ip if hasattr(result.precheck, 'gateway_ip') else "未知"
        report_content += f"测试网关地址: {gateway_ip}\n"
    
    if hasattr(result, 'link_results') and result.link_results:
        target_count = len(result.link_results)
        first_target = result.link_results[0].target if target_count > 0 else "未知"
        report_content += f"测试目标数量: {target_count}个 (主要目标: {first_target})\n"
    else:
        report_content += "测试目标: 未指定\n"
        
    report_content += f"测试协议版本: IPv4\n"
    report_content += f"DNS查询超时: 15秒（商业级配置）\n"
    
    # 2. 网关连通性预检测
    if hasattr(result, 'precheck') and result.precheck:
        report_content += "\n" + "-" * 50 + "\n"
        report_content += "1. 网关连通性预检测\n"
        report_content += "-" * 50 + "\n"
        
        ping_results = result.precheck.ping_results
        if ping_results and isinstance(ping_results, dict):
            status_mark = "[PASS]" if result.precheck.gateway_ping_success else "[FAIL]"
            report_content += f"Google DNS(8.8.8.8)测试: {status_mark} {'网关连通性正常' if result.precheck.gateway_ping_success else '网关连接失败'}\n"
            if 'sent' in ping_results:
                sent = ping_results.get('sent', 0)
                received = ping_results.get('received', 0) 
                loss_rate = ping_results.get('loss', 0)
                
                report_content += f"   数据包统计: 发送={sent}个, 接收={received}个, 丢包率={loss_rate:.1f}%\n"
                
                if 'avg_rtt' in ping_results:
                    avg_rtt = ping_results.get('avg_rtt', 0)
                    min_rtt = ping_results.get('min_rtt', 0)
                    max_rtt = ping_results.get('max_rtt', 0)
                    
                    # 网络延迟分级
                    if avg_rtt < 50:
                        rtt_level = "优秀"
                    elif avg_rtt < 100:
                        rtt_level = "良好"  
                    elif avg_rtt < 200:
                        rtt_level = "一般"
                    else:
                        rtt_level = "较差"
                        
                    report_content += f"   网络延迟(RTT): 平均={avg_rtt:.1f}ms ({rtt_level}), 最小={min_rtt:.1f}ms, 最大={max_rtt:.1f}ms\n"
    
    # 3. DNS解析对比分析
    if hasattr(result, 'dns_comparison') and result.dns_comparison:
        report_content += "\n" + "-" * 50 + "\n"
        report_content += "2. DNS解析对比分析\n"
        report_content += "-" * 50 + "\n"
        report_content += f"测试域名: {result.dns_comparison.target_domain}\n"
        
        # 本地DNS服务器解析状态
        local_status = "✅ 解析成功" if result.dns_comparison.local_resolved else "❌ 解析失败"
        local_ips = result.dns_comparison.local_resolved_ips if result.dns_comparison.local_resolved_ips else ["查询超时"]
        
        report_content += f"本地DNS服务器解析: {local_status}\n"
        report_content += f"   解析IP地址: {', '.join(local_ips)}\n"
        report_content += f"   DNS服务器: {', '.join(result.dns_comparison.local_dns_servers)}\n"
        
        # 网关DNS服务器解析状态  
        gateway_status = "✅ 解析成功" if result.dns_comparison.gateway_resolved else "❌ 查询超时(15s)"
        gateway_ips = result.dns_comparison.gateway_resolved_ips if result.dns_comparison.gateway_resolved_ips else ["暂无结果"]
        
        report_content += f"网关DNS服务器解析: {gateway_status}\n"
        report_content += f"   解析IP地址: {', '.join(gateway_ips)}\n" 
        report_content += f"   DNS服务器: {', '.join(result.dns_comparison.gateway_dns_servers)}\n"
        
        # DNS解析一致性分析
        if result.dns_comparison.local_resolved and result.dns_comparison.gateway_resolved:
            if set(result.dns_comparison.local_resolved_ips) == set(result.dns_comparison.gateway_resolved_ips):
                report_content += "DNS解析一致性: ✅ 本地与网关DNS解析结果一致\n"
            else:
                report_content += "DNS解析一致性: ⚠️ 本地与网关DNS解析存在差异\n"
        elif not result.dns_comparison.gateway_resolved:
            report_content += "DNS解析状态: ⚠️ 网关DNS查询15秒超时，可能因跨境网络延迟过高\n"
    
    # 4. 核心测试指标分析
    report_content += "\n" + "-" * 50 + "\n"
    report_content += "3. 核心测试指标分析\n"
    report_content += "-" * 50 + "\n"
    
    # 从预检测结果获取有用的连通性信息
    if hasattr(result, 'precheck') and result.precheck:
        ping_results = result.precheck.ping_results
        if ping_results and isinstance(ping_results, dict):
            avg_rtt = ping_results.get('avg_rtt', 0)
            loss_rate = ping_results.get('loss', 0)
            
            # 评估网关连通性
            if avg_rtt < 100:
                gateway_quality = "正常"
            elif avg_rtt < 300:
                gateway_quality = "高延迟"
            else:
                gateway_quality = "严重延迟"
                
            # 评估丢包情况
            if loss_rate < 1:
                packet_loss_level = "轻微"
            elif loss_rate < 5:
                packet_loss_level = "适中"
            else:
                packet_loss_level = "严重"
                
            report_content += f"国际链路质量: {gateway_quality}\n"
            report_content += f"  平均延迟: {avg_rtt:.1f}ms | 丢包率: {loss_rate:.1f}% ({packet_loss_level})\n"
    
    # DNS解析能力分析 (基于DNS对比测试)
    if hasattr(result, 'dns_comparison') and result.dns_comparison:
        dns_stats = result.dns_comparison
        report_content += f"DNS解析能力:\n"
        report_content += f"  网关DNS: {dns_stats.gateway_dns_status} | 8.8.8.8: {dns_stats.public_dns_status}\n"
        if dns_stats.gateway_dns_status == dns_stats.public_dns_status == 'success':
            if dns_stats.gateway_dns_result == dns_stats.public_dns_result:
                report_content += f"  DNS解析: 一致 (网关DNS解析正常)\n"
            else:
                report_content += f"  DNS解析: 存在差异 (可能DNS污染)\n"
        else:
            report_content += f"  DNS解析: 存在异常，建议检查DNS配置\n"
    
    # 网站连通性统计
    website_statuses = {}
    if hasattr(result, 'link_results') and result.link_results:
        success_count = sum(1 for r in result.link_results if r.stability_score >= 60)
        total_count = len(result.link_results)
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        
        report_content += f"网站连通性: {success_count}/{total_count} 个站点正常 (成功率: {success_rate:.1f}%)\n"
        
        # 列出具体站点状态
        for link_result in result.link_results:
            status_icon = "[OK]" if link_result.stability_score >= 60 else "[FAIL]"
            loss_info = f"丢包: {link_result.packet_loss:.1f}%" if link_result.packet_loss > 0 else "无丢包"
            report_content += f"  {link_result.target:<20} | 评分: {link_result.stability_score:.1f} {status_icon} | 延迟: {link_result.avg_latency:.0f}ms | {loss_info}\n"
    
    # 网站连通性 (如果有的话)
    website_results = getattr(result, 'website_results', {})
    if website_results:
        report_content += f"网站连通性: {len(website_results)} 个站点测试\n"
        for site, status in website_results.items():
            status_text = "通过" if status == "success" else "失败"
            report_content += f"  {site}: {status_text}\n"
    
    # 5. 综合评估与建议
    report_content += "\n" + "-" * 50 + "\n"
    report_content += "📋 综合评估结果\n"
    report_content += "-" * 50 + "\n"
    
    # 分级评估和改进建议
    if result.overall_score >= 90:
        assessment = "🟢 网络质量优秀"
        suggestion = "- 跨境链路质量稳定，符合商业运营标准"
        emoji = "🎯"
    elif result.overall_score >= 80:
        assessment = "🟢 网络质量良好" 
        suggestion = "- 跨境访问体验正常，适用于一般业务需求"
        emoji = "✅"
    elif result.overall_score >= 70:
        assessment = "🟡 网络质量可接受"
        suggestion = "- 存在轻微性能波动，建议监控链路稳定性"
        emoji = "⚠️"
    elif result.overall_score >= 60:
        assessment = "🟡 网络质量一般"
        suggestion = "- 跨境访问存在延迟，建议优化网络配置"
        emoji = "🔍"
    elif result.overall_score >= 40:
        assessment = "🔴 网络质量较差"
        suggestion = "- 跨境访问体验不佳，建议检查网关和DNS配置"
        emoji = "🔴"
    else:
        assessment = "🔴 网络质量严重异常"
        suggestion = "- 跨境连接失败，需要紧急网络故障排查"
        emoji = "🚨"
    
    report_content += f"综合评分: {result.overall_score:.1f}% {emoji}\n"
    report_content += f"质量等级: {assessment}\n"
    
    # 具体问题诊断和建议
    report_content += "\n📋 诊断建议:\n"
    report_content += f"{suggestion}\n"
    
    # 针对预检测失败的特殊建议
    if hasattr(result, 'precheck') and result.precheck and not result.precheck.gateway_ping_success:
        report_content += "\n🚨 网络连通性异常:\n"
        report_content += "- 网关无法访问Google DNS(8.8.8.8)\n"
        report_content += "- 建议优先检查网关网络连接和路由配置\n"
    
    # 针对DNS解析异常的诊断
    if hasattr(result, 'dns_comparison') and result.dns_comparison and not result.dns_comparison.gateway_resolved:
        report_content += "\n⚠️ DNS解析异常:\n"
        report_content += "- 网关DNS查询15秒超时，可能因跨境延迟过高\n"
        report_content += "- 建议配置备用DNS或调整DNS服务器超时设置\n"
    
    report_content += "=" * 70
    
    # 保存到文件的逻辑（如果配置了报告导出）
    if export_report_to_file:
        try:
            report_file_data = get_cross_border_report(result)
            report_file_data["test_type"] = "跨境链路专项测试"
            report_file_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 生成文件名
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cross_border_test_{timestamp_str}.json"
            
            export_report_to_file(report_file_data, filename)
            report_content += f"\n\n报告已保存到: {filename}"
        except Exception as e:
            report_content += f"\n\n报告保存失败: {str(e)}"
    
    return report_content