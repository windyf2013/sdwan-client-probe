# sdwan_analyzer/modules/cross_border_test.py
"""跨境链路专项测试模块 - 检测影响跨境业务的网络质量"""

import subprocess
import re
import time
import concurrent.futures
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# 假设这些模块存在，保持导入
from sdwan_analyzer.core.ping import ping_check
from sdwan_analyzer.utils.logger import get_logger

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
class CrossBorderTestResult:
    """跨境测试完整结果"""
    link_results: List[LinkQualityResult] = field(default_factory=list)
    overall_score: float = 0.0
    summary: str = ""


def measure_jitter(target: str, count: int = 4, timeout: int = 10) -> float:
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
        ping_result = ping_check(target)
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
    执行跨境链路专项测试 (并行优化版)
    :param targets: 测试目标列表
    :param max_workers: 最大并行线程数
    """
    test_result = CrossBorderTestResult()
    
    print("\n" + "=" * 60)
    print("🌏 跨境链路专项测试 (并行模式)")
    print("=" * 60)
    print(f"待测目标: {len(targets)} 个 | 并行线程: {max_workers}")
    print("-" * 60)
    
    start_time = time.time()
    completed_count = 0
    total_count = len(targets)
    
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
                status_icon = "✅" if link_result.stability_score >= 80 else ("⚠️" if link_result.stability_score >= 60 else "❌")
                print(f"[{completed_count}/{total_count}] {target:<25} | 评分: {link_result.stability_score:.1f} {status_icon} | 延迟: {link_result.avg_latency:.0f}ms")
                
            except concurrent.futures.TimeoutError:
                completed_count += 1
                print(f"[{completed_count}/{total_count}] {target:<25} | ❌ 任务超时")
                fail_result = LinkQualityResult(target=target, stability_score=0.0)
                fail_result.issues.append({"level": "error", "message": "测试任务超时"})
                results_map[target] = fail_result
            except Exception as e:
                completed_count += 1
                print(f"[{completed_count}/{total_count}] {target:<25} | ❌ 异常: {str(e)[:30]}")
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
    
    print("\n" + "=" * 60)
    print(f"⏱️ 测试总耗时: {duration:.2f} 秒")
    print(f"📊 整体稳定性评分: {test_result.overall_score:.1f}")
    print(f"📋 测试结论: {test_result.summary}")
    print("=" * 60)
    
    return test_result


def get_cross_border_report(test_result: CrossBorderTestResult) -> Dict:
    """生成跨境测试报告数据"""
    return {
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