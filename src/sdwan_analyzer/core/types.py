"""
核心类型系统 - 严格遵循AI Agent Python工程标准

文档编号: AAPS-001
规范等级: Mandatory（强制执行）
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict


# --- 业务类型枚举（结构化业务定义） ---

class BusinessType(str, Enum):
    """业务类型枚举 - 替代硬编码字符串"""
    DOMESTIC = "domestic"
    CROSS_BORDER = "cross_border"


class PriorityType(str, Enum):
    """优先级枚举"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class ProtocolType(str, Enum):
    """协议类型枚举"""
    ICMP = "icmp"
    TCP = "tcp"
    DNS = "dns"
    HTTP = "http"
    SSH = "ssh"
    TELNET = "telnet"


class StepStatus(str, Enum):
    """步骤状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# --- 精确的数据类型定义（避免Any类型） ---

@dataclass(slots=True)
class RetryPolicy:
    """重试策略配置"""
    max_attempts: int = 3
    backoff_seconds: float = 1.0
    exponential_backoff: bool = True


@dataclass(slots=True)
class TimeoutConfig:
    """超时配置"""
    timeout_seconds: int = 30
    connection_timeout_seconds: int = 10


@dataclass(slots=True)
class DetectionStrategy:
    """检测策略配置 - 结构化替代硬编码字典"""
    basic_checks: List[str] = field(default_factory=lambda: ["ping", "tcp", "dns"])
    deep_checks: Optional[List[str]] = None
    timeout_seconds: int = 30
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)


# --- 业务目标配置（结构化替代硬编码） ---

@dataclass(slots=True)
class BusinessTarget:
    """业务目标配置"""
    target: str
    business_type: BusinessType
    priority: PriorityType = PriorityType.NORMAL
    detection_strategy: Optional[DetectionStrategy] = None


@dataclass(slots=True)
class TargetConfig:
    """目标配置集合"""
    targets: List[BusinessTarget] = field(default_factory=list)
    
    def get_target_by_type(self, business_type: BusinessType) -> List[BusinessTarget]:
        """根据业务类型获取目标"""
        return [target for target in self.targets if target.business_type == business_type]


# --- 标准化常量定义 ---

class ToolCategory(str, Enum):
    """工具分类枚举 - 统一工具管理"""
    NETWORK = "network"
    PERFORMANCE = "performance"
    SECURITY = "security"
    DIAGNOSTIC = "diagnostic"
    APPLICATION = "application"
    GENERAL = "general"


class ExecutionResult:
    """执行结果类型"""
    pass


class ToolMetadata:
    """工具元数据类型"""
    def __init__(self, name, description, category, version, author, timeout, requires_permission, input_schema):
        self.name = name
        self.description = description
        self.category = category
        self.version = version
        self.author = author
        self.timeout = timeout
        self.requires_permission = requires_permission
        self.input_schema = input_schema


class StandardErrors:
    """标准化错误码 - AAPS-001 2.5节要求"""
    VAL_INVALID_TARGET = "VAL_001"
    VAL_INVALID_PRIORITY = "VAL_002"
    TOOL_TIMEOUT = "TOOL_001"
    TOOL_EXECUTION_FAILED = "TOOL_002"
    FLOW_STEP_FAILED = "FLOW_001"
    FLOW_BRANCH_ERROR = "FLOW_002"
    SYS_UNEXPECTED_ERROR = "SYS_001"


# --- 函数返回值类型定义（避免多态返回值） ---

@dataclass(slots=True)
class CheckResult:
    """检查结果统一类型"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    details: Optional[str] = None
    duration_ms: int = 0


@dataclass(slots=True)
class ValidationResult:
    """验证结果类型"""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)