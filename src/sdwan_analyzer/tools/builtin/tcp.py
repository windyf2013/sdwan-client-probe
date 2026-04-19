"""
TCP端口检测工具 - 严格遵循AI Agent Python工程标准

职责：实现TCP端口连通性检测，封装socket连接复杂性
禁止：直接连接操作、裸socket调用、连接状态泄漏

文档编号: AAPS-001
规范等级: Mandatory（强制执行）
"""

import asyncio
import socket
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

from ...core.contracts import ToolRequest, ToolResponse
from ...core.types import StandardErrors
from ...observability.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class TCPPortConfig:
    """TCP端口检测配置"""
    timeout_seconds: float = 5.0
    connection_timeout: float = 3.0
    max_concurrent_checks: int = 10


@dataclass(slots=True)
class TCPPortResult:
    """单端口检测结果"""
    port: int
    status: str  # 'open', 'closed', 'filtered', 'timeout', 'error'
    response_time_ms: float = 0.0
    error_message: Optional[str] = None
    banner: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "port": self.port,
            "status": self.status,
            "response_time_ms": round(self.response_time_ms, 2),
            "error_message": self.error_message,
            "banner_received": self.banner is not None
        }


@dataclass(slots=True)
class TCPProbeResult:
    """TCP探测结果"""
    target: str
    successful_checks: int = 0
    failed_checks: int = 0
    port_results: List[TCPPortResult] = field(default_factory=list)
    total_response_time_ms: float = 0.0
    success: bool = False
    error_message: Optional[str] = None
    
    @property
    def open_ports(self) -> List[int]:
        """获取开放的端口列表"""
        return [
            result.port for result in self.port_results 
            if result.status == 'open'
        ]
    
    @property
    def average_response_time(self) -> float:
        """平均响应时间"""
        valid_times = [
            result.response_time_ms for result in self.port_results 
            if result.response_time_ms > 0
        ]
        return sum(valid_times) / len(valid_times) if valid_times else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "target": self.target,
            "successful_checks": self.successful_checks,
            "failed_checks": self.failed_checks,
            "total_ports_checked": len(self.port_results),
            "open_ports": self.open_ports,
            "average_response_time_ms": round(self.average_response_time, 2),
            "success": self.success,
            "error_message": self.error_message,
            "detailed_results": [result.to_dict() for result in self.port_results]
        }


class TCPTool:
    """TCP工具实现类"""
    
    def __init__(self, config: Optional[TCPPortConfig] = None):
        self.config = config or TCPPortConfig()
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_checks)
    
    async def check_ports(
        self, 
        target: str, 
        ports: List[int],
        get_banner: bool = False
    ) -> TCPProbeResult:
        """异步检查多个端口"""
        logger.info(f"TCP端口扫描: {target}, 端口数: {len(ports)}")
        
        result = TCPProbeResult(target=target)
        
        # 验证目标地址
        if not await self._validate_target(target):
            result.error_message = "目标地址无效"
            result.success = False
            return result
        
        # 验证端口范围
        if not self._validate_ports(ports):
            result.error_message = "端口范围无效"
            result.success = False
            return result
        
        try:
            # 并发检查所有端口
            tasks = [
                self._check_single_port(target, port, get_banner)
                for port in ports
            ]
            
            port_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            for i, port_result in enumerate(port_results):
                port = ports[i]
                
                if isinstance(port_result, Exception):
                    # 处理异常结果
                    error_result = TCPPortResult(
                        port=port,
                        status="error",
                        error_message=str(port_result)
                    )
                    result.port_results.append(error_result)
                    result.failed_checks += 1
                else:
                    # 正常结果
                    result.port_results.append(port_result)
                    if port_result.status == "open":
                        result.successful_checks += 1
                    else:
                        result.failed_checks += 1
            
            result.success = result.successful_checks > 0
            result.total_response_time_ms = result.average_response_time
            
            logger.info(
                f"TCP端口扫描完成: {target}, "
                f"开放端口: {result.successful_checks}, "
                f"平均响应: {result.average_response_time:.2f}ms"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"TCP端口扫描失败: {e}")
            result.error_message = str(e)
            result.success = False
            return result
    
    async def _check_single_port(
        self, 
        target: str, 
        port: int, 
        get_banner: bool
    ) -> TCPPortResult:
        """检查单个端口"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # 使用线程池执行同步的socket操作
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._check_port_sync,
                target, port, get_banner
            )
            
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            result.response_time_ms = response_time
            
            return result
            
        except Exception as e:
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.warning(f"端口检查异常 {target}:{port}: {e}")
            
            return TCPPortResult(
                port=port,
                status="error",
                response_time_ms=response_time,
                error_message=str(e)
            )
    
    def _check_port_sync(self, target: str, port: int, get_banner: bool) -> TCPPortResult:
        """同步端口检查"""
        try:
            # 创建socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.config.connection_timeout)
            
            # 尝试连接
            try:
                sock.connect((target, port))
            except socket.timeout:
                return TCPPortResult(port=port, status="timeout")
            except ConnectionRefusedError:
                return TCPPortResult(port=port, status="closed")
            except OSError as e:
                if e.errno == 113:  # No route to host
                    return TCPPortResult(port=port, status="filtered")
                else:
                    raise
            
            # 连接成功
            banner = None
            if get_banner:
                try:
                    # 尝试接收banner（简单实现）
                    sock.settimeout(2.0)  # 减少banner获取的超时时间
                    banner_data = sock.recv(1024)
                    if banner_data:
                        banner = banner_data.decode('utf-8', errors='ignore').strip()
                except (socket.timeout, BlockingIOError):
                    # 没有banner或超时是可以接受的
                    pass
                except Exception:
                    # banner获取失败不影响端口状态判断
                    pass
            
            sock.close()
            
            return TCPPortResult(
                port=port,
                status="open",
                banner=banner
            )
            
        except Exception as e:
            return TCPPortResult(
                port=port,
                status="error",
                error_message=str(e)
            )
    
    async def _validate_target(self, target: str) -> bool:
        """验证目标地址"""
        if not target:
            return False
        
        # 尝试解析目标
        try:
            await asyncio.get_event_loop().getaddrinfo(
                target, None, family=socket.AF_UNSPEC
            )
            return True
        except socket.gaierror:
            return False
        except Exception:
            return False
    
    def _validate_ports(self, ports: List[int]) -> bool:
        """验证端口范围"""
        if not ports:
            return False
        
        for port in ports:
            if not isinstance(port, int) or port < 1 or port > 65535:
                return False
        
        return True
    
    def _get_common_ports(self) -> List[int]:
        """获取常见端口列表"""
        return [
            # Web服务
            80, 443, 8080, 8443,
            # SSH/Telnet
            22, 23,
            # 邮件
            25, 110, 143, 465, 587, 993, 995,
            # 数据库
            3306, 5432, 27017, 6379,
            # 文件传输
            21, 20, 69,
            # 其他常用
            53, 123, 161, 389, 636, 993, 995
        ]
    
    async def check_common_ports(self, target: str) -> TCPProbeResult:
        """检查常见端口"""
        common_ports = self._get_common_ports()
        return await self.check_ports(target, common_ports, get_banner=False)


async def tcp_tool_executor(request: ToolRequest) -> ToolResponse:
    """TCP工具执行器 - 供调度器调用"""
    logger.debug(f"执行TCP工具: {request.parameters}")
    
    # 参数提取和验证
    target = request.parameters.get("target", "")
    ports_param = request.parameters.get("ports", [])
    get_banner = request.parameters.get("get_banner", False)
    
    if not target:
        return ToolResponse.error(
            tool_name="tcp_tool",
            error=StandardErrors.INVALID_PARAMETER.create_with_details(
                message="目标地址不能为空",
                details={"valid_targets": ["IP地址", "主机名"]}
            )
        )
    
    # 处理端口参数
    ports = []
    if isinstance(ports_param, list) and ports_param:
        ports = [int(p) for p in ports_param if isinstance(p, (int, str)) and str(p).isdigit()]
    
    # 如果没有指定端口，使用常见端口
    if not ports:
        tcp_tool = TCPTool()
        ports = tcp_tool._get_common_ports()
    
    # 验证端口范围
    if not all(1 <= port <= 65535 for port in ports):
        return ToolResponse.error(
            tool_name="tcp_tool",
            error=StandardErrors.INVALID_PARAMETER.create_with_details(
                message="端口号必须在1-65535之间",
                details={"invalid_ports": [p for p in ports if not (1 <= p <= 65535)]}
            )
        )
    
    try:
        # 执行TCP端口检查
        tcp_tool = TCPTool()
        result = await tcp_tool.check_ports(target, ports, get_banner)
        
        response_data = {
            "success": result.success,
            "tcp_result": result.to_dict(),
            "diagnostic": {
                "protocol": "TCP",
                "ports_checked": len(result.port_results),
                "timestamp": asyncio.get_event_loop().time()
            }
        }
        
        return ToolResponse(
            tool_name="tcp_tool",
            result=response_data,
            execution_status="SUCCESS" if result.success else "PARTIAL_SUCCESS",
            metadata={
                "target": target,
                "ports_checked": len(result.port_results),
                "open_ports": result.open_ports,
                "avg_response_time_ms": result.average_response_time
            }
        )
        
    except Exception as e:
        logger.error(f"TCP工具执行异常: {e}", exc_info=True)
        return ToolResponse.error(
            tool_name="tcp_tool",
            error=StandardErrors.INTERNAL_ERROR.create_with_details(
                message=f"TCP端口检查失败: {str(e)}",
                details={"target": target, "ports": ports}
            )
        )