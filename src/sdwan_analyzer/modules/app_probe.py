import subprocess

from sdwan_analyzer.models.diagnose import AppProbeResult
from sdwan_analyzer.utils.logger import get_logger

# 获取日志记录器
logger = get_logger('app_probe_test')

def tcping(target: str, port: int = 443, timeout: int = 2) -> bool:
    """执行TCP端口测试"""
    logger.info(f"开始TCP端口测试: 目标={target}, 端口={port}, 超时={timeout}秒")
    try:
        cmd = f"""
        $client = New-Object System.Net.Sockets.TcpClient;
        $task = $client.ConnectAsync("{target}", {port});
        $success = $task.Wait({timeout * 1000});
        $client.Close();
        if ($success) {{ exit 0 }} else {{ exit 1 }}
        """
        logger.info(f"执行PowerShell命令: {cmd}")
        ret = subprocess.run(
            ["powershell", "-Command", cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        result = ret.returncode == 0
        logger.info(f"TCP端口测试结果: {result}, 返回码: {ret.returncode}")
        return result
    except Exception as e:
        logger.error(f"TCP端口测试失败: {e}")
        return False

def http_probe(target: str) -> bool:
    """执行HTTP探测"""
    logger.info(f"开始HTTP探测: 目标={target}")
    try:
        cmd = f"""
        $url = "https://{target}";
        try {{ 
            $req = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3;
            exit 0
        }} catch {{ 
            exit 1 
        }}
        """
        logger.info(f"执行PowerShell命令: {cmd}")
        ret = subprocess.run(
            ["powershell", "-Command", cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        result = ret.returncode == 0
        logger.info(f"HTTP探测结果: {result}, 返回码: {ret.returncode}")
        return result
    except Exception as e:
        logger.error(f"HTTP探测失败: {e}")
        return False

def detect_mtu(target: str, retries: int = 2) -> int:
    """
    检测MTU值
    :param target: 目标地址
    :param retries: 每个MTU值的重试次数，防止网络抖动导致误判
    :return: 检测到的最大MTU值
    """
    logger.info(f"开始MTU检测: 目标={target}, 重试次数={retries}")
    
    # 定义搜索范围
    # 最小MTU通常为576 (IPv4最小重组缓冲区大小)，最大通常为1500 (以太网标准MTU)
    min_mtu = 576
    max_mtu = 1500
    
    low = min_mtu
    high = max_mtu
    best_mtu = min_mtu  # 初始化为最小安全值，避免全失败时返回错误的大值
    
    logger.info(f"MTU搜索范围: [{low}, {high}]")
    
    while low <= high:
        mid = (low + high) // 2
        # ping -l 指定的是数据部分大小，需要减去 IP头(20) + ICMP头(8) = 28字节
        payload_size = mid - 28
        
        # 确保 payload_size 不为负数（虽然 mid >= 576 时不会发生）
        if payload_size < 0:
            payload_size = 0
            
        logger.debug(f"二分查找状态: low={low}, high={high}, mid(MTU)={mid}, payload={payload_size}")
        
        success = False
        for attempt in range(1, retries + 1):
            try:
                # Windows ping 命令:
                # -f: 设置不分片标志 (Do Not Fragment)
                # -n 1: 发送1个回显请求
                # -w 500: 超时时间500毫秒
                # -l: 数据部分大小
                args = ["ping", "-f", "-n", "1", "-w", "500", "-l", str(payload_size), target]
                
                logger.debug(f"执行Ping测试 (尝试 {attempt}/{retries}): {' '.join(args)}")
                
                ret = subprocess.run(
                    args,
                    stdout=subprocess.PIPE, # 捕获输出以便调试时可查看
                    stderr=subprocess.PIPE,
                    timeout=2 # 增加subprocess层面的超时保护
                )
                
                # returncode 0 表示成功收到回复
                if ret.returncode == 0:
                    success = True
                    logger.debug(f"Ping测试成功 (MTU={mid}, payload={payload_size})")
                    break # 只要成功一次，就认为该MTU可用
                else:
                    logger.debug(f"Ping测试失败 (MTU={mid}, payload={payload_size}), 返回码: {ret.returncode}")
                    
            except subprocess.TimeoutExpired:
                logger.warning(f"Ping测试超时 (MTU={mid}, payload={payload_size})")
            except Exception as e:
                logger.warning(f"Ping测试异常 (MTU={mid}, payload={payload_size}): {e}")
        
        if success:
            best_mtu = mid
            logger.info(f"MTU {mid} 测试通过 (payload={payload_size})，尝试更大值")
            low = mid + 1
        else:
            logger.info(f"MTU {mid} 测试失败 (payload={payload_size})，尝试更小值")
            high = mid - 1
            
    logger.info(f"MTU检测完成: 目标={target}, 最佳MTU={best_mtu}")
    return best_mtu

def run_app_probe(target: str, port: int = 443) -> AppProbeResult:
    """执行应用层探测"""
    logger.info(f"开始应用层探测: 目标={target}, 端口={port}")
    
    tcp_ok = tcping(target, port)
    http_ok = http_probe(target)
    mtu = detect_mtu(target)
    mtu_normal = mtu >= 1400

    result = AppProbeResult(
        target=target,
        tcp_port=port,
        tcp_open=tcp_ok,
        http_available=http_ok,
        detected_mtu=mtu,
        mtu_normal=mtu_normal
    )
    
    logger.info(f"应用层探测完成: {result}")
    return result