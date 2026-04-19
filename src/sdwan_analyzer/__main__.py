"""
SD-WAN分析器主入口点 - 符合AAPS-001标准的AI Agent架构

职责：
- 统一应用程序启动和生命周期管理
- CLI参数处理和交互式模式支持
- 错误处理和优雅关闭

依赖关系：Interface → Orchestration → Service → Tool → Core → Infra
"""

import asyncio
import sys
from pathlib import Path

# 确保将src目录添加到Python路径
src_dir = Path(__file__).parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from .interface.cli_adapter import CLIAdapter
from .core.bootstrap import ApplicationBootstrap
from .runtime.engine import WorkflowEngine
from .observability.logger import get_logger


def main():
    """应用程序主入口函数"""
    
    # 1. 应用启动引导
    bootstrap = ApplicationBootstrap()
    bootstrap.initialize()
    
    # 2. 获取日志记录器
    logger = get_logger("sdwan_analyzer.main")
    
    # 3. CLI适配器处理
    cli_adapter = CLIAdapter()
    
    try:
        # 4. 解析命令行参数
        cli_args = cli_adapter.parse_args()
        
        # 5. 如果交互模式，运行交互式界面
        if not sys.argv[1:]:
            return cli_adapter.run_interactive()
        
        # 6. 构建Agent输入
        agent_input = cli_adapter.build_agent_input(cli_args)
        
        # 7. 初始化工作流引擎
        engine = WorkflowEngine()
        
        # 8. 执行工作流
        agent_output = engine.execute(agent_input)
        
        # 9. 格式化输出
        output = cli_adapter.format_output(agent_output, cli_args)
        
        # 10. 输出结果
        print(output)
        
        # 11. 返回退出代码
        return 0 if agent_output.success else 1
        
    except KeyboardInterrupt:
        logger.info("用户终止程序")
        print("\n程序已终止")
        return 130  # SIGINT退出码
        
    except Exception as e:
        logger.error(f"应用程序错误: {e}", exc_info=True)
        print(f"错误: {e}")
        return 1
    
    finally:
        # 清理资源
        bootstrap.shutdown()


if __name__ == "__main__":
    sys.exit(main())