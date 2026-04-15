import subprocess
import re

from sdwan_analyzer.config import MTR_COUNT, MTR_TIMEOUT
from sdwan_analyzer.core.tracert import run_tracert
from sdwan_analyzer.models.diagnose import MtrResult
from sdwan_analyzer.utils.logger import get_logger

# 获取日志记录器
logger = get_logger('mtr_test')

class MtrHop:
    """MTR跳数信息"""
    def __init__(self, hop: int, ip: str, loss: float, avg_rtt: float):
        self.hop = hop
        self.ip = ip
        self.loss = loss
        self.avg_rtt = avg_rtt

def run_mtr(target: str, count: int = MTR_COUNT, timeout: int = MTR_TIMEOUT) -> MtrResult:
    """执行MTR测试（基于ping实现）"""
    hops = []
    output_lines = []
    hop_data = {}

    logger.info(f"开始MTR测试: 目标={target}, 每个跳点ping次数={count}, 超时={timeout}秒")

    # 首先执行一次traceroute获取路径
    logger.info("执行traceroute获取路径...")
    tracert_result = run_tracert(target, timeout=timeout/2)
    if tracert_result.has_error:
        logger.error(f"Traceroute执行失败: {tracert_result.output}")
        result = MtrResult(target=target, hops=[], has_error=True, output=tracert_result.output)
        logger.info(f"返回结果: {result}")
        return result

    # 解析traceroute结果获取跳点
    logger.info("解析traceroute结果获取跳点...")
    for line in tracert_result.output:
        # 匹配跳点行，例如：1    <1 ms    <1 ms    <1 ms  192.168.1.1
        match = re.match(r'^\s*(\d+)\s+.*?(\d+\.\d+\.\d+\.\d+)', line)
        if match:
            hop = int(match.group(1))
            ip = match.group(2)
            hop_data[hop] = ip
            logger.info(f"发现跳点 {hop}: {ip}")

    if not hop_data:
        logger.warning("未发现跳点")
        result = MtrResult(target=target, hops=[], has_error=True, output=["未发现跳点"])
        logger.info(f"返回结果: {result}")
        return result

    # 对每个跳点执行多次ping获取统计信息
    logger.info(f"开始对每个跳点执行{count}次ping...")
    print(f"\n开始MTR测试，对每个跳点执行{count}次ping...")
    for hop, ip in hop_data.items():
        logger.info(f"测试跳点 {hop}: {ip}")
        print(f"\n跳点 {hop}: {ip}")
        sent = 0
        received = 0
        rtts = []
        
        for i in range(count):
            sent += 1
            logger.info(f"执行第 {i+1}/{count} 次ping到 {ip}")
            try:
                args = ["ping", "-n", "1", "-w", "1000", ip]
                logger.info(f"执行命令: {' '.join(args)}")
                proc = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                output = proc.communicate(timeout=1.5)[0]
                
                # 解析ping结果
                rtt_match = re.search(r'时间=(\d+)ms', output)
                if rtt_match:
                    rtt = int(rtt_match.group(1))
                    rtts.append(rtt)
                    received += 1
                    logger.info(f"ping成功: 时间={rtt}ms")
                    print(f"  ping {i+1}/{count}: {rtt}ms")
                else:
                    logger.warning(f"ping超时")
                    print(f"  ping {i+1}/{count}: 超时")
            except Exception as e:
                logger.warning(f"ping失败: {e}")
                print(f"  ping {i+1}/{count}: 超时")
        
        # 计算统计信息
        if rtts:
            loss = ((sent - received) / sent) * 100
            avg_rtt = sum(rtts) / len(rtts)
            min_rtt = min(rtts)
            max_rtt = max(rtts)
            logger.info(f"跳点 {hop} 统计: 发送={sent}, 接收={received}, 丢失={loss:.1f}%, 平均延迟={avg_rtt:.1f}ms, 最小={min_rtt}ms, 最大={max_rtt}ms")
            print(f"  统计: 发送={sent}, 接收={received}, 丢失={loss:.1f}%, 平均延迟={avg_rtt:.1f}ms")
            output_lines.append(f"跳点 {hop}: {ip} - 丢失={loss:.1f}%, 平均延迟={avg_rtt:.1f}ms")
        else:
            logger.info(f"跳点 {hop} 统计: 发送={sent}, 接收={received}, 丢失=100.0%, 平均延迟=N/A")
            print(f"  统计: 发送={sent}, 接收={received}, 丢失=100.0%, 平均延迟=N/A")
            output_lines.append(f"跳点 {hop}: {ip} - 丢失=100.0%, 平均延迟=N/A")

    logger.info("MTR测试完成")
    result = MtrResult(target=target, hops=[], has_error=False, output=output_lines)
    logger.info(f"返回结果: {result}")
    return result