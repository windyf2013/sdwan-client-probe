"""
指标监控系统 - 严格遵循AI Agent Python工程标准

职责：统一管理应用性能指标、业务指标、健康度监控
禁止：裸指标调用、不可聚合的指标设计

文档编号: AAPS-001
规范等级: Mandatory（强制执行）
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Set
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

from ..infrastructure.config import get_config_manager
from ..observability.logger import get_logger

logger = get_logger(__name__)


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"      # 计数器（只增）
    GAUGE = "gauge"          # 标量（可增减）
    HISTOGRAM = "histogram"  # 直方图（适用于延迟等）
    SUMMARY = "summary"      # 摘要（预聚合统计）


class MetricUnit(Enum):
    """指标单位"""
    MILLISECONDS = "ms"
    SECONDS = "s"
    BYTES = "bytes"
    REQUESTS = "requests"
    ERRORS = "errors"
    PERCENT = "percent"
    COUNT = "count"


@dataclass
class MetricLabel:
    """指标标签"""
    name: str
    value: str


@dataclass
class MetricPoint:
    """指标数据点"""
    value: float
    timestamp: float
    labels: List[MetricLabel] = field(default_factory=list)


@dataclass
class MetricDefinition:
    """指标定义"""
    name: str
    metric_type: MetricType
    description: str
    unit: MetricUnit
    labels: List[str] = field(default_factory=list)
    aggregation_window: int = 60  # 聚合窗口（秒）
    retention_period: int = 3600  # 保留时间（秒）


class BaseMetric:
    """基础指标类"""
    
    def __init__(self, definition: MetricDefinition):
        self.definition = definition
        self._lock = threading.RLock()
        self._current_value: float = 0.0
        self._data_points: List[MetricPoint] = []
        self._last_update_time: float = 0.0
    
    def record(self, value: float, labels: Optional[List[MetricLabel]] = None) -> None:
        """记录指标值"""
        with self._lock:
            current_time = time.time()
            point_labels = labels or []
            
            # 验证标签
            self._validate_labels(point_labels)
            
            # 记录数据点
            point = MetricPoint(
                value=value,
                timestamp=current_time,
                labels=point_labels
            )
            self._data_points.append(point)
            
            # 更新当前值（根据指标类型）
            self._update_current_value(value)
            
            self._last_update_time = current_time
            
            # 清理过期数据
            self._clean_old_data()
    
    def get_current_value(self) -> float:
        """获取当前值"""
        with self._lock:
            return self._current_value
    
    def get_aggregated_data(self, window_seconds: Optional[int] = None) -> List[MetricPoint]:
        """获取聚合数据"""
        window = window_seconds or self.definition.aggregation_window
        cutoff_time = time.time() - window
        
        with self._lock:
            return [
                point for point in self._data_points
                if point.timestamp >= cutoff_time
            ]
    
    def get_statistics(self, window_seconds: Optional[int] = None) -> Dict[str, float]:
        """获取统计信息"""
        data_points = self.get_aggregated_data(window_seconds)
        
        if not data_points:
            return {}
        
        values = [point.value for point in data_points]
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "sum": sum(values),
            "avg": sum(values) / len(values)
        }
    
    def _validate_labels(self, labels: List[MetricLabel]) -> None:
        """验证标签"""
        label_names = {label.name for label in labels}
        defined_names = set(self.definition.labels)
        
        # 检查是否包含所有必需标签
        undefined_names = label_names - defined_names
        if undefined_names:
            raise ValueError(f"未定义的标签: {undefined_names}")
    
    def _update_current_value(self, value: float) -> None:
        """更新当前值（子类实现）"""
        pass
    
    def _clean_old_data(self) -> None:
        """清理过期数据"""
        cutoff_time = time.time() - self.definition.retention_period
        
        with self._lock:
            self._data_points = [
                point for point in self._data_points
                if point.timestamp >= cutoff_time
            ]


class CounterMetric(BaseMetric):
    """计数器指标"""
    
    def _update_current_value(self, value: float) -> None:
        """计数器只增不减"""
        if value < 0:
            raise ValueError("计数器不能记录负值")
        self._current_value += value


class GaugeMetric(BaseMetric):
    """标量指标"""
    
    def _update_current_value(self, value: float) -> None:
        """标量直接设置值"""
        self._current_value = value
    
    def increment(self, value: float = 1.0) -> None:
        """增加值"""
        with self._lock:
            self._current_value += value
            self.record(self._current_value)
    
    def decrement(self, value: float = 1.0) -> None:
        """减少值"""
        with self._lock:
            self._current_value -= value
            self.record(self._current_value)


class HistogramMetric(BaseMetric):
    """直方图指标"""
    
    def __init__(self, definition: MetricDefinition):
        super().__init__(definition)
        self._buckets: List[float] = [0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
    
    def _update_current_value(self, value: float) -> None:
        """直方图记录分布"""
        self._current_value = value  # 当前值设为最后记录的值
    
    def get_bucket_counts(self, window_seconds: Optional[int] = None) -> Dict[float, int]:
        """获取分桶计数"""
        data_points = self.get_aggregated_data(window_seconds)
        
        bucket_counts = {bucket: 0 for bucket in self._buckets}
        bucket_counts[float('inf')] = 0  # 无限桶
        
        for point in data_points:
            value = point.value
            
            # 找到对应的桶
            bucket_found = False
            for bucket in sorted(self._buckets):
                if value <= bucket:
                    bucket_counts[bucket] += 1
                    bucket_found = True
                    break
            
            if not bucket_found:
                bucket_counts[float('inf')] += 1
        
        return bucket_counts


class MetricsRegistry:
    """指标注册表"""
    
    def __init__(self):
        self._metrics: Dict[str, BaseMetric] = {}
        self._lock = threading.RLock()
        self._config_manager = get_config_manager()
        self._enabled = self._config_manager.get("enable_metrics", True)
    
    def register_metric(self, definition: MetricDefinition) -> BaseMetric:
        """注册指标"""
        if not self._enabled:
            return DummyMetric(definition)
        
        with self._lock:
            if definition.name in self._metrics:
                logger.warning(f"指标已存在: {definition.name}")
                return self._metrics[definition.name]
            
            # 根据类型创建指标实例
            metric_class = self._get_metric_class(definition.metric_type)
            metric = metric_class(definition)
            
            self._metrics[definition.name] = metric
            logger.info(f"注册指标: {definition.name}")
            
            return metric
    
    def get_metric(self, name: str) -> Optional[BaseMetric]:
        """获取指标"""
        with self._lock:
            return self._metrics.get(name)
    
    def list_metrics(self) -> List[MetricDefinition]:
        """列出所有指标"""
        with self._lock:
            return [metric.definition for metric in self._metrics.values()]
    
    def get_metric_data(self, name: str, window_seconds: Optional[int] = None) -> Dict[str, Any]:
        """获取指标数据"""
        metric = self.get_metric(name)
        if not metric:
            return {}
        
        return {
            "definition": {
                "name": metric.definition.name,
                "type": metric.definition.metric_type.value,
                "description": metric.definition.description,
                "unit": metric.definition.unit.value
            },
            "current_value": metric.get_current_value(),
            "statistics": metric.get_statistics(window_seconds),
            "recent_data": [
                {
                    "value": point.value,
                    "timestamp": point.timestamp,
                    "labels": {label.name: label.value for label in point.labels}
                }
                for point in metric.get_aggregated_data(window_seconds)
            ]
        }
    
    def _get_metric_class(self, metric_type: MetricType) -> type:
        """根据类型获取指标类"""
        metric_classes = {
            MetricType.COUNTER: CounterMetric,
            MetricType.GAUGE: GaugeMetric,
            MetricType.HISTOGRAM: HistogramMetric,
            MetricType.SUMMARY: BaseMetric  # 简化实现
        }
        return metric_classes.get(metric_type, BaseMetric)


class DummyMetric(BaseMetric):
    """虚拟指标（当指标禁用时使用）"""
    
    def record(self, value: float, labels: Optional[List[MetricLabel]] = None) -> None:
        """不执行任何操作"""
        pass
    
    def get_current_value(self) -> float:
        return 0.0
    
    def get_aggregated_data(self, window_seconds: Optional[int] = None) -> List[MetricPoint]:
        return []
    
    def get_statistics(self, window_seconds: Optional[int] = None) -> Dict[str, float]:
        return {}


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        self.registry = MetricsRegistry()
        self._setup_core_metrics()
    
    def _setup_core_metrics(self) -> None:
        """设置核心指标"""
        # 工具执行指标
        self.registry.register_metric(MetricDefinition(
            name="tool_execution_count",
            metric_type=MetricType.COUNTER,
            description="工具执行次数",
            unit=MetricUnit.REQUESTS,
            labels=["tool_name", "status"]
        ))
        
        self.registry.register_metric(MetricDefinition(
            name="tool_execution_duration",
            metric_type=MetricType.HISTOGRAM,
            description="工具执行耗时",
            unit=MetricUnit.MILLISECONDS,
            labels=["tool_name"]
        ))
        
        self.registry.register_metric(MetricDefinition(
            name="tool_execution_errors",
            metric_type=MetricType.COUNTER,
            description="工具执行错误次数",
            unit=MetricUnit.ERRORS,
            labels=["tool_name", "error_type"]
        ))
        
        # 系统资源指标
        self.registry.register_metric(MetricDefinition(
            name="memory_usage",
            metric_type=MetricType.GAUGE,
            description="内存使用量",
            unit=MetricUnit.BYTES
        ))
        
        self.registry.register_metric(MetricDefinition(
            name="cpu_usage",
            metric_type=MetricType.GAUGE,
            description="CPU使用率",
            unit=MetricUnit.PERCENT
        ))
        
        # 请求指标
        self.registry.register_metric(MetricDefinition(
            name="http_requests_total",
            metric_type=MetricType.COUNTER,
            description="HTTP请求总数",
            unit=MetricUnit.REQUESTS,
            labels=["method", "status", "path"]
        ))
    
    def record_tool_execution(self, tool_name: str, duration: float, success: bool) -> None:
        """记录工具执行指标"""
        # 执行次数
        count_metric = self.registry.get_metric("tool_execution_count")
        if count_metric:
            status = "success" if success else "failure"
            labels = [
                MetricLabel("tool_name", tool_name),
                MetricLabel("status", status)
            ]
            count_metric.record(1, labels)
        
        # 执行耗时
        if duration > 0:
            duration_metric = self.registry.get_metric("tool_execution_duration")
            if duration_metric:
                labels = [MetricLabel("tool_name", tool_name)]
                duration_metric.record(duration * 1000, labels)  # 转换为毫秒
    
    def record_tool_error(self, tool_name: str, error_type: str) -> None:
        """记录工具执行错误"""
        error_metric = self.registry.get_metric("tool_execution_errors")
        if error_metric:
            labels = [
                MetricLabel("tool_name", tool_name),
                MetricLabel("error_type", error_type)
            ]
            error_metric.record(1, labels)
    
    def collect_system_metrics(self) -> None:
        """收集系统指标"""
        try:
            import psutil
            
            # 内存使用
            memory_metric = self.registry.get_metric("memory_usage")
            if memory_metric:
                memory_metric.record(psutil.virtual_memory().used)
            
            # CPU使用率
            cpu_metric = self.registry.get_metric("cpu_usage")
            if cpu_metric:
                cpu_metric.record(psutil.cpu_percent())
                
        except ImportError:
            logger.warning("psutil模块未安装，无法收集系统指标")


# 全局指标收集器实例
_metrics_collector_instance: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器实例"""
    global _metrics_collector_instance
    if _metrics_collector_instance is None:
        _metrics_collector_instance = MetricsCollector()
    return _metrics_collector_instance


def record_tool_metrics(tool_name: str, duration: float, success: bool) -> None:
    """记录工具指标"""
    collector = get_metrics_collector()
    collector.record_tool_execution(tool_name, duration, success)
    
    if not success:
        collector.record_tool_error(tool_name, "execution_failed")


# 装饰器：自动记录函数执行指标
def measure_execution_time(metric_name: str):
    """测量函数执行时间的装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # 记录指标
                record_tool_metrics(metric_name, duration, True)
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                # 记录错误指标
                collector = get_metrics_collector()
                collector.record_tool_error(metric_name, type(e).__name__)
                
                raise
        
        return wrapper
    return decorator