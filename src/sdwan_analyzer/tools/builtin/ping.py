"""
网络Ping工具 - 严格遵循AI Agent Python工程标准

职责：实现ICMP Ping功能，封装低层网络操作的复杂性
禁止：直接访问网络socket、裸ping调用、状态泄漏

文档编号: AAPS-001
规范等级: Mandatory（强制执行）
"""

import asyncio
import subprocess
import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from statistics import mean

from ...core.contracts import ToolRequest, ToolResponse
from ...core.types import StandardErrors
from ...observability.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class PingConfig:
    """Ping配置"""
    timeout_seconds: int = 10
    packet_size: int = 56
    interval_seconds: float = 0.2
    ttl: int = 64


@dataclass(slots=True)
class PingResult:
    """Ping结果"""
    target: str
    packets_sent: int = 0
    packets_received: int = 0
    packet_loss: float = 0.0
    min_rtt: float = 0.0
    max_rtt: float = 0.0
    avg_rtt: float = 0.0
    stddev_rtt: float = 0.0  # 标准偏差
    round_trips: List[float] = field(default_factory=list)  # 所有往返时间
    success: bool = False
    error_message: Optional[str] = None
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.packets_sent == 0:
            return 0.0
        return self.packets_received / self.packets_sent * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "target": self.target,
            "packets_sent": self.packets_sent,
            "packets_received": self.packets_received,
            "packet_loss": round(self.packet_loss, 2),
            "min_rtt": round(self.min_rtt, 2),
            "max_rtt": round(self.max_rtt, 2),
            "avg_rtt": round(self.avg_rtt, 2),
            "stddev_rtt": round(self.stddev_rtt, 2),
            "success_rate": round(self.success_rate, 2),
            "success": self.success,
            "error_message": self.error_message,
            "total_round_trips": len(self.round_trips)
        }


class PingTool:
    """Ping工具实现类"""
    
    def __init__(self, config: Optional[PingConfig] = None):
        self.config = config or PingConfig()
        
    async def ping_async_target(self, target: str, count: int = 4) -> PingResult:
        """异步Ping目标（支持Windows/Linux）"""
        logger.info(f"开始Ping测试: {target}, 次数: {count}")
        
        # 验证目标地址
        if not await self._validate_target(target):
            result = PingResult(target=target, success=False)
            result.error_message = "目标地址无效或无法解析"
            return result
        
        try:
            if self._is_windows():
                return await self._ping_windows(target, count)
            else:
                return await self._ping_linux(target, count)
        except Exception as e:
            logger.error(f"Ping执行失败: {e}")
            result = PingResult(target=target, success=False)
            result.error_message = f"Ping执行异常: {str(e)}"
            return result
    
    async def _validate_target(self, target: str) -> bool:
        """验证目标地址"""
        # 基本格式验证
        if not target or len(target.strip()) == 0:
            return False
        
        # IPv4地址格式
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if re.match(ipv4_pattern, target):
            parts = target.split('.')
            if all(0 <= int(part) <= 255 for part in parts):
                return True
            return False
        
        # 主机名格式（简化验证）
        hostname_pattern = r'^[a-zA-Z0-9.-]+$'
        if re.match(hostname_pattern, target):
            return True
        
        # IPv6地址（简化验证）
        if ':' in target:
            return True
        
        return False
    
    def _is_windows(self) -> bool:
        """判断当前系统是否为Windows"""
        import platform
        return platform.system().lower() == 'windows'
    
    async def _ping_windows(self, target: str, count: int) -> PingResult:
        """Windows系统Ping实现"""
        result = PingResult(target=target)
        
        # 构建ping命令
        cmd = [
            "ping", "-n", str(count),  # Windows使用-n参数
            "-l", str(self.config.packet_size),
            "-i", str(self.config.ttl),
            target
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.config.timeout_seconds
            )
            
            if process.returncode != 0:
                result.success = False
                result.error_message = f"Ping命令执行失败，返回码: {process.returncode}"
                return result
            
            output = stdout.decode('utf-8', errors='ignore')
            return self._parse_windows_output(output, result)
            
        except asyncio.TimeoutError:
            result.success = False
            result.error_message = "Ping操作超时"
            return result
        except Exception as e:
            result.success = False
            result.error_message = f"Ping执行异常: {str(e)}"
            return result
    
    async def _ping_linux(self, target: str, count: int) -> PingResult:
        """Linux系统Ping实现"""
        result = PingResult(target=target)
        
        # 构建ping命令
        cmd = [
            "ping", "-c", str(count),  # Linux使用-c参数
            "-s", str(self.config.packet_size),
            "-t", str(self.config.ttl),
            "-i", str(self.config.interval_seconds),
            target
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.config.timeout_seconds
            )
            
            if process.returncode != 0:
                result.success = False
                result.error_message = f"Ping命令执行失败，返回码: {process.returncode}"
                return result
            
            output = stdout.decode('utf-8', errors='ignore')
            return self._parse_linux_output(output, result)
            
        except asyncio.TimeoutError:
            result.success = False
            result.error_message = "Ping操作超时"
            return result
        except Exception as e:
            result.success = False
            result.error_message = f"Ping执行异常: {str(e)}"
            return result
    
    def _parse_windows_output(self, output: str, result: PingResult) -> PingResult:
        """解析Windows ping输出"""
        lines = output.split('\n')
        
        # 查找统计信息
        stats_pattern = r'数据包: 发送 = (\d+), 接收 = (\d+), 丢失 = (\d+)'
        rtt_pattern = r'最短 = (\d+)ms, 最长 = (\d+)ms, 平均 = (\d+)ms'
        
        for line in lines:
            # 数据包统计
            match = re.search(stats_pattern, line)
            if match:
                result.packets_sent = int(match.group(1))
                result.packets_received = int(match.group(2))
                result.packet_loss = (int(match.group(3)) / result.packets_sent) * 100 if result.packets_sent > 0 else 100.0
            
            # 延迟统计
            match = re.search(rtt_pattern, line)
            if match:
                result.min_rtt = float(match.group(1))
                result.max_rtt = float(match.group(2))
                result.avg_rtt = float(match.group(3))
        
        # 解析每行回复的时间
        time_pattern = r'来自 .+ 的回复: 字节=(\d+) 时间=([<>]*(\d+)ms) TTL=\d+'
        for line in lines:
            match = re.search(time_pattern, line)
            if match:
                time_str = match.group(2)
                if '<' in time_str or '>' in time_str:
                    # 处理<1ms之类的特殊格式
                    time_value = 0.5  # 近似值
                else:
                    time_value = float(match.group(3))
                result.round_trips.append(time_value)
        
        # 计算标准偏差
        if result.round_trips:
            result.stddev_rtt = self._calculate_stddev(result.round_trips)
        
        result.success = result.packets_received > 0
        return result
    
    def _parse_linux_output(self, output: str, result: PingResult) -> PingResult:
        """解析Linux ping输出"""
        lines = output.split('\n')
        
        # 查找统计信息
        stats_pattern = r'(\d+) packets transmitted, (\d+) received'
        loss_pattern = r'(\d+\.?\d*)% packet loss'
        rtt_pattern = r'min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms'
        
        for line in lines:
            # 数据包统计
            match = re.search(stats_pattern, line)
            if match:
                result.packets_sent = int(match.group(1))
                result.packets_received = int(match.group(2))
            
            # 丢包率
            match = re.search(loss_pattern, line)
            if match:
                result.packet_loss = float(match.group(1))
            
            # 延迟统计
            match = re.search(rtt_pattern, line)
            if match:
                result.min_rtt = float(match.group(1))
                result.avg_rtt = float(match.group(2))
                result.max_rtt = float(match.group(3))
                result.stddev_rtt = float(match.group(4))
        
        # 解析每行的时间
        time_pattern = r'icmp_seq=\d+ ttl=\d+ time=([\d.]+) ms'
        for line in lines:
            match = re.search(time_pattern, line)
            if match:
                result.round_trips.append(float(match.group(1)))
        
        result.success = result.packets_received > 0
        return result
    
    def _calculate_stddev(self, data: List[float]) -> float:
        """计算标准偏差"""
        if len(data) < 2:
            return 0.0
        
        avg = mean(data)
        variance = sum((x - avg) ** 2 for x in data) / len(data)
        return variance ** 0.5


async def ping_tool_executor(request: ToolRequest) -> ToolResponse:
    """Ping工具执行器 - 供调度器调用"""
    logger.debug(f"执行Ping工具: {request.parameters}")
    
    # 参数提取和验证
    target = request.parameters.get("target", "")
    count = request.parameters.get("count", 4)
    
    if not target:
        return ToolResponse.error(
            tool_name="ping_tool",
            error=StandardErrors.INVALID_PARAMETER.create_with_details(
                message="目标地址不能为空",
                details={"valid_targets": ["IP地址", "域名"]}
            )
        )
    
    if not isinstance(count, int) or count < 1 or count > 100:
        return ToolResponse.error(
            tool_name="ping_tool",
            error=StandardErrors.INVALID_PARAMETER.create_with_details(
                message=f"Ping次数必须在1-100之间，当前: {count}",
                details={"min": 1, "max": 100}
            )
        )
    
    try:
        # 执行Ping
        ping_tool = PingTool()
        result = await ping_tool.ping_async_target(target, count)
        
        response_data = {
            "success": result.success,
            "ping_result": result.to_dict(),
            "diagnostic": {
                "target_resolved": result.success,
                "connectivity_type": "ICMP",
                "timestamp": asyncio.get_event_loop().time()
            }
        }
        
        return ToolResponse(
            tool_name="ping_tool",
            result=response_data,
            execution_status="SUCCESS" if result.success else "PARTIAL_SUCCESS",
            metadata={
                "packets_sent": result.packets_sent,
                "packets_received": result.packets_received,
                "packet_loss": result.packet_loss,
                "avg_latency_ms": result.avg_rtt
            }
        )
        
    except Exception as e:
        logger.error(f"Ping工具执行异常: {e}", exc_info=True)
        return ToolResponse.error(
            tool_name="ping_tool",
            error=StandardErrors.INTERNAL_ERROR.create_with_details(
                message=f"Ping执行失败: {str(e)}",
                details={"target": target, "count": count}
            )
        )