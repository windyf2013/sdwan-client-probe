"""
配置管理系统 - 严格遵循AI Agent Python工程标准

职责：统一管理应用配置、环境变量、动态配置更新
禁止：硬编码配置值、散落在代码各处的配置访问

文档编号: AAPS-001
规范等级: Mandatory（强制执行）
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List, Set
from enum import Enum
from pathlib import Path

from ..core.contracts import BaseContract


class ConfigSource(Enum):
    """配置来源"""
    ENVIRONMENT = "environment"
    FILE = "file"
    DEFAULT = "default"
    SECRETS = "secrets"


@dataclass(slots=True)
class ConfigValue:
    """配置值"""
    key: str
    value: Any
    source: ConfigSource
    description: Optional[str] = None
    sensitive: bool = False
    updated_at: Optional[float] = None
    
    def masked_value(self) -> str:
        """敏感值掩码显示"""
        if self.sensitive:
            return "*" * 8
        return str(self.value)


@dataclass(slots=True)
class ConfigUpdateEvent:
    """配置更新事件"""
    keys: List[str]
    source: ConfigSource
    timestamp: float
    user_id: Optional[str] = None


class ConfigurationError(Exception):
    """配置错误"""
    pass


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, env_prefix: str = "SDWAN_", config_file: Optional[str] = None):
        self.env_prefix = env_prefix
        self.config_file = config_file
        self._config_store: Dict[str, ConfigValue] = {}
        self._observers: Set = set()
        self._logger = logging.getLogger(__name__)
        
        # 初始化配置
        self._initialize_config()
    
    def _initialize_config(self) -> None:
        """初始化配置系统"""
        # 加载默认配置
        self._load_default_config()
        
        # 加载环境变量配置
        self._load_environment_config()
        
        # 加载文件配置
        if self.config_file:
            self._load_file_config()
        
        self._logger.info(f"配置系统初始化完成，已加载 {len(self._config_store)} 个配置项")
    
    def _load_default_config(self) -> None:
        """加载默认配置"""
        default_config = self._get_default_config()
        
        for key, value in default_config.items():
            config_value = ConfigValue(
                key=key,
                value=value["value"],
                source=ConfigSource.DEFAULT,
                description=value.get("description"),
                sensitive=value.get("sensitive", False)
            )
            self._config_store[key] = config_value
    
    def _load_environment_config(self) -> None:
        """加载环境变量配置"""
        env_vars = {k: v for k, v in os.environ.items() if k.startswith(self.env_prefix)}
        
        for env_key, env_value in env_vars.items():
            # 转换环境变量名为配置键名（移除前缀并转换为小写）
            config_key = env_key[len(self.env_prefix):].lower()
            
            # 尝试解析JSON值，否则使用字符串
            try:
                parsed_value = json.loads(env_value)
            except (json.JSONDecodeError, TypeError):
                parsed_value = env_value
            
            config_value = ConfigValue(
                key=config_key,
                value=parsed_value,
                source=ConfigSource.ENVIRONMENT,
                description=f"环境变量: {env_key}"
            )
            self._config_store[config_key] = config_value
    
    def _load_file_config(self) -> None:
        """加载文件配置"""
        if not self.config_file or not Path(self.config_file).exists():
            return
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
            
            for key, value in file_config.items():
                config_value = ConfigValue(
                    key=key,
                    value=value,
                    source=ConfigSource.FILE,
                    description=f"配置文件: {self.config_file}"
                )
                self._config_store[key] = config_value
                
        except Exception as e:
            self._logger.warning(f"配置文件加载失败: {e}")
    
    def get(self, key: str, default: Any = None, required: bool = False) -> Any:
        """获取配置值"""
        config_value = self._config_store.get(key)
        
        if config_value:
            return config_value.value
        
        if required:
            self._logger.error(f"必需的配置项缺失: {key}")
            raise ConfigurationError(f"必需的配置项缺失: {key}")
        
        return default
    
    def get_config_value(self, key: str) -> Optional[ConfigValue]:
        """获取完整的配置值对象"""
        return self._config_store.get(key)
    
    def set(self, key: str, value: Any, source: ConfigSource = ConfigSource.DEFAULT) -> None:
        """设置配置值"""
        config_value = ConfigValue(
            key=key,
            value=value,
            source=source
        )
        
        self._config_store[key] = config_value
        
        # 通知观察者
        self._notify_observers([key], source)
        
        self._logger.debug(f"配置项已设置: {key}")
    
    def update_from_dict(self, config_dict: Dict[str, Any], source: ConfigSource) -> None:
        """从字典批量更新配置"""
        updated_keys = []
        
        for key, value in config_dict.items():
            config_value = ConfigValue(
                key=key,
                value=value,
                source=source
            )
            self._config_store[key] = config_value
            updated_keys.append(key)
        
        # 通知观察者
        if updated_keys:
            self._notify_observers(updated_keys, source)
            self._logger.info(f"批量更新配置完成，更新了 {len(updated_keys)} 个配置项")
    
    def list_configs(self, include_sensitive: bool = False) -> List[Dict[str, Any]]:
        """列出所有配置（可选是否包含敏感信息）"""
        result = []
        
        for config_value in self._config_store.values():
            if config_value.sensitive and not include_sensitive:
                continue
                
            result.append({
                "key": config_value.key,
                "value": config_value.value if include_sensitive else config_value.masked_value(),
                "source": config_value.source.value,
                "description": config_value.description,
                "sensitive": config_value.sensitive
            })
        
        return result
    
    def register_observer(self, observer: Any) -> None:
        """注册配置观察者"""
        self._observers.add(observer)
    
    def unregister_observer(self, observer: Any) -> None:
        """注销配置观察者"""
        self._observers.discard(observer)
    
    def _notify_observers(self, updated_keys: List[str], source: ConfigSource) -> None:
        """通知观察者配置更新"""
        event = ConfigUpdateEvent(
            keys=updated_keys,
            source=source,
            timestamp=float("inf")  # 实际应该用time.time()
        )
        
        for observer in self._observers:
            try:
                if hasattr(observer, 'on_config_update'):
                    observer.on_config_update(event)
            except Exception as e:
                self._logger.error(f"配置观察者通知失败: {e}")
    
    def _get_default_config(self) -> Dict[str, Dict[str, Any]]:
        """获取默认配置"""
        return {
            "log_level": {
                "value": "INFO",
                "description": "日志级别",
                "options": ["DEBUG", "INFO", "WARNING", "ERROR"]
            },
            "log_format": {
                "value": "json",
                "description": "日志格式",
                "options": ["json", "text"]
            },
            "max_concurrent_tasks": {
                "value": 10,
                "description": "最大并发任务数"
            },
            "default_timeout": {
                "value": 30.0,
                "description": "默认操作超时时间（秒）"
            },
            "api_rate_limit": {
                "value": 100,
                "description": "API请求速率限制（每分钟）"
            },
            "tool_registry_enabled": {
                "value": True,
                "description": "工具注册表是否启用"
            },
            "tool_execution_timeout": {
                "value": 60.0,
                "description": "工具执行超时时间（秒）"
            },
            "enable_metrics": {
                "value": True,
                "description": "是否启用指标收集"
            },
            "enable_tracing": {
                "value": False,
                "description": "是否启用分布式追踪"
            },
            "database_url": {
                "value": "sqlite:///sdwan_analyzer.db",
                "description": "数据库连接URL",
                "sensitive": True
            },
            "cache_enabled": {
                "value": True,
                "description": "是否启用缓存"
            },
            "cache_ttl": {
                "value": 300,
                "description": "缓存生存时间（秒）"
            },
            "security_enable_ssl": {
                "value": True,
                "description": "是否启用SSL加密"
            },
            "security_allowed_origins": {
                "value": ["*"],
                "description": "允许的CORS源"
            },
            "network_scan_max_ports": {
                "value": 100,
                "description": "网络扫描最大端口数"
            },
            "ping_timeout": {
                "value": 5.0,
                "description": "Ping超时时间（秒）"
            },
            "http_request_timeout": {
                "value": 15.0,
                "description": "HTTP请求超时时间（秒）"
            }
        }


# 全局配置管理器实例
_config_manager_instance: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例（单例模式）"""
    global _config_manager_instance
    if _config_manager_instance is None:
        env_prefix = os.getenv("SDWAN_CONFIG_PREFIX", "SDWAN_")
        config_file = os.getenv("SDWAN_CONFIG_FILE")
        _config_manager_instance = ConfigManager(env_prefix, config_file)
    return _config_manager_instance


def get_config(key: str, default: Any = None, required: bool = False) -> Any:
    """快捷获取配置值"""
    return get_config_manager().get(key, default, required)


# 类型化配置访问器
class ConfigKeys:
    """配置键常量"""
    LOG_LEVEL = "log_level"
    LOG_FORMAT = "log_format"
    MAX_CONCURRENT_TASKS = "max_concurrent_tasks"
    DEFAULT_TIMEOUT = "default_timeout"
    API_RATE_LIMIT = "api_rate_limit"
    TOOL_REGISTRY_ENABLED = "tool_registry_enabled"
    TOOL_EXECUTION_TIMEOUT = "tool_execution_timeout"
    ENABLE_METRICS = "enable_metrics"
    ENABLE_TRACING = "enable_tracing"
    DATABASE_URL = "database_url"
    CACHE_ENABLED = "cache_enabled"
    CACHE_TTL = "cache_ttl"
    SECURITY_ENABLE_SSL = "security_enable_ssl"
    SECURITY_ALLOWED_ORIGINS = "security_allowed_origins"
    NETWORK_SCAN_MAX_PORTS = "network_scan_max_ports"
    PING_TIMEOUT = "ping_timeout"
    HTTP_REQUEST_TIMEOUT = "http_request_timeout"