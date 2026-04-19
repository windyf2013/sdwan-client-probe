"""
工具调度器 - 严格遵循AI Agent Python工程标准Tool Dispatcher

职责：统一调度工具执行、权限验证、负载管理、并发控制
禁止：工具直接调用、裸dict传参、状态泄漏

文档编号: AAPS-001
规范等级: Mandatory（强制执行）
"""

import asyncio
import concurrent.futures
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable, Tuple
from functools import wraps
import threading

from ..core.contracts import (
    BaseContract, BaseError, Context, ToolRequest, ToolResponse
)
from ..core.types import StandardErrors
from ..observability.logger import get_logger
from .registry import ToolRegistry, ToolEntry

logger = get_logger(__name__)


@dataclass(slots=True)
class ExecutionStats:
    """执行统计"""
    tool_name: str
    start_time: float
    end_time: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    
    @property
    def duration_ms(self) -> float:
        """计算执行时长（毫秒）"""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000


@dataclass(slots=True)
class RateLimiter:
    """速率限制器"""
    max_requests_per_minute: int = 60
    
    def __post_init__(self):
        self._lock = threading.RLock()
        self._requests: List[float] = []
        
    def can_execute(self) -> Tuple[bool, Optional[float]]:
        """检查是否可以执行（返回是否允许、等待秒数）"""
        with self._lock:
            now = time.time()
            one_minute_ago = now - 60
            
            # 清理过期请求
            self._requests = [req_time for req_time in self._requests if req_time > one_minute_ago]
            
            if len(self._requests) < self.max_requests_per_minute:
                self._requests.append(now)
                return True, None
            else:
                # 计算等待时间
                oldest_request = min(self._requests)
                wait_seconds = 60 - (now - oldest_request)
                return False, max(0.0, wait_seconds)


class ToolExecutionError(BaseError):
    """工具执行错误"""
    error_type = "TOOL_EXECUTION_ERROR"
    
    @classmethod
    def from_error(cls, tool_name: str, error: Exception) -> 'ToolExecutionError':
        """从异常创建错误"""
        return cls(
            code="TOOL_EXECUTION_ERROR",
            message=f"工具 {tool_name} 执行失败: {str(error)}",
            details={
                "tool_name": tool_name,
                "error_type": type(error).__name__,
                "error_message": str(error)
            }
        )


class ToolDispatcher:
    """工具调度器 - 统一调度工具执行"""
    
    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or ToolRegistry()
        self.rate_limiter = RateLimiter()
        self._execution_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=10,
            thread_name_prefix="tool_dispatch"
        )
        
        # 执行统计
        self._stats_lock = threading.RLock()
        self._execution_stats: List[ExecutionStats] = []
    
    async def dispatch_tool(
        self, 
        tool_request: ToolRequest, 
        context: Context
    ) -> ToolResponse:
        """调度工具执行 - 异步版本"""
        logger.info(
            f"调度工具执行: {tool_request.tool_name} "
            f"trace_id={context.trace_id}"
        )
        
        # 1. 参数验证
        validation_result = self._validate_tool_request(tool_request)
        if not validation_result[0]:
            return ToolResponse.error(
                tool_name=tool_request.tool_name,
                error=ToolExecutionError.create(
                    code="VALIDATION_ERROR",
                    message=f"工具请求验证失败: {validation_result[1]}",
                    details={"validation_errors": validation_result[2]}
                )
            )
        
        # 2. 权限验证
        if not await self._validate_permissions(tool_request, context):
            return ToolResponse.error(
                tool_name=tool_request.tool_name,
                error=ToolExecutionError.create(
                    code="PERMISSION_DENIED",
                    message=f"没有权限执行工具: {tool_request.tool_name}",
                    details={"user_id": context.user_id}
                )
            )
        
        # 3. 速率限制检查
        can_execute, wait_time = self.rate_limiter.can_execute()
        if not can_execute and wait_time > 0:
            logger.warning(f"速率限制触发，等待 {wait_time:.1f} 秒")
            await asyncio.sleep(wait_time)
        
        # 4. 同步执行（在异步上下文中运行同步代码）
        try:
            # 创建工作线程执行同步工具代码
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._execution_pool,
                self._execute_tool_sync,
                tool_request,
                context
            )
            return result
            
        except Exception as e:
            logger.error(f"工具调度异常: {e}", exc_info=True)
            return ToolResponse.error(
                tool_name=tool_request.tool_name,
                error=ToolExecutionError.from_error(tool_request.tool_name, e)
            )
    
    def _execute_tool_sync(self, tool_request: ToolRequest, context: Context) -> ToolResponse:
        """同步执行工具"""
        stats = ExecutionStats(
            tool_name=tool_request.tool_name,
            start_time=time.time()
        )
        
        try:
            # 获取工具
            tool_entry = self.registry.get_tool(tool_request.tool_name)
            if not tool_entry:
                raise ValueError(f"工具不存在: {tool_request.tool_name}")
            
            # 执行工具
            logger.debug(f"执行工具: {tool_request.tool_name}")
            
            raw_result = tool_entry.implementation(tool_request.parameters)
            
            # 转换为规范响应
            result = self._format_tool_result(raw_result, tool_entry)
            
            # 记录成功统计
            stats.end_time = time.time()
            stats.success = True
            
            logger.info(
                f"工具执行成功: {tool_request.tool_name} "
                f"duration={stats.duration_ms:.1f}ms"
            )
            
            return result
            
        except Exception as e:
            # 记录错误统计
            stats.end_time = time.time()
            stats.success = False
            stats.error = str(e)
            
            logger.error(f"工具执行失败: {tool_request.tool_name} - {e}", exc_info=True)
            
            return ToolResponse.error(
                tool_name=tool_request.tool_name,
                error=ToolExecutionError.from_error(tool_request.tool_name, e)
            )
            
        finally:
            # 保存执行统计
            self._record_execution_stats(stats)
    
    def _validate_tool_request(self, tool_request: ToolRequest) -> Tuple[bool, str, Dict[str, Any]]:
        """验证工具请求"""
        errors = {}
        
        # 检查工具是否存在
        if not self.registry.get_tool(tool_request.tool_name):
            return False, f"工具不存在: {tool_request.tool_name}", errors
        
        # 验证参数
        if not self.registry.validate_tool_request(tool_request.tool_name, tool_request.parameters):
            errors["parameter_validation"] = "参数验证失败"
            return False, "参数验证失败", errors
        
        return True, "OK", {}
    
    async def _validate_permissions(self, tool_request: ToolRequest, context: Context) -> bool:
        """验证权限（简化实现）"""
        # 简化的权限验证逻辑
        # 实际应该根据context.user_id、tool_category等进行验证
        tool_entry = self.registry.get_tool(tool_request.tool_name)
        if not tool_entry:
            return False
        
        # 权限分类
        protected_categories = ["admin", "system"]
        if tool_entry.metadata.category in protected_categories:
            # 需要管理员权限
            return context.user_id is not None  # 简化的权限检查
        
        return True
    
    def _format_tool_result(self, raw_result: Dict[str, Any], tool_entry: ToolEntry) -> ToolResponse:
        """格式化工具结果"""
        # 确保结果包含必需字段
        result = {
            "success": raw_result.get("success", True),
            "tool_name": tool_entry.metadata.name,
            "execution_time": raw_result.get("execution_time", time.time()),
            "data": raw_result
        }
        
        return ToolResponse(
            tool_name=tool_entry.metadata.name,
            result=result,
            execution_status="SUCCESS",
            metadata={
                "tool_version": tool_entry.metadata.version,
                "category": tool_entry.metadata.category
            }
        )
    
    def _record_execution_stats(self, stats: ExecutionStats) -> None:
        """记录执行统计"""
        with self._stats_lock:
            self._execution_stats.append(stats)
            
            # 限制统计记录数量
            if len(self._execution_stats) > 1000:
                self._execution_stats = self._execution_stats[-1000:]
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        with self._stats_lock:
            total_executions = len(self._execution_stats)
            successful_executions = len([s for s in self._execution_stats if s.success])
            
            avg_duration = 0.0
            if self._execution_stats:
                completed = [s for s in self._execution_stats if s.end_time is not None]
                if completed:
                    avg_duration = sum(s.duration_ms for s in completed) / len(completed)
            
            return {
                "total_executions": total_executions,
                "successful_executions": successful_executions,
                "failure_rate": (total_executions - successful_executions) / total_executions if total_executions > 0 else 0.0,
                "average_duration_ms": avg_duration,
                "recent_executions": self._execution_stats[-10:] if self._execution_stats else []
            }
    
    def shutdown(self) -> None:
        """关闭调度器"""
        logger.info("关闭工具调度器")
        self._execution_pool.shutdown(wait=True)
    
    def __del__(self):
        """析构函数，确保资源清理"""
        if hasattr(self, '_execution_pool'):
            self.shutdown()


# 装饰器：工具执行上下文管理
def with_dispatch_context(func: Callable):
    """工具执行上下文装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 添加上下文信息
        start_time = time.time()
        tool_name = func.__name__
        
        logger.info(f"开始执行工具: {tool_name}")
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            logger.info(f"工具执行完成: {tool_name}, 耗时: {duration:.3f}s")
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"工具执行失败: {tool_name}, 耗时: {duration:.3f}s, 错误: {e}")
            raise
    
    return wrapper


# 全局调度器实例
_dispatcher_instance: Optional[ToolDispatcher] = None


def get_dispatcher() -> ToolDispatcher:
    """获取全局调度器实例（单例模式）"""
    global _dispatcher_instance
    if _dispatcher_instance is None:
        _dispatcher_instance = ToolDispatcher()
    return _dispatcher_instance


async def dispatch_tool(tool_request: ToolRequest, context: Context) -> ToolResponse:
    """全局工具调度函数"""
    dispatcher = get_dispatcher()
    return await dispatcher.dispatch_tool(tool_request, context)