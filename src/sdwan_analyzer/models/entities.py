from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class BusinessType(str, Enum):
    DOMESTIC = "domestic"
    CROSS_BORDER = "cross_border"
    UNKNOWN = "unknown"

class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class PingResult:
    is_success: bool = False
    avg_rtt: float = 0.0
    loss: float = 0.0
    sent: int = 0
    received: int = 0
    min_rtt: float = 0.0
    max_rtt: float = 0.0

@dataclass
class AppProbeResult:
    tcp_open: bool = False
    http_available: bool = False
    detected_mtu: int = 1500
    mtu_normal: bool = True
    response_time: float = 0.0

@dataclass
class LinkQualityResult:
    """深度链路检测结果"""
    overall_score: float = 100.0
    jitter: float = 0.0
    packet_loss: float = 0.0
    route_hops: int = 0
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Issue:
    level: str  # error, warning, info
    category: str
    message: str
    suggestion: str = ""

@dataclass
class UnifiedTargetResult:
    """统一的目标检测结果模型 - 核心载体"""
    target: str
    business_type: BusinessType = BusinessType.UNKNOWN
    priority: Priority = Priority.MEDIUM
    
    # 基础检测结果（快速）
    ping_result: Optional[PingResult] = None
    app_probe_result: Optional[AppProbeResult] = None
    basic_reachable: bool = False
    
    # 深度检测结果（按需）
    link_quality: Optional[LinkQualityResult] = None
    needs_deep_check: bool = False
    deep_check_completed: bool = False
    
    # 综合状态
    issues: List[Issue] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def add_issue(self, level: str, category: str, message: str, suggestion: str = ""):
        self.issues.append(Issue(level=level, category=category, message=message, suggestion=suggestion))