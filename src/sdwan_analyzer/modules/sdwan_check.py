import subprocess
import re

from sdwan_analyzer.config import IPSEC_PORTS
from sdwan_analyzer.models.diagnose import SDWANCheckResult
from sdwan_analyzer.utils.logger import get_logger

# 获取日志记录器
logger = get_logger('sdwan_check')

def check_sdwan_features(cpe_ip: str) -> SDWANCheckResult:
    """检查SD-WAN特征"""
    logger.info(f"开始SD-WAN特征检查: CPE IP={cpe_ip}")
    res = SDWANCheckResult()
    res.cpe_ip = cpe_ip

    # 1. 网关是否可通
    logger.info("检查CPE可达性...")
    res.cpe_reachable = ping_target(cpe_ip)
    logger.info(f"CPE可达: {res.cpe_reachable}")

    # 2. 是否多默认网关
    logger.info("检查多默认网关...")
    res.is_multi_gateway = detect_multi_default_gateway()
    logger.info(f"多默认网关: {res.is_multi_gateway}")

    # 3. 探测 IPSec 端口（500/4500/1701）
    logger.info("探测IPSec端口...")
    res.ipsec_port_open, res.open_ports = detect_ipsec_ports(cpe_ip)
    logger.info(f"IPSec端口开放: {res.ipsec_port_open}, 开放端口: {res.open_ports}")

    # 4. 策略路由
    logger.info("检查策略路由...")
    res.has_policy_route = detect_real_sdwan_policy_routes()
    logger.info(f"存在策略路由: {res.has_policy_route}")

    # 5. SD-WAN 综合判定
    res.is_likely_sdwan_enabled = (
        res.cpe_reachable and
        (res.ipsec_port_open or res.is_multi_gateway or res.has_policy_route)
    )
    logger.info(f"SD-WAN启用: {res.is_likely_sdwan_enabled}")

    # 6. 评分
    score = 0
    if res.cpe_reachable:
        score += 40
        logger.info("+40分: CPE可达")
    if res.ipsec_port_open:
        score += 30
        logger.info("+30分: IPSec端口开放")
    if res.has_policy_route:
        score += 15
        logger.info("+15分: 存在策略路由")
    if res.is_multi_gateway:
        score += 15
        logger.info("+15分: 多默认网关")
    res.sdwan_health_score = min(score, 100)
    logger.info(f"SD-WAN健康评分: {res.sdwan_health_score} / 100")

    logger.info(f"SD-WAN特征检查完成: {res}")
    return res

# ------------------------------
# 工具函数
# ------------------------------
def ping_target(ip: str) -> bool:
    """Ping目标IP"""
    if not ip:
        logger.warning("目标IP为空")
        return False
    try:
        args = ["ping", "-n", "1", "-w", "600", ip]
        logger.info(f"执行ping命令: {' '.join(args)}")
        ret = subprocess.run(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        result = ret.returncode == 0
        logger.info(f"ping结果: {result}, 返回码: {ret.returncode}")
        return result
    except Exception as e:
        logger.error(f"ping失败: {e}")
        return False

def detect_ipsec_ports(ip: str):
    """检测IPSec端口"""
    if not ip:
        logger.warning("目标IP为空")
        return False, []
    open_ports = []
    ports = IPSEC_PORTS
    logger.info(f"检测IPSec端口: {ports}")
    for p in ports:
        try:
            cmd = f'''
            $client = New-Object System.Net.Sockets.UdpClient;
            $client.Send((New-Object byte[] 1), 1, "{ip}", {p});
            Start-Sleep -Milliseconds 200;
            $client.Close();
            '''
            logger.info(f"检测端口 {p}...")
            subprocess.run(
                ["powershell", "-Command", cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1
            )
            open_ports.append(p)
            logger.info(f"端口 {p} 开放")
        except Exception as e:
            logger.warning(f"端口 {p} 关闭或检测失败: {e}")
            continue
    result = len(open_ports) > 0
    logger.info(f"IPSec端口检测完成: 开放端口={open_ports}, 结果={result}")
    return result, open_ports

def detect_multi_default_gateway() -> bool:
    """检测多默认网关"""
    try:
        args = ["route", "print", "0.0.0.0"]
        logger.info(f"执行命令: {' '.join(args)}")
        out = subprocess.check_output(
            args, text=True, encoding="gbk", errors="ignore"
        )
        lines = [
            l for l in out.splitlines()
            if l.strip() and "0.0.0.0" in l and "255.0.0.0" in l
        ]
        logger.info(f"找到 {len(lines)} 条默认路由")
        result = len(lines) >= 2
        logger.info(f"多默认网关: {result}")
        return result
    except Exception as e:
        logger.error(f"检测多默认网关失败: {e}")
        return False

def detect_real_sdwan_policy_routes() -> bool:
    """检测策略路由"""
    try:
        args = ["route", "print"]
        logger.info(f"执行命令: {' '.join(args)}")
        out = subprocess.check_output(
            args, text=True, encoding="gbk", errors="ignore"
        )
        count = 0
        for line in out.splitlines():
            line = line.strip()
            if re.match(r'^(10\.|172\.1[6-9]\.|172\.2[0-9]\.|172\.3[0-1]\.|192\.168\.)', line):
                count += 1
                logger.info(f"找到私有IP路由: {line}")
                if count >= 2:
                    logger.info("找到至少2条私有IP路由，存在策略路由")
                    return True
        logger.info(f"只找到 {count} 条私有IP路由，不存在策略路由")
        return False
    except Exception as e:
        logger.error(f"检测策略路由失败: {e}")
        return False