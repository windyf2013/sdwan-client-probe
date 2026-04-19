import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 1. 业务目标配置 (结构化增强版 - 保持向后兼容)
# 传统格式 (兼容旧代码)
BUSINESS_TARGETS_LEGACY = [
    ("baidu.com", "国内业务"),
    ("youtube.com", "跨境业务"),
    ("tiktok.com", "直播业务")
]

# 新结构格式 (供智能调度器使用)
BUSINESS_TARGETS = [
    {
        "target": "baidu.com", 
        "type": "domestic", 
        "priority": "high",
        "description": "国内核心业务"
    },
    {
        "target": "youtube.com", 
        "type": "cross_border", 
        "priority": "high",
        "description": "跨境视频业务"
    },
    {
        "target": "tiktok.com",
        "type": "cross_border", 
        "priority": "medium", 
        "description": "跨境直播业务"
    }
]

# 2. 智能检测策略配置 (重构新增)
DETECTION_STRATEGY = {
    "domestic": {
        "basic_checks": ["ping", "tcp", "http"],
        "deep_checks": [],  # 国内业务通常不需要 MTR/跨境分析
        "timeout": 10
    },
    "cross_border": {
        "basic_checks": ["ping", "tcp"], 
        "deep_checks": ["link_quality", "route_analysis"], # 触发深度检测
        "timeout": 30
    }
}

# 默认端口配置
DEFAULT_PORT = 443

# 网络检测配置
PING_COUNT = 4
TRACERT_TIMEOUT = 40
MTR_COUNT = 10
MTR_TIMEOUT = 60

# IPSec端口配置
IPSEC_PORTS = [500, 4500, 1701]

# 日志配置
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

# 【修改点】报告配置：默认设置为当前目录 (即 exe 所在目录或运行 cmd 的目录)
# os.getcwd() 获取当前工作目录
REPORT_DIR = os.environ.get('REPORT_DIR', os.getcwd())

# 测试模式
TEST_MODE = os.environ.get('TEST_MODE', '0') == '1'
