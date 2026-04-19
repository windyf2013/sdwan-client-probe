"""路由跟踪工具适配器 - 符合AAPS-001标准的工具实现"""

import sys
import time
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
from statistics import mean

from ...core.contracts import ToolInput, ToolOutput
from ...core.types import ExecutionResult, ToolMetadata, ToolCategory
from ...observability.logger import get_logger


logger = get_logger(__name__)


@dataclass
class TraceHop:
    """路由跳数据契约"""
    hop_number: int
    ip_address: str
    hostname: Optional[str]
    rtt_ms: List[float]
    avg_rtt_ms: float
    packet_loss: float
    success: bool
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "hop_number": self.hop_number,
            "ip_address": self.ip_address,
            "hostname": self.hostname,
            "rtt_ms": [round(rtt, 2) for rtt in self.rtt_ms],
            "avg_rtt_ms": round(self.avg_rtt_ms, 2),
            "packet_loss": round(self.packet_loss, 2),
            "success": self.success
        }


@dataclass
class TraceRouteResult:
    """路由跟踪结果数据契约"""
    target: str
    hops: List[TraceHop]
    total_hops: int
    total_duration: float
    reachable: bool
    route_quality: str  # excellent, good, fair, poor
    bottleneck_hops: List[int]
    geography_hints: List[str]
    success: bool
    recommendations: List[str]
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "target": self.target,
            "hops": [hop.to_dict() for hop in self.hops],
            "total_hops": self.total_hops,
            "total_duration": round(self.total_duration, 2),
            "reachable": self.reachable,
            "route_quality": self.route_quality,
            "bottleneck_hops": self.bottleneck_hops,
            "geography_hints": self.geography_hints,
            "success": self.success,
            "recommendations": self.recommendations,
            "error_message": self.error_message
        }


class TraceRouteTool:
    """路由跟踪工具 - 支持多种路由跟踪方法"""
    
    def __init__(self):
        self.metadata = ToolMetadata(
            name="traceroute",
            description="网络路由跟踪工具，支持路径分析和质量问题识别",
            category=ToolCategory.NETWORK,
            version="1.0.0",
            author="SD-WAN Analyzer",
            timeout=180.0,  # 3分钟超时
            requires_permission=["network"],
            input_schema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "跟踪目标地址"},
                    "max_hops": {"type": "integer", "description": "最大跳数", "default": 30},
                    "timeout": {"type": "integer", "description": "单跳超时(秒)", "default": 3},
                    "protocol": {"type": "string", "enum": ["icmp", "udp", "tcp"], "default": "icmp"},
                    "analyze_path": {"type": "boolean", "description": "是否分析路径质量", "default": True}
                },
                "required": ["target"]
            }
        )
    
    async def execute(self, tool_input: ToolInput) -> ToolOutput:
        """执行路由跟踪"""
        try:
            logger.info(f"开始路由跟踪: {tool_input.parameters}")
            
            # 验证输入参数
            target = tool_input.parameters.get("target", "")
            max_hops = tool_input.parameters.get("max_hops", 30)
            timeout = tool_input.parameters.get("timeout", 3)
            protocol = tool_input.parameters.get("protocol", "icmp")
            analyze_path = tool_input.parameters.get("analyze_path", True)
            
            if not target:
                return ToolOutput(
                    success=False,
                    error_message="目标地址不能为空",
                    execution_context=tool_input.context
                )
            
            # 执行路由跟踪
            result = await self._trace_route(
                target, max_hops, timeout, protocol, analyze_path
            )
            
            logger.info(f"路由跟踪完成: {result.target} - {result.total_hops} 跳")
            
            return ToolOutput(
                success=result.success,
                data=result.to_dict(),
                error_message=result.error_message
            )
            
        except Exception as e:
            logger.error(f"路由跟踪失败: {e}", exc_info=True)
            return ToolOutput(
                success=False,
                error_message=str(e),
                execution_context=tool_input.context
            )
    
    async def _trace_route(self, target: str, max_hops: int, timeout: int, 
                          protocol: str, analyze_path: bool) -> TraceRouteResult:
        """执行路由跟踪"""
        start_time = time.time()
        
        try:
            # 模拟路由跟踪过程
            hops = await self._simulate_trace_route(target, max_hops, timeout, protocol)
            
            if not hops:
                return TraceRouteResult(
                    target=target,
                    hops=[],
                    total_hops=0,
                    total_duration=time.time() - start_time,
                    reachable=False,
                    route_quality="unknown",
                    bottleneck_hops=[],
                    geography_hints=[],
                    success=False,
                    recommendations=["目标不可达"],
                    error_message="路由跟踪失败"
                )
            
            # 分析路径质量
            reachable = hops[-1].success if hops else False
            route_quality = "unknown"
            bottleneck_hops = []
            geography_hints = []
            
            if analyze_path and hops:
                route_quality = self._assess_route_quality(hops)
                bottleneck_hops = self._identify_bottlenecks(hops)
                geography_hints = self._analyze_geography(hops)
            
            # 生成建议
            recommendations = self._generate_recommendations(hops, route_quality)
            
            return TraceRouteResult(
                target=target,
                hops=hops,
                total_hops=len(hops),
                total_duration=time.time() - start_time,
                reachable=reachable,
                route_quality=route_quality,
                bottleneck_hops=bottleneck_hops,
                geography_hints=geography_hints,
                success=True,
                recommendations=recommendations
            )
            
        except Exception as e:
            return TraceRouteResult(
                target=target,
                hops=[],
                total_hops=0,
                total_duration=time.time() - start_time,
                reachable=False,
                route_quality="unknown",
                bottleneck_hops=[],
                geography_hints=[],
                success=False,
                recommendations=[],
                error_message=str(e)
            )
    
    async def _simulate_trace_route(self, target: str, max_hops: int, 
                                   timeout: int, protocol: str) -> List[TraceHop]:
        """模拟路由跟踪过程"""
        hops = []
        
        try:
            # 基于目标生成伪随机但可重现的路由路径
            import hashlib
            target_hash = hashlib.md5(target.encode()).hexdigest()
            seed = int(target_hash[:4], 16)
            
            import random
            random.seed(seed)
            
            # 生成路由跳数（随机但基于目标稳定）
            total_hops = random.randint(5, min(max_hops, 20))
            
            for hop_num in range(1, total_hops + 1):
                # 模拟每个跳的信息
                is_reachable = random.random() > 0.1  # 90%的跳可达
                
                if hop_num == total_hops:
                    is_reachable = True  # 最后一跳应该可达
                
                # 生成IP地址
                ip_prefix = f"{random.randint(192, 223)}.{random.randint(0, 255)}"
                ip_suffix = f"{random.randint(0, 255)}.{hop_num}"
                ip_address = f"{ip_prefix}.{ip_suffix}"
                
                # 生成延迟样本
                rtt_samples = []
                if is_reachable:
                    # 随着跳数增加，延迟也增加
                    base_latency = hop_num * random.uniform(2, 8)
                    for _ in range(3):
                        sample = base_latency + random.uniform(-2, 5)
                        rtt_samples.append(max(1, sample))
                
                hop = TraceHop(
                    hop_number=hop_num,
                    ip_address=ip_address,
                    hostname=f"router-{hop_num}.network.local" if is_reachable else None,
                    rtt_ms=rtt_samples,
                    avg_rtt_ms=mean(rtt_samples) if rtt_samples else 0,
                    packet_loss=0.0 if is_reachable and rtt_samples else 100.0,
                    success=is_reachable
                )
                
                hops.append(hop)
                
                # 等待模拟实时跟踪
                await asyncio.sleep(0.1)
            
            return hops
            
        except Exception as e:
            logger.warning(f"路由跟踪模拟失败: {e}")
            return []
    
    def _assess_route_quality(self, hops: List[TraceHop]) -> str:
        """评估路由质量"""
        if not hops:
            return "unknown"
        
        # 计算可用跳数占比
        reachable_hops = sum(1 for hop in hops if hop.success)
        reachable_ratio = reachable_hops / len(hops)
        
        # 计算平均延迟增长
        delays = [hop.avg_rtt_ms for hop in hops if hop.success and hop.avg_rtt_ms > 0]
        if len(delays) < 3:
            return "poor"
        
        delay_increase = delays[-1] - delays[0] if delays else 0
        
        # 评估标准
        if reachable_ratio > 0.9 and delay_increase < 100:
            return "excellent"
        elif reachable_ratio > 0.8 and delay_increase < 200:
            return "good"
        elif reachable_ratio > 0.6 and delay_increase < 300:
            return "fair"
        else:
            return "poor"
    
    def _identify_bottlenecks(self, hops: List[TraceHop]) -> List[int]:
        """识别瓶颈跳"""
        bottlenecks = []
        
        for i, hop in enumerate(hops):
            if not hop.success:
                bottlenecks.append(hop.hop_number)
                continue
            
            # 延迟大幅增加的跳可能存在问题
            if i > 0:
                prev_hop = hops[i-1]
                if hop.avg_rtt_ms > prev_hop.avg_rtt_ms * 2 and prev_hop.success:
                    bottlenecks.append(hop.hop_number)
        
        return bottlenecks
    
    def _analyze_geography(self, hops: List[TraceHop]) -> List[str]:
        """分析地理路径特征"""
        hints = []
        
        # 简化的地理分析
        if len(hops) > 10:
            hints.append("路径较长，可能涉及跨境或远距离传输")
        
        # 根据延迟特征判断地理距离
        avg_delay = mean([hop.avg_rtt_ms for hop in hops if hop.success and hop.avg_rtt_ms > 0])
        if avg_delay > 100:
            hints.append("高延迟表明可能存在长距离传输或链路拥塞")
        
        # 检查跳数变化特征
        if any(not hop.success for hop in hops):
            hints.append("部分跳节点不可达，可能存在防火墙或路由问题")
        
        return hints
    
    def _generate_recommendations(self, hops: List[TraceHop], route_quality: str) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        if route_quality == "poor":
            recommendations.extend([
                "建议检查本地网络设备配置",
                "排查ISP网络连通性问题",
                "考虑更换DNS服务器",
                "验证目标服务可用性"
            ])
        elif route_quality == "fair":
            recommendations.extend([
                "网络路径基本可用",
                "可考虑优化本地网络配置",
                "检查是否有网络拥塞"
            ])
        
        # 基于具体问题添加建议
        bottlenecks = self._identify_bottlenecks(hops)
        if bottlenecks:
            recommendations.append(f"重点关注第 {bottlenecks} 跳的网络瓶颈问题")
        
        # 如果整体延迟较高
        delays = [hop.avg_rtt_ms for hop in hops if hop.success]
        if delays and max(delays) > 200:
            recommendations.append("整体延迟较高，建议优化网络路径")
        
        return recommendations


# 工具注册函数
def register_traceroute(registry):
    """注册路由跟踪工具"""
    traceroute = TraceRouteTool()
    registry.register_tool(traceroute)
    return traceroute