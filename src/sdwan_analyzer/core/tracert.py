import sys
import subprocess

from sdwan_analyzer.config import TRACERT_TIMEOUT
from sdwan_analyzer.models.diagnose import MtrResult
from sdwan_analyzer.utils.logger import get_logger

# 获取日志记录器
logger = get_logger('tracert_test')

def run_tracert(target: str, timeout: int = TRACERT_TIMEOUT) -> MtrResult:
    """执行traceroute测试"""
    hops = []
    output_lines = []

    logger.info(f"开始Traceroute测试: 目标={target}, 超时={timeout}秒")

    if sys.platform.lower() == "win32":
        try:
            args = ["tracert", "-d", "-w", "1000", target]
            logger.info(f"执行命令: {' '.join(args)}")
            
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                bufsize=1
            )

            logger.info("开始读取traceroute输出...")
            for line in iter(proc.stdout.readline, ""):
                line = line.rstrip()
                if line:
                    output_lines.append(line)
                    logger.info(f"Traceroute输出: {line}")
                    print(line)

            logger.info("等待traceroute命令完成...")
            proc.wait(timeout=timeout)
            logger.info(f"Traceroute命令完成，返回码: {proc.returncode}")
            
            result = MtrResult(target=target, hops=hops, has_error=False, output=output_lines)
            logger.info(f"返回结果: {result}")
            return result

        except Exception as e:
            logger.error(f"Traceroute执行失败: {e}")
            result = MtrResult(target=target, hops=[], has_error=True, output=[f"执行失败: {str(e)}"])
            logger.info(f"返回结果: {result}")
            return result

    # Linux 保留 traceroute
    else:
        logger.warning("不支持的平台")
        result = MtrResult(target=target, hops=[], has_error=True, output=["不支持的平台"])
        logger.info(f"返回结果: {result}")
        return result