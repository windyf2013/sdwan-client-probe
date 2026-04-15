import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 业务目标配置
BUSINESS_TARGETS = [
    ("baidu.com", "国内业务"),
    ("youtube.com", "跨境业务"),
    ("tiktok.com", "直播业务")
]

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

# 如果必须在这里加载规则文件，请使用 get_resource_path
# from sdwan_analyzer.utils.path_utils import get_resource_path
# rule_path = get_resource_path(os.path.join("docs", "my-rules.md"))