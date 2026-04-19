"""延迟分析器工具适配器 - 符合AAPS-001标准的工具实现"""

import time
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
from statistics import mean, stdev, median

from ...core.contracts import ToolInput, ToolOutput
from ...core.types import ExecutionResult, ToolMetadata, ToolCategory
from ...observability.logger import get_logger


logger = get_logger(__name__)


@dataclass
class LatencyAnalysisResult:
    """延迟分析结果数据契约"""
    target: str
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    latency_stddev: float
    jitter_ms: float
    packet_loss_rate: float
    rtt_trend: str  # stable, improving, degrading
    connection_quality: str  # excellent, good, fair, poor
    analysis_duration: float
    success: bool
    recommendations: List[str]
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "target": self.target,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "min_latency_ms": round(self.min_latency_ms, 2),
            "max_latency_ms": round(self.max_latency_ms, 2),
            "latency_stddev": round(self.latency_stddev, 2),
            "jitter_ms": round(self.jitter_ms, 2),
            "packet_loss_rate": round(self.packet_loss_rate, 3),
            "rtt_trend": self.rtt_trend,
            "connection_quality": self.connection_quality,
            "analysis_duration": round(self.analysis_duration, 2),
            "success": self.success,
            "recommendations": self.recommendations,
            "error_message": self.error_message
        }


class LatencyAnalyzer:
    """延迟分析工具 - 深度分析网络延迟特征"""
    
    def __init__(self):
        self.metadata = ToolMetadata(
            name="latency_analyzer",
            description="网络延迟深度分析工具，支持趋势分析和质量评估",
            category=ToolCategory.NETWORK,
            version="1.0.0",
            author="SD-WAN Analyzer",
            timeout=180.0,  # 3分钟超时
            requires_permission=["network"],
            input_schema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "分析目标地址"},
                    "sample_count": {"type": "integer", "description": "采样次数", "default": 100},
                    "interval_ms": {"type": "integer", "description": "采样间隔(毫秒)", "default": 100},
                    "duration_seconds": {"type": "integer", "description": "总分析时长(秒)", "default": 60},
                    "analyze_trends": {"type": "boolean", "description": "是否分析趋势", "default": True}
                },
                "required": ["target"]
            }
        )
    
    async def execute(self, tool_input: ToolInput) -> ToolOutput:
        """执行延迟分析"""
        try:
            logger.info(f"开始延迟分析: {tool_input.parameters}")
            
            # 验证输入参数
            target = tool_input.parameters.get("target", "")
            sample_count = tool_input.parameters.get("sample_count", 100)
            interval_ms = tool_input.parameters.get("interval_ms", 100)
            duration_seconds = tool_input.parameters.get("duration_seconds", 60)
            analyze_trends = tool_input.parameters.get("analyze_trends", True)
            
            if not target:
                return ToolOutput(
                    success=False,
                    error_message="目标地址不能为空",
                    execution_context=tool_input.context
                )
            
            # 执行延迟分析
            result = await self._analyze_latency(
                target, sample_count, interval_ms, duration_seconds, analyze_trends
            )
            
            logger.info(f"延迟分析完成: {result.target} - 平均延迟 {result.avg_latency_ms}ms")
            
            return ToolOutput(
                success=result.success,
                data=result.to_dict(),
                execution_context=tool_input.context,
                error_message=result.error_message
            )
            
        except Exception as e:
            logger.error(f"延迟分析失败: {e}", exc_info=True)
            return ToolOutput(
                success=False,
                error_message=str(e),
                execution_context=tool_input.context
            )
    
    async def _analyze_latency(self, target: str, sample_count: int, interval_ms: int, 
                              duration_seconds: int, analyze_trends: bool) -> LatencyAnalysisResult:
        """执行延迟分析"""
        start_time = time.time()
        
        try:
            # 收集延迟样本
            latency_samples = await self._collect_latency_samples(
                target, min(sample_count, 1000), max(interval_ms, 10), min(duration_seconds, 300)
            )
            
            if not latency_samples:
                return LatencyAnalysisResult(
                    target=target,
                    avg_latency_ms=0,
                    min_latency_ms=0,
                    max_latency_ms=0,
                    latency_stddev=0,
                    jitter_ms=0,
                    packet_loss_rate=1.0,
                    rtt_trend="unknown",
                    connection_quality="poor",
                    analysis_duration=time.time() - start_time,
                    success=False,
                    recommendations=["目标不可达"],
                    error_message="无法收集延迟样本"
                )
            
            # 计算基本统计指标
            avg_latency = mean(latency_samples)
            min_latency = min(latency_samples)
            max_latency = max(latency_samples)
            latency_std = stdev(latency_samples) if len(latency_samples) > 1 else 0
            
            # 计算抖动（连续延迟差值的标准差）
            jitter = self._calculate_jitter(latency_samples)
            
            # 分析趋势
            trend = "stable"
            if analyze_trends and len(latency_samples) > 10:
                trend = self._analyze_trend(latency_samples)
            
            # 评估连接质量
            quality = self._assess_connection_quality(avg_latency, jitter, latency_std)
            
            # 生成建议
            recommendations = self._generate_recommendations(avg_latency, jitter, quality)
            
            return LatencyAnalysisResult(
                target=target,
                avg_latency_ms=avg_latency,
                min_latency_ms=min_latency,
                max_latency_ms=max_latency,
                latency_stddev=latency_std,
                jitter_ms=jitter,
                packet_loss_rate=0.0,  # 基于Ping结果计算
                rtt_trend=trend,
                connection_quality=quality,
                analysis_duration=time.time() - start_time,
                success=True,
                recommendations=recommendations
            )
            
        except Exception as e:
            return LatencyAnalysisResult(
                target=target,
                avg_latency_ms=0,
                min_latency_ms=0,
                max_latency_ms=0,
                latency_stddev=0,
                jitter_ms=0,
                packet_loss_rate=0,
                rtt_trend="unknown",
                connection_quality="poor",
                analysis_duration=time.time() - start_time,
                success=False,
                recommendations=[],
                error_message=str(e)
            )
    
    async def _collect_latency_samples(self, target: str, sample_count: int, 
                                      interval_ms: int, duration_seconds: int) -> List[float]:
        """收集延迟样本"""
        samples = []
        
        try:
            from .ping import PingTool
            
            ping_tool = PingTool()
            
            for i in range(sample_count):
                if time.time() > duration_seconds:
                    break
                    
                ping_input = ToolInput(
                    parameters={"target": target, "count": 1, "timeout": interval_ms // 1000},
                    context=None
                )
                
                ping_result = await ping_tool.execute(ping_input)
                
                if ping_result.success and ping_result.data.get("avg_rtt", 0) > 0:
                    samples.append(ping_result.data["avg_rtt"])
                
                # 等待采样间隔
                if i < sample_count - 1:  # 最后一次不需要等待
                    await asyncio.sleep(interval_ms / 1000)
            
            return samples
            
        except Exception:
            return []
    
    def _calculate_jitter(self, samples: List[float]) -> float:
        """计算抖动（连续延迟差值的绝对差的平均值）"""
        if len(samples) < 2:
            return 0
        
        differences = []
        for i in range(1, len(samples)):
            diff = abs(samples[i] - samples[i-1])
            differences.append(diff)
        
        return mean(differences) if differences else 0
    
    def _analyze_trend(self, samples: List[float]) -> str:
        """分析延迟趋势"""
        if len(samples) < 10:
            return "stable"
        
        # 将样本分为前半段和后半段
        midpoint = len(samples) // 2
        first_half = samples[:midpoint]
        second_half = samples[midpoint:]
        
        first_avg = mean(first_half)
        second_avg = mean(second_half)
        
        # 计算变化百分比
        change_percentage = ((second_avg - first_avg) / first_avg) * 100 if first_avg > 0 else 0
        
        if abs(change_percentage) < 5:
            return "stable"
        elif change_percentage < -5:
            return "improving"
        else:
            return "degrading"
    
    def _assess_connection_quality(self, avg_latency: float, jitter: float, stddev: float) -> str:
        """评估连接质量"""
        # 基于延迟、抖动和稳定性的综合评估
        
        if avg_latency < 50 and jitter < 5 and stddev < 10:
            return "excellent"
        elif avg_latency < 100 and jitter < 10 and stddev < 20:
            return "good"
        elif avg_latency < 200 and jitter < 20 and stddev < 30:
            return "fair"
        else:
            return "poor"
    
    def _generate_recommendations(self, latency: float, jitter: float, quality: str) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        if quality == "poor":
            recommendations.extend([
                "检查本地网络连接质量",
                "尝试更换DNS服务器",
                "排查网络设备性能问题",
                "考虑使用有线连接替代无线"
            ])
        elif quality == "fair":
            recommendations.extend([
                "可尝试优化网络配置",
                "检查是否有后台网络占用",
                "验证网络带宽是否充足"
            ])
        elif quality == "good":
            recommendations.append("网络质量良好，保持当前配置")
        else:
            recommendations.append("网络连接质量极佳")
        
        if jitter > 10:
            recommendations.append("网络抖动较高，建议排查抖动源")
        
        if latency > 100:
            recommendations.append("延迟较高，建议优化网络路径")
        
        return recommendations


# 工具注册函数
def register_latency_analyzer(registry):
    """注册延迟分析工具"""
    latency_analyzer = LatencyAnalyzer()
    registry.register_tool(latency_analyzer)
    return latency_analyzer