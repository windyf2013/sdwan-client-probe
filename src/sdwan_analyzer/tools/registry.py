"""
工具注册表 - 严格遵循AI Agent Python工程标准Tool Registry

职责：统一注册工具元数据、版本、schema、权限标签
禁止：工具直接耦合业务逻辑

文档编号: AAPS-001
规范等级: Mandatory（强制执行）
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Type, Callable
import importlib

from ..core.contracts import ToolRequest, ToolResponse, BaseError
from ..core.types import StandardErrors
from ..observability.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class ToolMetadata:
    """工具元数据"""
    name: str  # 工具名称
    version: str = "1.0.0"
    description: str = ""
    author: str = "system"
    timeout_seconds: int = 30
    retry_policy: Dict[str, Any] = field(default_factory=lambda: {"max_attempts": 3, "backoff_seconds": 1.0})
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    

@dataclass(slots=True)
class ToolEntry:
    """工具注册项"""
    metadata: ToolMetadata
    implementation: Callable[[Dict[str, Any]], Dict[str, Any]]
    module_path: str  # 工具实现的模块路径
    

class ToolRegistry:
    """工具注册表 - 统一管理所有工具"""
    
    def __init__(self):
        self._registry: Dict[str, ToolEntry] = {}
        self._initialized = False
    
    def initialize(self) -> None:
        """初始化注册表，加载所有可用工具"""
        if self._initialized:
            return
        
        logger.info("初始化工具注册表")
        
        # 注册内置工具
        self._register_builtin_tools()
        
        # 注册适配器工具
        self._register_adapter_tools()
        
        self._initialized = True
        logger.info(f"工具注册表初始化完成，注册工具数: {len(self._registry)}")
    
    def register_tool(self, metadata: ToolMetadata, implementation: Callable, module_path: str) -> None:
        """注册工具"""
        if metadata.name in self._registry:
            logger.warning(f"工具 {metadata.name} 已存在，将被覆盖")
        
        entry = ToolEntry(metadata=metadata, implementation=implementation, module_path=module_path)
        self._registry[metadata.name] = entry
        
        logger.info(f"注册工具: {metadata.name} v{metadata.version}")
    
    def get_tool(self, tool_name: str) -> Optional[ToolEntry]:
        """获取工具"""
        if not self._initialized:
            self.initialize()
        
        return self._registry.get(tool_name)
    
    def list_tools(self) -> List[ToolMetadata]:
        """列出所有可用工具"""
        if not self._initialized:
            self.initialize()
        
        return [entry.metadata for entry in self._registry.values()]
    
    def validate_tool_request(self, tool_name: str, parameters: Dict[str, Any]) -> bool:
        """验证工具请求参数"""
        tool_entry = self.get_tool(tool_name)
        if not tool_entry:
            return False
        
        # 基本参数验证（实际应该更详细的schema验证）
        schema = tool_entry.metadata.input_schema
        if not schema:
            return True  # 没有schema则默认通过
        
        # 这里可以实现更复杂的schema验证逻辑
        return self._validate_against_schema(parameters, schema)
    
    def _validate_against_schema(self, parameters: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """根据schema验证参数"""
        # 简化的schema验证实现
        required_fields = schema.get("required", [])
        
        for field in required_fields:
            if field not in parameters:
                logger.error(f"缺失必需参数: {field}")
                return False
        
        return True
    
    def _register_builtin_tools(self) -> None:
        """注册内置工具"""
        # Ping工具
        self.register_tool(
            ToolMetadata(
                name="ping_tool",
                description="ICMP Ping检测工具",
                category="network",
                timeout_seconds=10,
                input_schema={
                    "required": ["target", "count"],
                    "properties": {
                        "target": {"type": "string", "description": "目标地址"},
                        "count": {"type": "integer", "minimum": 1, "maximum": 100}
                    }
                },
                tags=["icmp", "latency", "availability"]
            ),
            self._ping_tool_implementation,
            "sdwan_analyzer.tools.builtin.ping"
        )
        
        # DNS工具
        self.register_tool(
            ToolMetadata(
                name="dns_tool",
                description="DNS解析工具",
                category="network",
                timeout_seconds=5,
                input_schema={
                    "required": ["domain"],
                    "properties": {
                        "domain": {"type": "string", "description": "域名"},
                        "resolver": {"type": "string", "description": "DNS服务器"}
                    }
                },
                tags=["dns", "resolution"]
            ),
            self._dns_tool_implementation,
            "sdwan_analyzer.tools.builtin.dns"
        )
        
        # HTTP工具
        self.register_tool(
            ToolMetadata(
                name="http_tool",
                description="HTTP/HTTPS探测工具",
                category="application",
                timeout_seconds=15,
                input_schema={
                    "required": ["url"],
                    "properties": {
                        "url": {"type": "string", "description": "目标URL"},
                        "method": {"type": "string", "enum": ["GET", "POST", "HEAD"]}
                    }
                },
                tags=["http", "web", "api"]
            ),
            self._http_tool_implementation,
            "sdwan_analyzer.tools.builtin.http"
        )
        
        # TCP端口工具
        self.register_tool(
            ToolMetadata(
                name="tcp_tool",
                description="TCP端口检测工具",
                category="network",
                timeout_seconds=5,
                input_schema={
                    "required": ["target"],
                    "properties": {
                        "target": {"type": "string", "description": "目标地址"},
                        "ports": {"type": "array", "description": "端口列表"}
                    }
                },
                tags=["tcp", "ports", "connectivity"]
            ),
            self._tcp_tool_implementation,
            "sdwan_analyzer.tools.builtin.tcp"
        )
    
    def _register_adapter_tools(self) -> None:
        """注册适配器工具"""
        # 带宽测试工具
        self.register_tool(
            ToolMetadata(
                name="bandwidth_tester",
                description="网络带宽测试工具",
                category="performance",
                timeout_seconds=60,
                tags=["bandwidth", "performance"]
            ),
            self._bandwidth_tool_implementation,
            "sdwan_analyzer.tools.adapters.bandwidth"
        )
        
        # 延迟分析工具
        self.register_tool(
            ToolMetadata(
                name="latency_analyzer",
                description="网络延迟分析工具",
                category="performance",
                timeout_seconds=120,
                tags=["latency", "analysis"]
            ),
            self._latency_tool_implementation,
            "sdwan_analyzer.tools.adapters.latency"
        )
        
        # 路由追踪工具
        self.register_tool(
            ToolMetadata(
                name="traceroute_tool",
                description="网络路由追踪工具",
                category="network",
                timeout_seconds=180,
                tags=["traceroute", "routing"]
            ),
            self._traceroute_tool_implementation,
            "sdwan_analyzer.tools.adapters.traceroute"
        )
    
    # --- 工具实现 ---
    
    def _ping_tool_implementation(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Ping工具实现"""
        # 这里应该调用底层ping实现
        target = parameters.get("target", "")
        count = parameters.get("count", 4)
        
        # 实际实现应该调用具体的ping库
        # 这里返回示例数据
        return {
            "success": True,
            "target": target,
            "sent_packets": count,
            "received_packets": count,
            "avg_latency": 15.5,
            "packet_loss": 0.0
        }
    
    def _dns_tool_implementation(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """DNS工具实现"""
        domain = parameters.get("domain", "")
        
        # 实际实现应该调用具体的DNS库
        return {
            "success": True,
            "domain": domain,
            "resolved_ips": ["8.8.8.8", "8.8.4.4"],
            "resolver_used": "system_default"
        }
    
    def _http_tool_implementation(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """HTTP工具实现"""
        url = parameters.get("url", "")
        
        # 实际实现应该调用具体的HTTP库
        return {
            "success": True,
            "url": url,
            "status_code": 200,
            "response_time_ms": 150.2,
            "headers": {}
        }
    
    def _tcp_tool_implementation(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """TCP工具实现"""
        target = parameters.get("target", "")
        ports = parameters.get("ports", [80, 443])
        
        # 实际实现应该调用具体的TCP端口扫描
        port_status = {port: "open" for port in ports}
        
        return {
            "success": True,
            "target": target,
            "ports": port_status,
            "total_open": len(ports)
        }
    
    def _bandwidth_tool_implementation(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """带宽测试工具实现"""
        target = parameters.get("target", "")
        
        return {
            "success": True,
            "target": target,
            "download_speed_mbps": 45.2,
            "upload_speed_mbps": 23.1,
            "latency_ms": 25.3
        }
    
    def _latency_tool_implementation(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """延迟分析工具实现"""
        target = parameters.get("target", "")
        
        return {
            "success": True,
            "target": target,
            "avg_latency_ms": 28.5,
            "jitter_ms": 5.2,
            "packet_loss_percent": 0.1
        }
    
    def _traceroute_tool_implementation(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """路由追踪工具实现"""
        target = parameters.get("target", "")
        
        return {
            "success": True,
            "target": target,
            "hops": [
                {"ip": "192.168.1.1", "latency": 1.2},
                {"ip": "10.0.0.1", "latency": 5.8},
                {"ip": target, "latency": 28.5}
            ]
        }


# 全局工具注册表实例 - AAPS-001标准化单例模式
# 所有模块应使用这个全局实例以确保一致的工具管理
tool_registry = ToolRegistry()