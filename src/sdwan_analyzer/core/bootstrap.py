"""
应用启动器 - 严格遵循AI Agent Python工程标准

职责：统一管理应用启动、组件初始化、生命周期管理
禁止：散乱的启动代码、不可预测的启动顺序

文档编号: AAPS-001
规范等级: Mandatory（强制执行）
"""

import asyncio
import signal
import sys
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from ..observability.logger import get_logger, initialize_logging, set_global_log_context
from ..infrastructure.config import get_config_manager, ConfigManager
from ..tools.registry import ToolRegistry
from ..tools.dispatcher import ToolDispatcher, get_dispatcher
from ..runtime.engine import DiagnosticEngine
from ..observability.metrics import get_metrics_collector

logger = get_logger(__name__)


class AppState(Enum):
    """应用状态"""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"


@dataclass
class ComponentStatus:
    """组件状态"""
    name: str
    initialized: bool = False
    healthy: bool = False
    error_message: Optional[str] = None
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "initialized": self.initialized,
            "healthy": self.healthy,
            "error_message": self.error_message,
            "dependencies": self.dependencies
        }


class Application:
    """应用程序主类"""
    
    def __init__(self):
        self.state = AppState.UNINITIALIZED
        self.components: Dict[str, ComponentStatus] = {}
        self.config_manager: Optional[ConfigManager] = None
        self.tool_registry: Optional[ToolRegistry] = None
        self.tool_dispatcher: Optional[ToolDispatcher] = None
        self.engine: Optional[DiagnosticEngine] = None
        self._shutdown_event = asyncio.Event()
        self._logger = get_logger(__name__)
        
        # 注册组件
        self._register_components()
    
    def _register_components(self) -> None:
        """注册所有应用组件"""
        components = [
            ComponentStatus("logging", dependencies=[]),
            ComponentStatus("config", dependencies=["logging"]),
            ComponentStatus("metrics", dependencies=["config", "logging"]),
            ComponentStatus("tool_registry", dependencies=["config", "logging"]),
            ComponentStatus("tool_dispatcher", dependencies=["tool_registry"]),
            ComponentStatus("diagnostic_engine", dependencies=["tool_dispatcher"]),
            ComponentStatus("cli_interface", dependencies=["diagnostic_engine"])
        ]
        
        for component in components:
            self.components[component.name] = component
    
    async def initialize(self) -> bool:
        """初始化应用程序"""
        self.state = AppState.INITIALIZING
        self._logger.info("开始初始化应用程序")
        
        try:
            # 按照依赖顺序初始化组件
            initialization_order = self._get_initialization_order()
            
            for component_name in initialization_order:
                await self._initialize_component(component_name)
            
            self.state = AppState.READY
            self._logger.info("应用程序初始化完成")
            
            # 记录启动指标
            await self._record_startup_metrics()
            
            return True
            
        except Exception as e:
            self._logger.error(f"应用程序初始化失败: {e}", exc_info=True)
            self.state = AppState.SHUTDOWN
            return False
    
    def _get_initialization_order(self) -> List[str]:
        """获取初始化顺序（拓扑排序）"""
        # 简化的拓扑排序实现
        visited = set()
        result = []
        
        def visit(component_name: str):
            if component_name in visited:
                return
            
            component = self.components[component_name]
            for dep in component.dependencies:
                visit(dep)
            
            visited.add(component_name)
            result.append(component_name)
        
        for component_name in self.components:
            if component_name not in visited:
                visit(component_name)
        
        return result
    
    async def _initialize_component(self, component_name: str) -> None:
        """初始化单个组件"""
        component = self.components[component_name]
        
        self._logger.info(f"初始化组件: {component_name}")
        
        try:
            if component_name == "logging":
                await self._initialize_logging()
            elif component_name == "config":
                await self._initialize_config()
            elif component_name == "metrics":
                await self._initialize_metrics()
            elif component_name == "tool_registry":
                await self._initialize_tool_registry()
            elif component_name == "tool_dispatcher":
                await self._initialize_tool_dispatcher()
            elif component_name == "diagnostic_engine":
                await self._initialize_diagnostic_engine()
            elif component_name == "cli_interface":
                await self._initialize_cli_interface()
            else:
                raise ValueError(f"未知的组件: {component_name}")
            
            component.initialized = True
            component.healthy = True
            
            self._logger.info(f"组件初始化完成: {component_name}")
            
        except Exception as e:
            component.error_message = str(e)
            component.initialized = False
            component.healthy = False
            
            self._logger.error(f"组件初始化失败: {component_name} - {e}", exc_info=True)
            raise
    
    async def _initialize_logging(self) -> None:
        """初始化日志系统"""
        initialize_logging()
        
        # 设置全局日志上下文
        set_global_log_context(
            app_name="sdwan_analyzer",
            app_version="1.0.0",
            environment=self._get_environment()
        )
        
        self._logger.info("日志系统初始化完成")
    
    async def _initialize_config(self) -> None:
        """初始化配置系统"""
        self.config_manager = get_config_manager()
        
        # 验证关键配置
        self._validate_critical_config()
        
        self._logger.info("配置系统初始化完成")
    
    async def _initialize_metrics(self) -> None:
        """初始化指标系统"""
        # 指标系统在get_metrics_collector时自动初始化
        _ = get_metrics_collector()
        self._logger.info("指标系统初始化完成")
    
    async def _initialize_tool_registry(self) -> None:
        """初始化工具注册表"""
        self.tool_registry = ToolRegistry()
        self.tool_registry.initialize()
        self._logger.info("工具注册表初始化完成")
    
    async def _initialize_tool_dispatcher(self) -> None:
        """初始化工具调度器"""
        self.tool_dispatcher = get_dispatcher()
        
        # 验证工具注册表可用
        if not self.tool_registry:
            raise RuntimeError("工具注册表未初始化")
            
        self._logger.info("工具调度器初始化完成")
    
    async def _initialize_diagnostic_engine(self) -> None:
        """初始化诊断引擎"""
        if not self.tool_dispatcher:
            raise RuntimeError("工具调度器未初始化")
        
        self.engine = DiagnosticEngine(self.tool_dispatcher)
        self._logger.info("诊断引擎初始化完成")
    
    async def _initialize_cli_interface(self) -> None:
        """初始化CLI接口"""
        # CLI接口是惰性初始化的，这里只是标记完成
        self._logger.info("CLI接口初始化准备完成")
    
    def _validate_critical_config(self) -> None:
        """验证关键配置"""
        if not self.config_manager:
            raise RuntimeError("配置管理器未初始化")
        
        critical_configs = [
            ("log_level", "INFO"),
            ("max_concurrent_tasks", 10),
            ("tool_execution_timeout", 60.0)
        ]
        
        for key, default_value in critical_configs:
            value = self.config_manager.get(key, default_value)
            self._logger.debug(f"配置验证: {key} = {value}")
    
    def _get_environment(self) -> str:
        """获取运行环境"""
        return "development"  # 简化实现
    
    async def _record_startup_metrics(self) -> None:
        """记录启动指标"""
        # 记录启动时间等指标
        # 实际应该记录更详细的启动指标
        pass
    
    async def run_cli(self, cli_args: Optional[List[str]] = None) -> int:
        """运行CLI模式"""
        if self.state != AppState.READY:
            self._logger.error("应用程序未就绪，无法运行CLI")
            return 1
        
        self.state = AppState.RUNNING
        
        try:
            from ..interface.cli import main as cli_main
            
            # 设置信号处理
            self._setup_signal_handlers()
            
            # 运行CLI
            return await cli_main(args=cli_args)
            
        except Exception as e:
            self._logger.error(f"CLI执行失败: {e}", exc_info=True)
            return 1
        finally:
            await self.shutdown()
    
    async def run_server(self) -> int:
        """运行服务器模式"""
        # TODO: 实现服务器模式
        self._logger.info("服务器模式待实现")
        return 0
    
    async def shutdown(self) -> None:
        """关闭应用程序"""
        if self.state in [AppState.SHUTTING_DOWN, AppState.SHUTDOWN]:
            return
        
        self.state = AppState.SHUTTING_DOWN
        self._logger.info("开始关闭应用程序")
        
        # 按照依赖逆序关闭组件
        shutdown_order = list(reversed(self._get_initialization_order()))
        
        for component_name in shutdown_order:
            await self._shutdown_component(component_name)
        
        self._shutdown_event.set()
        self.state = AppState.SHUTDOWN
        self._logger.info("应用程序关闭完成")
    
    async def _shutdown_component(self, component_name: str) -> None:
        """关闭单个组件"""
        component = self.components[component_name]
        
        if not component.initialized:
            return
        
        try:
            self._logger.info(f"关闭组件: {component_name}")
            
            if component_name == "tool_dispatcher" and self.tool_dispatcher:
                self.tool_dispatcher.shutdown()
            
            component.initialized = False
            component.healthy = False
            
            self._logger.info(f"组件关闭完成: {component_name}")
            
        except Exception as e:
            self._logger.error(f"组件关闭失败: {component_name} - {e}")
    
    def _setup_signal_handlers(self) -> None:
        """设置信号处理器"""
        def signal_handler(signum, frame):
            self._logger.info(f"接收到信号: {signum}")
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def get_health_status(self) -> Dict[str, Any]:
        """获取应用健康状态"""
        healthy_components = [
            c for c in self.components.values() 
            if c.initialized and c.healthy
        ]
        
        return {
            "state": self.state.value,
            "total_components": len(self.components),
            "healthy_components": len(healthy_components),
            "all_healthy": len(healthy_components) == len(self.components),
            "components": [c.to_dict() for c in self.components.values()]
        }


# 全局应用实例
_application_instance: Optional[Application] = None


def get_application() -> Application:
    """获取全局应用实例"""
    global _application_instance
    if _application_instance is None:
        _application_instance = Application()
    return _application_instance


async def main() -> int:
    """应用程序主入口点"""
    app = get_application()
    
    # 初始化应用
    if not await app.initialize():
        return 1
    
    # 运行CLI模式
    return await app.run_cli(sys.argv[1:])


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)