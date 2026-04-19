"""
诊断服务层 - 严格遵循AI Agent Python工程标准Service Layer

职责：实现领域业务能力，消费上下文与工具抽象结果，输出结构化业务结果
禁止：流程编排硬编码、基础设施细节耦合

文档编号: AAPS-001
规范等级: Mandatory（强制执行）
"""

from dataclasses import asdict
from typing import Dict, List, Optional

from ..core.contracts import AgentInput, Context, BaseError
from ..core.types import BusinessType, CheckResult
from ..tools.registry import ToolRegistry
from ..tools.dispatcher import ToolDispatcher
from ..observability.logger import get_logger

logger = get_logger(__name__)


class DiagnosticService:
    """诊断服务 - 纯业务逻辑，不处理流程编排和工具调用细节"""
    
    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry
        self.tool_dispatcher = ToolDispatcher(tool_registry)
    
    def perform_network_check(self, agent_input: AgentInput, context: Context) -> Dict:
        """执行网络检查 - 业务逻辑封装"""
        logger.info(f"执行网络检查", trace_id=agent_input.trace_id)
        
        target = agent_input.target
        results = []
        
        # 执行Ping检查（通过Tool Dispatcher）
        ping_result = self._execute_ping_check(target, context)
        if ping_result.success:
            results.append({"check": "ping", "status": "success", "latency": ping_result.data.get("latency")})
        else:
            results.append({"check": "ping", "status": "failed", "error": ping_result.error_message})
        
        # 执行DNS检查
        dns_result = self._execute_dns_check(target, context)
        if dns_result.success:
            results.append({"check": "dns", "status": "success", "resolved_ips": dns_result.data.get("ip_addresses")})
        else:
            results.append({"check": "dns", "status": "failed", "error": dns_result.error_message})
        
        # 执行TCP端口检查
        tcp_result = self._execute_tcp_check(target, context)
        if tcp_result.success:
            results.append({"check": "tcp", "status": "success", "port_status": tcp_result.data})
        else:
            results.append({"check": "tcp", "status": "failed", "error": tcp_result.error_message})
        
        return {
            "target": target,
            "check_type": "network",
            "results": results,
            "success_rate": len([r for r in results if r["status"] == "success"]) / len(results)
        }
    
    def perform_application_check(self, agent_input: AgentInput, context: Context) -> Dict:
        """执行应用层检查"""
        logger.info(f"执行应用层检查", trace_id=agent_input.trace_id)
        
        target = agent_input.target
        results = []
        
        # HTTP/HTTPS检查
        http_result = self._execute_http_check(target, context)
        if http_result.success:
            results.append({"check": "http", "status": "success", "status_code": http_result.data.get("status_code")})
        else:
            results.append({"check": "http", "status": "failed", "error": http_result.error_message})
        
        # SSL证书检查
        ssl_result = self._execute_ssl_check(target, context)
        if ssl_result.success:
            results.append({"check": "ssl", "status": "success", "cert_valid": ssl_result.data.get("valid")})
        else:
            results.append({"check": "ssl", "status": "failed", "error": ssl_result.error_message})
        
        return {
            "target": target,
            "check_type": "application",
            "results": results,
            "success_rate": len([r for r in results if r["status"] == "success"]) / len(results) if results else 0
        }
    
    def perform_overseas_check(self, agent_input: AgentInput, context: Context) -> Dict:
        """执行跨境检查 - 专门针对跨境场景的业务逻辑"""
        logger.info(f"执行跨境检查", trace_id=agent_input.trace_id)
        
        # 检查跨境DNS解析
        global_dns_result = self._execute_global_dns_check(agent_input.target, context)
        
        # 检查国际路由
        international_route_result = self._execute_international_route_check(agent_input.target, context)
        
        # 检查跨境带宽
        cross_border_bandwidth = self._execute_cross_border_bandwidth_check(agent_input.target, context)
        
        return {
            "target": agent_input.target,
            "check_type": "overseas",
            "dns_resolution": {"success": global_dns_result.success, "data": global_dns_result.data},
            "route_tracing": {"success": international_route_result.success, "data": international_route_result.data},
            "bandwidth_test": {"success": cross_border_bandwidth.success, "data": cross_border_bandwidth.data}
        }
    
    def perform_bandwidth_test(self, agent_input: AgentInput, context: Context) -> Dict:
        """执行带宽测试"""
        logger.info(f"执行带宽测试", trace_id=agent_input.trace_id)
        
        # 通过Tool Dispatcher调用带宽测试工具
        bandwidth_result = self.tool_dispatcher.execute_tool(
            "bandwidth_tester",
            "test_bandwidth",
            {"target": agent_input.target, "duration_seconds": 10},
            context
        )
        
        return {
            "target": agent_input.target,
            "check_type": "bandwidth",
            "result": bandwidth_result.data if bandwidth_result.success else {},
            "success": bandwidth_result.success
        }
    
    def perform_latency_analysis(self, agent_input: AgentInput, context: Context) -> Dict:
        """执行延迟分析"""
        logger.info(f"执行延迟分析", trace_id=agent_input.trace_id)
        
        latency_result = self.tool_dispatcher.execute_tool(
            "latency_analyzer",
            "analyze_latency",
            {"target": agent_input.target, "packet_count": 100},
            context
        )
        
        return {
            "target": agent_input.target,
            "check_type": "latency_analysis",
            "statistics": latency_result.data if latency_result.success else {},
            "success": latency_result.success
        }
    
    def generate_report(self, agent_input: AgentInput, context: Context) -> Dict:
        """生成诊断报告 - 纯业务逻辑"""
        logger.info(f"生成诊断报告", trace_id=agent_input.trace_id)
        
        # 业务逻辑：分析检查结果并生成报告
        # 此处只是示例，实际实现需要根据检查结果进行分析
        
        return {
            "target": agent_input.target,
            "report_type": "diagnostic",
            "summary": "诊断报告生成完成",
            "recommendations": ["建议优化网络配置", "考虑跨境带宽升级"],
            "timestamp": context.timestamp
        }
    
    # --- 私有方法：具体业务逻辑实现 ---
    
    def _execute_ping_check(self, target: str, context: Context) -> CheckResult:
        """执行Ping检查"""
        return self.tool_dispatcher.execute_tool(
            "ping_tool",
            "ping_target",
            {"target": target, "count": 4, "timeout": 2},
            context
        )
    
    def _execute_dns_check(self, target: str, context: Context) -> CheckResult:
        """执行DNS检查"""
        return self.tool_dispatcher.execute_tool(
            "dns_tool",
            "resolve_domain",
            {"domain": target, "timeout": 5},
            context
        )
    
    def _execute_tcp_check(self, target: str, context: Context) -> CheckResult:
        """执行TCP端口检查"""
        return self.tool_dispatcher.execute_tool(
            "tcp_tool",
            "check_ports",
            {"target": target, "ports": [80, 443, 22, 53], "timeout": 3},
            context
        )
    
    def _execute_http_check(self, target: str, context: Context) -> CheckResult:
        """执行HTTP检查"""
        return self.tool_dispatcher.execute_tool(
            "http_tool",
            "check_http",
            {"url": f"http://{target}", "timeout": 10},
            context
        )
    
    def _execute_ssl_check(self, target: str, context: Context) -> CheckResult:
        """执行SSL检查"""
        return self.tool_dispatcher.execute_tool(
            "ssl_tool",
            "check_certificate",
            {"domain": target, "port": 443},
            context
        )
    
    def _execute_global_dns_check(self, target: str, context: Context) -> CheckResult:
        """执行全球DNS检查"""
        return self.tool_dispatcher.execute_tool(
            "dns_tool",
            "global_resolve",
            {"domain": target, "resolvers": ["8.8.8.8", "1.1.1.1", "9.9.9.9"]},
            context
        )
    
    def _execute_international_route_check(self, target: str, context: Context) -> CheckResult:
        """执行国际路由检查"""
        return self.tool_dispatcher.execute_tool(
            "traceroute_tool",
            "international_trace",
            {"target": target, "max_hops": 30},
            context
        )
    
    def _execute_cross_border_bandwidth_check(self, target: str, context: Context) -> CheckResult:
        """执行跨境带宽检查"""
        return self.tool_dispatcher.execute_tool(
            "bandwidth_tester",
            "cross_border_test",
            {"target": target, "duration": 30},
            context
        )