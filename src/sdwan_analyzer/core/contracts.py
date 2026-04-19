"""
遵循AI Agent Python工程标准的核心数据契约定义

文档编号: AAPS-001
规范等级: Mandatory（强制执行）
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


# --- 基础契约基类 ---

def utc_now_iso() -> str:
    """获取当前UTC时间的ISO格式"""
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class BaseContract:
    """所有数据契约的基类 - 强制遵循AAPS-001规范"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=utc_now_iso)

    def to_json_dict(self) -> Dict[str, Any]:
        """转换为JSON字典 - 符合AAPS-001结构化契约要求"""
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
        }


# --- AI Agent标准化契约（强制） ---

@dataclass(slots=True)
class AgentInput(BaseContract):
    """AI Agent入口统一输入模型 - AAPS-001 2.1.1节要求"""
    # 必需参数必须在继承的可选参数之前
    target: str = ""  # 诊断目标（域名/IP）
    session_id: Optional[str] = None
    business_context: Optional[Dict[str, Any]] = field(default_factory=dict)
    priority: str = "normal"  # （low/normal/high）

    def validate(self) -> None:
        """输入验证前置条件"""
        if not self.target or self.target == "":
            raise ValidationError("诊断目标不能为空")
        if self.priority not in ["low", "normal", "high"]:
            raise ValidationError("优先级必须是low/normal/high")


@dataclass(slots=True)
class AgentOutput(BaseContract):
    """AI Agent统一输出模型 - AAPS-001 2.1.1节要求"""
    # 必需参数必须在所有可选参数之前
    success: bool = True
    result: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    execution_time_ms: int = 0


@dataclass(slots=True)
class Context(BaseContract):
    """运行时上下文对象 - AAPS-001 状态集中管理要求"""
    # 必需参数必须在所有可选参数之前
    session_id: str = ""
    user_id: Optional[str] = None
    platform: str = ""
    environment: Dict[str, Any] = field(default_factory=dict)
    
    # 流程状态 - 符合流程可编排原则
    current_steps: List[str] = field(default_factory=list)
    completed_steps: List[str] = field(default_factory=list)


@dataclass(slots=True)
class ToolRequest(BaseContract):
    """统一工具请求模型 - AAPS-001 工具系统规范"""
    # 必需参数必须在所有可选参数之前
    tool_name: str = ""  # 工具名称
    operation: str = ""  # 操作类型
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 30


@dataclass(slots=True)
class ToolResponse(BaseContract):
    """统一工具响应模型 - AAPS-001 工具系统规范"""
    # 必需参数必须在所有可选参数之前
    success: bool = True
    data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    execution_time_ms: int = 0


# 兼容现有工具系统的数据结构
@dataclass(slots=True)
class ToolInput:
    """工具输入模型 - 兼容现有工具接口"""
    parameters: Dict[str, Any] = field(default_factory=dict)
    context: Optional[Dict[str, Any]] = None


@dataclass(slots=True)
class ToolOutput:
    """工具输出模型 - 兼容现有工具接口"""
    success: bool = True
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: int = 0


@dataclass(slots=True)
class FlowState(BaseContract):
    """流程执行状态 - AAPS-001 2.3节流程规范"""
    current_step: str = ""
    step_history: List[Dict[str, Any]] = field(default_factory=list)
    context_snapshot: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending/running/completed/failed


# --- 网络诊断领域模型（适应现有规范但遵循AAPS-001） ---

@dataclass(slots=True)
class ProbeResult(BaseContract):
    """网络探测结果 - 结合现有规范创建兼容版本"""
    # 必需参数必须在所有可选参数之前
    probe_id: str = ""
    target: str = ""
    protocol: str = "icmp"  # icmp|tcp|dns|http|ssh|telnet
    status: str = "pending"  # pending/success/failure/timeout
    latency_ms: Optional[float] = None
    packet_loss: Optional[float] = None
    raw_output: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FlowRecord(BaseContract):
    """网络流记录"""
    # 必需参数必须在所有可选参数之前
    flow_id: str = ""
    src_ip: str = ""
    dst_ip: str = ""
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    protocol: str = "tcp"  # tcp|udp|icmp
    latency_ms: Optional[float] = None
    retransmissions: int = 0
    loss_rate: float = 0.0


@dataclass(slots=True)
class DiagnosisResult(BaseContract):
    """诊断结果 - 证据驱动诊断模型"""
    # 必需参数必须在所有可选参数之前
    diagnosis_id: str = ""
    root_cause: str = ""
    confidence: float = 0.0
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)


# --- 错误模型（AAPS-001 2.5节要求） ---

class BaseError(Exception):
    """基础错误类 - AAPS-001错误体系规范"""
    
    def __init__(self, error_code: str, message: str, context: dict, trace_id: str):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.context = context
        self.trace_id = trace_id


class ValidationError(BaseError):
    """校验错误"""
    pass


class ToolError(BaseError):
    """工具调用错误"""
    pass


class FlowError(BaseError):
    """流程编排错误"""
    pass


class TimeoutError(BaseError):
    """超时错误"""
    pass