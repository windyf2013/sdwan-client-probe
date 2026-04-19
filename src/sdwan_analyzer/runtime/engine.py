"""
执行引擎层 - 严格遵循AI Agent Python工程标准Orchestration Layer

职责：基于Flow定义调度步骤、状态迁移、分支决策、重试与回放控制
禁止：直接实现业务算法与底层IO

文档编号: AAPS-001
规范等级: Mandatory（强制执行）
"""

from dataclasses import asdict
from typing import Dict, List, Optional

from ..core.contracts import (
    AgentInput, AgentOutput, Context, FlowState, BaseError, FlowError
)
from ..core.types import StepStatus, StandardErrors
from ..services.diagnostic import DiagnosticService
from ..tools.registry import ToolRegistry
from ..observability.logger import get_logger

logger = get_logger(__name__)


class DiagnosticEngine:
    """诊断执行引擎 - 负责流程编排，不包含具体业务逻辑"""
    
    def __init__(self):
        self.tool_registry = ToolRegistry()
        self.diagnostic_service = DiagnosticService(self.tool_registry)
        self.flow_definitions = self._load_flow_definitions()
    
    def _load_flow_definitions(self) -> Dict[str, Dict]:
        """加载流程定义配置 - 支持DAG/Pipeline/StateMachine"""
        return {
            "basic_diagnosis": {
                "type": "pipeline",
                "steps": ["network_check", "application_check", "report_generation"],
                "timeout": 300
            },
            "cross_border_diagnosis": {
                "type": "dag",
                "steps": ["overseas_check", "bandwidth_test", "latency_analysis"],
                "dependencies": {"bandwidth_test": ["overseas_check"]},
                "timeout": 600
            }
        }
    
    def select_flow_definition(self, agent_input: AgentInput) -> str:
        """根据输入选择流程定义 - 非业务逻辑，纯编排决策"""
        business_type = agent_input.business_context.get("business_type", "")
        
        if business_type == "cross_border":
            return "cross_border_diagnosis"
        else:
            return "basic_diagnosis"
    
    def execute(self, agent_input: AgentInput) -> AgentOutput:
        """编排入口：与 __main__ / 测试约定的 `execute` 名称。"""
        return self.execute_diagnosis(agent_input)

    def execute_diagnosis(self, agent_input: AgentInput) -> AgentOutput:
        """执行诊断流程 - 纯编排逻辑"""
        logger.info(f"执行诊断流程编排", trace_id=agent_input.trace_id)
        
        try:
            # 初始化流程状态
            context = Context(session_id=agent_input.session_id or agent_input.trace_id)
            flow_state = FlowState()
            
            # 选择流程定义
            flow_name = self.select_flow_definition(agent_input)
            flow_def = self.flow_definitions[flow_name]
            
            # 执行流程步骤
            result = self._execute_flow(flow_def, agent_input, context, flow_state)
            
            return AgentOutput(
                success=True,
                result=result,
                execution_time_ms=flow_state.context_snapshot.get("total_duration_ms", 0)
            )
            
        except FlowError as e:
            logger.error(f"流程编排错误: {e.message}", trace_id=e.trace_id)
            raise
        except Exception as e:
            logger.error(f"执行引擎异常: {str(e)}")
            raise FlowError(
                error_code=StandardErrors.FLOW_STEP_FAILED,
                message=f"执行引擎异常: {str(e)}",
                context={"agent_input": asdict(agent_input)},
                trace_id=agent_input.trace_id
            )
    
    def _execute_flow(self, flow_def: Dict, agent_input: AgentInput, 
                     context: Context, flow_state: FlowState) -> Dict:
        """执行具体流程"""
        results = {}
        
        for step_name in flow_def["steps"]:
            # 更新当前步骤
            flow_state.current_step = step_name
            flow_state.status = StepStatus.RUNNING
            
            try:
                # 执行步骤 - 委托给Service层
                step_result = self._execute_step(step_name, agent_input, context, flow_state)
                results[step_name] = step_result
                
                # 记录步骤历史
                flow_state.add_step_record({
                    "step": step_name,
                    "status": StepStatus.COMPLETED,
                    "result": step_result
                })
                
            except Exception as e:
                # 处理步骤失败 - 根据重试策略决定是否继续
                flow_state.add_step_record({
                    "step": step_name,
                    "status": StepStatus.FAILED,
                    "error": str(e)
                })
                
                if not self._should_retry_step(step_name, flow_state):
                    raise FlowError(
                        error_code=StandardErrors.FLOW_STEP_FAILED,
                        message=f"步骤 {step_name} 执行失败",
                        context={"step_name": step_name, "error": str(e)},
                        trace_id=agent_input.trace_id
                    )
        
        flow_state.status = StepStatus.COMPLETED
        return results
    
    def _execute_step(self, step_name: str, agent_input: AgentInput, 
                     context: Context, flow_state: FlowState) -> Dict:
        """执行单个步骤 - 路由到对应的Service层方法"""
        routing_table = {
            "network_check": self.diagnostic_service.perform_network_check,
            "application_check": self.diagnostic_service.perform_application_check,
            "overseas_check": self.diagnostic_service.perform_overseas_check,
            "bandwidth_test": self.diagnostic_service.perform_bandwidth_test,
            "latency_analysis": self.diagnostic_service.perform_latency_analysis,
            "report_generation": self.diagnostic_service.generate_report
        }
        
        if step_name not in routing_table:
            raise FlowError(
                error_code=StandardErrors.FLOW_BRANCH_ERROR,
                message=f"未知步骤: {step_name}",
                context={"step_name": step_name},
                trace_id=agent_input.trace_id
            )
        
        return routing_table[step_name](agent_input, context)
    
    def _should_retry_step(self, step_name: str, flow_state: FlowState) -> bool:
        """判断是否应该重试步骤 - 编排策略"""
        # 简单的重试逻辑 - 实际应根据配置决定
        step_records = [r for r in flow_state.step_history if r.get("step") == step_name]
        return len(step_records) < 2  # 最多重试1次


# 与 __main__.py、tests 中使用的类名一致（AAPS 编排层对外符号）
WorkflowEngine = DiagnosticEngine