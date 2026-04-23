# d:/AI/testing/proj5/sdwan_analyzer/src/sdwan_analyzer/models/diagnose.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import uuid

@dataclass
class PingResult:
    target: str
    sent: int = 0
    received: int = 0
    loss: float = 0.0
    min_rtt: float = 0.0
    avg_rtt: float = 0.0
    max_rtt: float = 0.0
    jitter: float = 0.0
    is_success: bool = False
    packet_status: list[str] = field(default_factory=list)
            
    @property
    def is_reachable(self):
        return self.is_success

@dataclass
class TracertHop:
    hop: int
    ip: str
    timeout: bool

@dataclass
class MtrResult:
    target: str
    hops: list[TracertHop]
    is_cross_border: bool = False
    problem_hop: str = ""
    has_error: bool = False
    output: list[str] = field(default_factory=list)

@dataclass
class NicInfo:
    """系统诊断用的网卡信息 (简化版)"""
    index: int
    name: str
    status: str
    ip: list[str]
    gateway: list[str]
    dns: list[str]
    is_dhcp: bool

@dataclass
class NicDetail:
    """本地配置检测用的网卡详细信息 (完整版)"""
    name: str = ""
    description: str = ""
    ip_addresses: List[str] = field(default_factory=list)
    gateways: List[str] = field(default_factory=list)
    dns_servers: List[str] = field(default_factory=list)
    mac_address: str = ""
    status: str = "Unknown" 
    is_primary: bool = False 

@dataclass
class SystemDiagnoseResult:
    """系统网络环境就绪检查结果"""
    nic: Optional[NicInfo] = None
    default_route_valid: bool = False      
    gateway_reachable: bool = False        
    dns_working: bool = False              
    
    # --- 环境干扰项检测 ---
    firewall_enabled: bool = False         
    proxy_enabled: bool = False            
    proxy_server: str = ""                 
    
    all_ok: bool = False                   

@dataclass
class LocalConfigCheckResult:
    """本地网络配置合理性检查结果"""
    # 识别到的主网卡信息
    primary_nic: Optional[NicDetail] = None
    all_nics: List[NicDetail] = field(default_factory=list)
    
    # 各模块配置状态 (简化存储，详细问题在 issues 中)
    proxy_enabled: bool = False
    firewall_enabled: bool = False
    has_multiple_gateways: bool = False
    dns_config_reasonable: bool = True
    
    # MTU 探测结果
    mtu_detected: int = 1500
    mtu_is_optimal: bool = True
    
    # 汇总问题
    issues: List[dict] = field(default_factory=list) 
    config_score: float = 100.0

@dataclass
class NetworkContext:
    """网络上下文特征"""
    is_behind_nat: bool = False
    has_multiple_gateways: bool = False
    note: str = ""

@dataclass
class AppProbeResult:
    target: str
    tcp_port: int = 443
    tcp_open: bool = False
    http_available: bool = False
    detected_mtu: int = 1500
    mtu_normal: bool = True

@dataclass
class Issue:
    """诊断发现的问题"""
    level: str = "info"  
    category: str = ""   
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@dataclass
class FinalReport:
    """最终诊断报告"""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    target: str = ""
    
    # 原始检测结果引用
    system: Optional[SystemDiagnoseResult] = None
    local_config: Optional[LocalConfigCheckResult] = None 
    network_context: Optional[NetworkContext] = None      

    # 业务测试结果
    app_probes: List[AppProbeResult] = field(default_factory=list)
    cross_border_results: dict = field(default_factory=dict)
    
    # 评分与结论
    overall_score: float = 100.0
    environment_score: float = 100.0 
    connectivity_score: float = 100.0 
    conclusion: str = "正常"
    
    issues: List[Issue] = field(default_factory=list)
    all_ok: bool = True

    def add_issue(self, level: str, category: str, message: str):
        self.issues.append(Issue(level=level, category=category, message=message))
        if level == "error":
            self.all_ok = False
            self.overall_score -= 20
        elif level == "warning":
            self.overall_score -= 10
        self.overall_score = max(0, self.overall_score)
        

@dataclass
class NetworkInterface:
    """统一的网络接口模型 - 仅包含基础网络配置信息"""
    name: str
    description: str
    mac_address: str
    ip_addresses: List[str] = field(default_factory=list)
    subnet_masks: List[str] = field(default_factory=list)  # 【新增】子网掩码列表
    gateways: List[str] = field(default_factory=list)
    dns_servers: List[str] = field(default_factory=list)
    is_dhcp: bool = False
    status: str = "Unknown"   # Connected, Disconnected, Unknown
    is_primary: bool = False  # 是否被识别为主网卡
    mtu: int = 1500

@dataclass
class SystemEnvironmentResult:
    """合并后的系统环境与配置结果"""
    # 1. 静态配置信息 (Static Config)
    interfaces: List[NetworkInterface] = field(default_factory=list)
    primary_interface: Optional[NetworkInterface] = None
    
    proxy_enabled: bool = False
    proxy_server: str = ""
    firewall_enabled: bool = False
    has_multiple_gateways: bool = False
    
    # 2. 动态连通性结果 (Dynamic Connectivity)
    default_route_exists: bool = False
    gateway_reachable: bool = False
    dns_resolution_working: bool = False
    
    # 3. 路由信息 (Routing Information) - 新增字段，确保JSON报告完整路由信息
    routing_information: Dict = field(default_factory=dict)
    
    # 4. 综合评分与建议
    config_score: float = 100.0
    issues: List[Issue] = field(default_factory=list)
    
    @property
    def is_healthy(self) -> bool:
        return len([i for i in self.issues if i.level == 'error']) == 0