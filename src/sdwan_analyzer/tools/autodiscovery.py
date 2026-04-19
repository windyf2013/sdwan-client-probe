"""
工具自动发现和注册系统 - 符合AAPS-001标准的工具管理

职责：动态发现和注册工具，支持插件式架构
禁止：硬编码工具依赖关系

文档编号: AAPS-001
规范等级: Mandatory（强制执行）
"""

import importlib
import inspect
import pkgutil
from typing import Dict, List, Type, Any, Optional
from pathlib import Path

from .registry import ToolRegistry, ToolMetadata, tool_registry
from ..core.contracts import ToolInput, ToolOutput
from ..core.types import ToolCategory
from ..observability.logger import get_logger

logger = get_logger(__name__)


class ToolAdapter:
    """工具适配器基类 - 统一管理工具接口"""
    
    def __init__(self, tool_class: Type):
        self.tool_class = tool_class
        self.instance = None
        
    def _ensure_instance(self):
        """确保工具实例存在"""
        if self.instance is None:
            self.instance = self.tool_class()
            
    def get_metadata(self) -> ToolMetadata:
        """获取工具元数据"""
        self._ensure_instance()
        return self.instance.metadata
        
    async def execute_async(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """异步执行工具"""
        self._ensure_instance()
        
        # 创建工具输入
        tool_input = ToolInput(
            parameters=parameters,
            context=None
        )
        
        # 执行工具
        result: ToolOutput = await self.instance.execute(tool_input)
        
        # 返回格式化结果
        output_data = {
            "success": result.success,
            "data": result.data or {},
            "error_message": result.error_message
        }
        
        # 添加工具特定结果
        if isinstance(result.data, dict):
            output_data.update(result.data)
            
        return output_data
        
    def execute_sync(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """同步执行工具（适配器模式）"""
        import asyncio
        
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.execute_async(parameters))


class ToolAutoDiscovery:
    """工具自动发现系统"""
    
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.discovered_tools: Dict[str, ToolAdapter] = {}
        
    def discover_tools(self, package_path: str) -> List[str]:
        """发现指定包路径下的所有工具"""
        discovered = []
        
        try:
            # 导入工具包
            package = importlib.import_module(package_path)
            
            # 获取包所在目录
            if hasattr(package, '__path__') and package.__path__:
                # 包（有__path__属性）
                package_dir = Path(package.__path__[0])
            elif hasattr(package, '__file__') and package.__file__:
                # 模块（有__file__属性）
                package_dir = Path(package.__file__).parent
            else:
                logger.warning(f"包 {package_path} 缺少路径属性")
                return discovered
            
            logger.info(f"开始发现工具: {package_path} ({package_dir})")
            
            # 遍历包下的所有模块
            for module_info in pkgutil.iter_modules([str(package_dir)]):
                if module_info.ispkg:
                    continue  # 跳过子包
                    
                module_name = f"{package_path}.{module_info.name}"
                try:
                    # 导入模块
                    module = importlib.import_module(module_name)
                    
                    # 查找工具类
                    tool_classes = self._find_tool_classes(module)
                    
                    for tool_class in tool_classes:
                        if self._register_tool_class(tool_class, module_name):
                            discovered.append(tool_class.__name__)
                            
                except Exception as e:
                    logger.warning(f"发现工具模块失败 {module_name}: {e}")
                    
        except Exception as e:
            logger.error(f"工具自动发现失败 {package_path}: {e}")
            
        logger.info(f"发现 {len(discovered)} 个工具")
        return discovered
        
    def _find_tool_classes(self, module) -> List[Type]:
        """在模块中查找工具类"""
        tool_classes = []
        
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                obj.__module__ == module.__name__ and
                not name.startswith('_') and
                hasattr(obj, 'execute')):
                
                # 检查是否包含必要的工具方法
                if callable(getattr(obj, 'execute', None)):
                    # 尝试创建实例并检查是否有metadata属性
                    try:
                        tool_instance = obj()
                        if hasattr(tool_instance, 'metadata'):
                            tool_classes.append(obj)
                        else:
                            # 如果在实例上没有metadata，但在类上有，也认为是工具类
                            if hasattr(obj, 'metadata'):
                                tool_classes.append(obj)
                            else:
                                logger.warning(f"类 {name} 有execute方法但没有metadata属性")
                    except Exception as e:
                        logger.warning(f"无法创建 {name} 实例进行检测: {e}")
        
        logger.info(f"在模块 {module.__name__} 中找到 {len(tool_classes)} 个工具类")
        return tool_classes
        
    def _register_tool_class(self, tool_class: Type, module_path: str) -> bool:
        """注册工具类"""
        try:
            # 创建工具适配器
            adapter = ToolAdapter(tool_class)
            source_metadata = adapter.get_metadata()
            
            # 获取工具名称
            tool_name = getattr(source_metadata, 'name', tool_class.__name__)
            
            # 统一元数据格式 - 转换为core.types.ToolMetadata
            from ..core.types import ToolMetadata as CoreToolMetadata
            from ..core.types import ToolCategory
            
            # 映射参数类型
            registry_metadata = CoreToolMetadata(
                name=tool_name,
                description=getattr(source_metadata, 'description', f'{tool_name} tool'),
                category=self._map_category(getattr(source_metadata, 'category', 'general')),
                version=getattr(source_metadata, 'version', '1.0.0'),
                author=getattr(source_metadata, 'author', 'SD-WAN Analyzer'),
                timeout=float(getattr(source_metadata, 'timeout', getattr(source_metadata, 'timeout_seconds', 30.0))),
                requires_permission=getattr(source_metadata, 'requires_permission', ['network']),
                input_schema=getattr(source_metadata, 'input_schema', {})
            )
            
            # 检查工具实现是否可调用
            if not callable(adapter.execute_sync):
                logger.error(f"工具 {tool_name} 的实现不可调用")
                return False
            
            # 注册工具到全局注册表
            self.registry.register_tool(
                registry_metadata,
                adapter.execute_sync,
                module_path
            )
            
            # 记录到发现列表
            self.discovered_tools[tool_name] = adapter
            
            logger.info(f"注册工具: {tool_name}")
            return True
            
        except Exception as e:
            logger.error(f"注册工具类失败 {tool_class.__name__}: {e}")
            return False
            
    def _map_category(self, category: Any) -> str:
        """映射工具类别"""
        if isinstance(category, ToolCategory):
            return category.value
        elif isinstance(category, str):
            return category
        else:
            return "general"
            
    def get_tool_adapter(self, tool_name: str) -> Optional[ToolAdapter]:
        """获取工具适配器"""
        return self.discovered_tools.get(tool_name)
        
    def list_discovered_tools(self) -> List[str]:
        """列出所有发现的工具"""
        return list(self.discovered_tools.keys())


# 全局工具自动发现实例
tool_discovery = ToolAutoDiscovery(tool_registry)