"""
结构化日志系统 - 严格遵循AI Agent Python工程标准

职责：统一管理可观测性日志、指标、追踪信息
禁止：直接print、裸logging调用、不可追踪的日志消息

文档编号: AAPS-001
规范等级: Mandatory（强制执行）
"""

import logging
import json
import time
import sys
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, List, Union
from enum import Enum

from ..infrastructure.config import ConfigManager, get_config_manager


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogContext:
    """日志上下文"""
    trace_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    flow_id: Optional[str] = None
    step_id: Optional[str] = None
    client_ip: Optional[str] = None
    request_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class LogRecord:
    """结构化日志记录"""
    timestamp: float
    level: str
    logger: str
    message: str
    event: Optional[str] = None
    context: Optional[LogContext] = None
    extra: Optional[Dict[str, Any]] = None
    exception: Optional[str] = None
    stack_trace: Optional[str] = None
    duration: Optional[float] = None  # 操作耗时（秒）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为JSON可序列化字典"""
        result = {
            "timestamp": self.timestamp,
            "level": self.level,
            "logger": self.logger,
            "message": self.message,
            "timestamp_iso": self._format_timestamp(),
        }
        
        if self.event:
            result["event"] = self.event
        
        if self.context:
            result["context"] = self.context.to_dict()
        
        if self.extra:
            result["extra"] = self.extra
        
        if self.exception:
            result["exception"] = self.exception
        
        if self.stack_trace:
            result["stack_trace"] = self.stack_trace
        
        if self.duration is not None:
            result["duration_ms"] = round(self.duration * 1000, 2)
        
        return result
    
    def _format_timestamp(self) -> str:
        """格式化时间戳为ISO格式"""
        import datetime
        return datetime.datetime.fromtimestamp(self.timestamp).isoformat()


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    def __init__(self, format_type: str = "json"):
        super().__init__()
        self.format_type = format_type
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        # 提取结构化数据
        context = getattr(record, 'context', None)
        extra = getattr(record, 'extra', {})
        event = getattr(record, 'event', None)
        duration = getattr(record, 'duration', None)
        
        # 构建日志记录
        log_record = LogRecord(
            timestamp=record.created,
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
            event=event,
            context=context,
            extra=extra,
            duration=duration
        )
        
        # 异常信息
        if record.exc_info:
            exception_type, exception_value, tb = record.exc_info
            if exception_type:
                log_record.exception = f"{exception_type.__name__}: {exception_value}"
                
                # 简化的堆栈跟踪（避免过多细节）
                if tb:
                    import traceback
                    tb_text = ''.join(traceback.format_tb(tb))
                    log_record.stack_trace = tb_text
        
        if self.format_type == "json":
            return json.dumps(log_record.to_dict(), ensure_ascii=False)
        else:
            return self._format_text(log_record)
    
    def _format_text(self, record: LogRecord) -> str:
        """格式化文本日志"""
        parts = [
            f"[{record.timestamp_iso}]",
            f"{record.level:8}",
            f"{record.logger}",
            f"{record.message}"
        ]
        
        if record.event:
            parts.append(f"event={record.event}")
        
        if record.context:
            context_str = ' '.join([f"{k}={v}" for k, v in record.context.to_dict().items()])
            parts.append(f"ctx:{context_str}")
        
        if record.extra:
            extra_str = ' '.join([f"{k}={v}" for k, v in record.extra.items()])
            parts.append(f"extra:{extra_str}")
        
        if record.duration is not None:
            parts.append(f"duration={record.duration_ms}ms")
        
        return ' '.join(parts)


class ContextAwareLogger(logging.Logger):
    """上下文感知的日志记录器"""
    
    def __init__(self, name: str, level=logging.NOTSET):
        super().__init__(name, level)
        self._context = LogContext()
    
    def set_context(self, context: LogContext) -> None:
        """设置日志上下文"""
        self._context = context
    
    def update_context(self, **kwargs) -> None:
        """更新日志上下文"""
        for key, value in kwargs.items():
            if hasattr(self._context, key):
                setattr(self._context, key, value)
    
    def clear_context(self) -> None:
        """清除日志上下文"""
        self._context = LogContext()
    
    def _log_with_context(
        self,
        level: int,
        msg: str,
        args: tuple,
        exc_info=None,
        extra: Optional[Dict[str, Any]] = None,
        event: Optional[str] = None,
        duration: Optional[float] = None,
        **kwargs
    ) -> None:
        """带上下文的日志记录"""
        if extra is None:
            extra = {}
        
        # 添加上下文信息
        extra['context'] = self._context
        if event:
            extra['event'] = event
        if duration is not None:
            extra['duration'] = duration
        
        super()._log(level, msg, args, exc_info, extra, **kwargs)
    
    def debug(
        self,
        msg: str,
        *args: Any,
        event: Optional[str] = None,
        duration: Optional[float] = None,
        **kwargs: Any
    ) -> None:
        """调试级别日志"""
        if self.isEnabledFor(logging.DEBUG):
            self._log_with_context(
                logging.DEBUG, msg, args, event=event, duration=duration, **kwargs
            )
    
    def info(
        self,
        msg: str,
        *args: Any,
        event: Optional[str] = None,
        duration: Optional[float] = None,
        **kwargs: Any
    ) -> None:
        """信息级别日志"""
        if self.isEnabledFor(logging.INFO):
            self._log_with_context(
                logging.INFO, msg, args, event=event, duration=duration, **kwargs
            )
    
    def warning(
        self,
        msg: str,
        *args: Any,
        event: Optional[str] = None,
        duration: Optional[float] = None,
        **kwargs: Any
    ) -> None:
        """警告级别日志"""
        if self.isEnabledFor(logging.WARNING):
            self._log_with_context(
                logging.WARNING, msg, args, event=event, duration=duration, **kwargs
            )
    
    def error(
        self,
        msg: str,
        *args: Any,
        event: Optional[str] = None,
        duration: Optional[float] = None,
        exc_info=None,
        **kwargs: Any
    ) -> None:
        """错误级别日志"""
        if self.isEnabledFor(logging.ERROR):
            self._log_with_context(
                logging.ERROR, msg, args, exc_info=exc_info, 
                event=event, duration=duration, **kwargs
            )
    
    def critical(
        self,
        msg: str,
        *args: Any,
        event: Optional[str] = None,
        duration: Optional[float] = None,
        **kwargs: Any
    ) -> None:
        """严重级别日志"""
        if self.isEnabledFor(logging.CRITICAL):
            self._log_with_context(
                logging.CRITICAL, msg, args, event=event, duration=duration, **kwargs
            )


class LoggerFactory:
    """日志记录器工厂"""
    
    def __init__(self):
        self._config_manager = get_config_manager()
        self._initialized = False
    
    def initialize(self) -> None:
        """初始化日志系统"""
        if self._initialized:
            return
        
        # 配置日志级别
        log_level = self._config_manager.get("log_level", "INFO")
        log_format = self._config_manager.get("log_format", "json")
        
        # 设置根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))
        
        # 添加控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        formatter = StructuredFormatter(log_format)
        console_handler.setFormatter(formatter)
        
        # 清除现有处理器，添加新的
        root_logger.handlers.clear()
        root_logger.addHandler(console_handler)
        
        # 设置日志记录器类
        logging.setLoggerClass(ContextAwareLogger)
        
        self._initialized = True
    
    def get_logger(self, name: str) -> ContextAwareLogger:
        """获取日志记录器"""
        if not self._initialized:
            self.initialize()
        
        logger = logging.getLogger(name)
        return logger  # type: ignore
    
    def set_global_context(self, **context_kwargs) -> None:
        """设置全局日志上下文"""
        # 为所有现有记录器设置上下文
        for logger_name, logger in logging.Logger.manager.loggerDict.items():
            if isinstance(logger, ContextAwareLogger):
                logger.update_context(**context_kwargs)


# 全局日志工厂实例
_logger_factory_instance: Optional[LoggerFactory] = None


def get_logger_factory() -> LoggerFactory:
    """获取全局日志工厂实例"""
    global _logger_factory_instance
    if _logger_factory_instance is None:
        _logger_factory_instance = LoggerFactory()
    return _logger_factory_instance


def get_logger(name: str) -> ContextAwareLogger:
    """获取日志记录器"""
    return get_logger_factory().get_logger(name)


def initialize_logging() -> None:
    """初始化日志系统"""
    get_logger_factory().initialize()


def set_global_log_context(**context_kwargs) -> None:
    """设置全局日志上下文"""
    get_logger_factory().set_global_context(**context_kwargs)


# 装饰器：自动添加函数执行时间日志
def log_execution_time(logger_name: str = None, level: LogLevel = LogLevel.DEBUG):
    """记录函数执行时间的装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger(logger_name or func.__module__)
            start_time = time.time()
            
            logger.debug(
                f"开始执行: {func.__name__}",
                event="function_start",
                extra={
                    "function_name": func.__name__,
                    "module": func.__module__
                }
            )
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                log_method = getattr(logger, level.value.lower())
                log_method(
                    f"完成执行: {func.__name__}",
                    event="function_complete",
                    duration=duration,
                    extra={
                        "function_name": func.__name__,
                        "duration_ms": round(duration * 1000, 2),
                        "success": True
                    }
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"执行失败: {func.__name__}",
                    event="function_failed",
                    duration=duration,
                    exc_info=True,
                    extra={
                        "function_name": func.__name__,
                        "duration_ms": round(duration * 1000, 2),
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                raise
        
        return wrapper
    return decorator