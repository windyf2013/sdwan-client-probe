"""
CLI接口层 - 严格遵循AI Agent Python工程标准Interface Layer

职责：接收外部输入、参数校验、组装标准化AgentInput、返回AgentOutput
禁止：承载业务规则、直接调用工具实现细节

文档编号: AAPS-001
规范等级: Mandatory（强制执行）
"""

import argparse
from typing import Optional
from dataclasses import asdict

from ..core.contracts import AgentInput, AgentOutput, BaseError, ValidationError
from ..core.types import PriorityType, BusinessType
from ..runtime.engine import DiagnosticEngine
from ..observability.logger import get_logger

logger = get_logger(__name__)


def parse_cli_args() -> argparse.Namespace:
    """解析命令行参数 - 仅做参数解析"""
    parser = argparse.ArgumentParser(description="SD-WAN云网跨境健康分析平台")
    
    parser.add_argument("target", nargs='?', help="诊断目标（域名/IP）")
    parser.add_argument("--priority", choices=["low", "normal", "high"], 
                        default="normal", help="优先级")
    parser.add_argument("--business-type", choices=["domestic", "cross_border"],
                        default="cross_border", help="业务类型")
    parser.add_argument("--session-id", help="会话ID")
    parser.add_argument("--interactive", action="store_true", help="交互模式")
    
    return parser.parse_args()


def validate_cli_input(args: argparse.Namespace) -> AgentInput:
    """验证CLI输入并构建AgentInput - 符合AAPS-001数据契约要求"""
    if not args.target:
        raise ValidationError(
            error_code="VAL_INVALID_TARGET", 
            message="诊断目标不能为空",
            context={"args": asdict(args)},
            trace_id=str(id(args))
        )
    
    return AgentInput(
        target=args.target,
        session_id=args.session_id,
        business_context={
            "business_type": args.business_type,
            "interactive_mode": args.interactive
        },
        priority=args.priority
    )


def run_diagnosis(agent_input: AgentInput) -> AgentOutput:
    """运行诊断流程 - Interface层不应包含业务逻辑"""
    logger.info(f"启动诊断流程", 
                trace_id=agent_input.trace_id, 
                target=agent_input.target)
    
    try:
        # 验证输入 - 符合前置条件检查
        agent_input.validate()
        
        # 创建执行引擎 - 不包含业务逻辑
        engine = DiagnosticEngine()
        
        # 执行诊断 - 将业务逻辑委托给Orchestration层
        result = engine.execute_diagnosis(agent_input)
        
        return result
        
    except BaseError as e:
        logger.error(f"诊断流程异常: {e.message}", 
                     trace_id=getattr(e, 'trace_id', 'unknown'),
                     error_code=e.error_code)
        return AgentOutput(
            success=False,
            result={},
            errors=[f"{e.error_code}: {e.message}"]
        )
    except Exception as e:
        # 捕获未预期的系统错误
        logger.error(f"系统异常: {str(e)}")
        return AgentOutput(
            success=False,
            result={},
            errors=[f"SYS_UNEXPECTED_ERROR: {str(e)}"]
        )


def render_output(agent_output: AgentOutput) -> str:
    """渲染输出结果 - 仅负责展示，不含业务逻辑"""
    if agent_output.success:
        return f"✅ 诊断完成\n结果: {agent_output.result}"
    else:
        return f"❌ 诊断失败\n错误: {', '.join(agent_output.errors)}"


def main():
    """主入口函数 - 严格遵守Interface Layer职责"""
    try:
        # 1. 参数解析
        args = parse_cli_args()
        
        # 2. 输入验证和转换
        agent_input = validate_cli_input(args)
        
        # 3. 执行诊断（业务逻辑委托给下层）
        agent_output = run_diagnosis(agent_input)
        
        # 4. 结果展示
        print(render_output(agent_output))
        
    except Exception as e:
        print(f"❌ 程序异常: {str(e)}")
        return 1
    
    return 0