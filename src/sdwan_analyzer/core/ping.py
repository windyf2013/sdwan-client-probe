import sys
import subprocess
import re

from sdwan_analyzer.config import PING_COUNT
from sdwan_analyzer.models.diagnose import PingResult
from sdwan_analyzer.utils.logger import get_logger

# 获取日志记录器
logger = get_logger('ping_test')

def ping_check(target: str, count: int = PING_COUNT, timeout_ms: int = 3000, 
               is_crossborder: bool = False) -> PingResult:
    """执行Ping测试并返回结果
    
    Args:
        target: 目标地址
        count: Ping次数 (默认: 4次)
        timeout_ms: Ping超时时间 (默认: 3000ms)
        is_crossborder: 是否为跨境链路测试 (默认: False)
    
    Returns:
        PingResult: Ping测试结果，当全部失败时is_success=False
    """
    
    # 智能超时设置: 跨境链路使用更宽松的超时
    if is_crossborder:
        timeout_ms = 5000  # 跨境链路5秒超时
        logger.info(f"跨境链路检测: 使用{timeout_ms}ms超时设置")
    elif 'youtube.com' in target.lower() or 'tiktok.com' in target.lower() or 'google.com' in target.lower():
        # 自动识别常见的跨境目标
        timeout_ms = 4000  # 常见跨境目标4秒超时
        logger.info(f"跨境目标检测({target}): 使用{timeout_ms}ms超时设置")
    times = []
    sent = 0
    received = 0
    target_ip = target
    ttl_values = []

    logger.info(f"开始Ping测试: 目标={target}, 次数={count}, 超时={timeout_ms}ms")

    # 首先获取目标的IP地址（快速探测，超时800ms）
    try:
        if sys.platform == "win32":
            args = ["ping", "-n", "1", "-w", str(timeout_ms), target]
        else:
            args = ["ping", "-c", "1", "-W", str(timeout_ms // 1000), target]
        logger.info(f"执行命令: {' '.join(args)}")
        output = subprocess.check_output(args, text=True, stderr=subprocess.STDOUT, timeout=10)
        # 提取IP地址
        ip_match = re.search(r"\[(\d+\.\d+\.\d+\.\d+)\]", output)
        if ip_match:
            target_ip = ip_match.group(1)
            logger.info(f"解析到目标IP: {target_ip}")
        # 提取TTL值
        ttl_match = re.search(r"TTL=(\d+)", output)
        if ttl_match:
            ttl_values.append(int(ttl_match.group(1)))
            logger.info(f"解析到TTL值: {ttl_match.group(1)}")
    except subprocess.TimeoutExpired:
        logger.warning(f"Ping目标IP解析超时: {target}")
        # 如果IP解析都超时，直接返回失败结果
        return PingResult(target=target, sent=0, received=0, loss=100.0, is_success=False)
    except Exception as e:
        logger.warning(f"获取目标IP失败: {e}")
        return PingResult(target=target, sent=0, received=0, loss=100.0, is_success=False)

    # 输出开始信息
    print(f"正在 Ping {target} [{target_ip}] 具有 32 字节的数据:")

    for i in range(1, count + 1):
        sent += 1
        logger.info(f"执行第 {i}/{count} 次Ping")
        try:
            if sys.platform == "win32":
                args = ["ping", "-n", "1", "-w", str(timeout_ms), target]
            else:
                args = ["ping", "-c", "1", "-W", str(timeout_ms // 1000), target]

            logger.info(f"执行命令: {' '.join(args)}")
            # 设置命令超时，避免任务卡死
            output = subprocess.check_output(args, text=True, stderr=subprocess.STDOUT, timeout=timeout_ms // 500 + 2)
            time_val = re.search(r"时间=(\d+)ms", output) or re.search(r"time=(\d+)ms", output)
            ttl_match = re.search(r"TTL=(\d+)", output)

            if time_val:
                t = int(time_val.group(1))
                times.append(t)
                received += 1
                ttl = ttl_match.group(1) if ttl_match else "45"  # 默认TTL值
                ttl_values.append(int(ttl))
                logger.info(f"Ping成功: 时间={t}ms, TTL={ttl}")
                print(f"来自 {target_ip} 的回复: 字节=32 时间={t}ms TTL={ttl}")
            else:
                logger.warning(f"Ping失败: 无时间信息")
                print(f"请求超时。")

        except Exception as e:
            logger.warning(f"Ping失败: {e}")
            print(f"请求超时。")

    loss = ((sent - received) / sent) * 100 if sent > 0 else 100
    logger.info(f"Ping测试完成: 发送={sent}, 接收={received}, 丢失率={loss:.1f}%")

    if not times:
        print(f"\n{target_ip} 的 Ping 统计信息:")
        print(f"    数据包: 已发送 = {sent}，已接收 = {received}，丢失 = {sent - received} ({loss:.0f}% 丢失)，")
        result = PingResult(target=target, sent=sent, received=received, loss=loss, is_success=False)
        logger.info(f"返回结果: {result}")
        return result

    min_rtt = min(times)
    avg_rtt = sum(times) / len(times)
    max_rtt = max(times)
    jitter = max_rtt - min_rtt

    logger.info(f"延迟统计: 最小={min_rtt}ms, 平均={avg_rtt:.1f}ms, 最大={max_rtt}ms, 抖动={jitter}ms")

    # 输出统计信息
    print(f"\n{target_ip} 的 Ping 统计信息:")
    print(f"    数据包: 已发送 = {sent}，已接收 = {received}，丢失 = {sent - received} ({loss:.0f}% 丢失)，")
    print("往返行程的估计时间(以毫秒为单位):")
    print(f"    最短 = {min_rtt}ms，最长 = {max_rtt}ms，平均 = {round(avg_rtt)}ms")

    result = PingResult(
        target=target, sent=sent, received=received,
        loss=round(loss,1), min_rtt=min_rtt, avg_rtt=round(avg_rtt,1),
        max_rtt=max_rtt, jitter=jitter, is_success=(loss < 100)
    )
    logger.info(f"返回结果: {result}")
    return result