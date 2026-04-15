企业级 Python 软件开发规范
1. 项目结构规范
project_name/
│
├─ src/                    # 主代码目录
│   ├─ project_name/       # 核心包
│   │   ├─ __init__.py
│   │   ├─ core/           # 核心模块
│   │   ├─ utils/          # 工具函数
│   │   ├─ api/            # 对外接口
│   │   └─ config.py        # 配置入口
│   └─ main.py             # 主入口
│
├─ tests/                  # 测试目录
│   ├─ unit/               # 单元测试
│   ├─ integration/        # 集成测试
│   └─ conftest.py         # pytest 配置文件
│
├─ docs/                   # 文档
│   └─ index.md
├─ scripts/                # 辅助脚本
├─ requirements.txt        # 依赖列表
├─ pyproject.toml          # Poetry / PEP 517 配置
├─ setup.py                # 打包安装
├─ .gitignore              # Git 忽略文件
└─ README.md               # 项目说明
src/ 结构可避免直接运行时导入冲突
包名、模块名使用小写+下划线，类名 PascalCase，函数/变量 snake_case
2. 模块设计规范
2.1 单一职责原则
每个模块只负责一个功能域
模块行数 ≤ 500
2.2 包设计
内部模块以 _ 开头
__init__.py 只暴露核心接口
# core/__init__.py
from .processor import DataProcessor
2.3 模块依赖
核心业务模块依赖工具模块，不反向依赖
避免循环依赖
层级关系：
core -> utils
api -> core
tests -> core / api / utils
3. 数据结构设计
3.1 核心实体
使用 dataclass 封装核心数据
核心业务实体建议不可变（frozen=True）
from dataclasses import dataclass

@dataclass(frozen=True)
class Route:
    destination: str
    next_hop: str
    metric: int
3.2 类型安全
全面使用类型注解
对复杂结构使用 List, Dict, Tuple, Optional, Union
from typing import List, Dict

def parse_routes(config: str) -> List[Dict[str, str]]:
    ...
3.3 数据层次
Entity (Route, Device) -> Collection (RouteTable) -> Service (RouteManager)
4. 函数设计规范
4.1 函数职责
单一功能
函数长度 ≤ 30 行
参数数量 ≤ 5（复杂参数用对象封装）
4.2 参数与返回
可选参数使用关键字参数
默认不可变对象
def add_route(route: Route, table: Optional[List[Route]] = None):
    table = table or []
    table.append(route)
返回值可使用 NamedTuple 或自定义 Result 类型
from typing import NamedTuple, Union

class Result(NamedTuple):
    success: bool
    message: str
    data: Union[None, object]
4.3 异常处理
不吞异常
自定义异常
class RouteParseError(Exception):
    pass
4.4 命名规范
动词 + 名词：parse_config(), validate_route()
避免模糊命名：do_it(), handle_data() ❌
5. 编码规范
遵循 PEP8
缩进 4 空格
最大行长 79-99
顶级函数/类两行空行
注释：
行内注释 # 注释
文档字符串 """多行描述"""
类型注解必须使用
日志使用 logging
import logging

logger = logging.getLogger(__name__)
logger.info("开始任务")
6. 依赖与环境
使用虚拟环境：venv 或 conda
依赖管理：
小型项目：requirements.txt
企业级项目：Poetry + pyproject.toml
锁定版本保证环境一致性
自动化安装：
poetry install
7. 测试规范
使用 pytest 或 unittest
测试覆盖率 ≥ 80%
目录结构：
tests/unit/
tests/integration/
单元测试示例：
def test_add_positive():
    assert add(1, 2) == 3
CI 集成，测试失败禁止合并
8. 文档规范
函数/类文档字符串必写
文档风格：Google 或 NumPy 风格
README.md：项目概述、安装、使用示例
docs/: 详细设计文档、接口文档
可选 Sphinx 生成 HTML 文档
9. 配置管理
配置文件独立：YAML/JSON/TOML
支持多环境（dev/staging/prod）
敏感信息使用环境变量
database:
  host: localhost
  port: 3306
  user: root
  password: ${DB_PASSWORD}
10. 版本管理与发布
Git 分支：
main/master：生产
develop：开发
feature/*：功能
hotfix/*：紧急修复
Commit 规范：
<type>[optional scope]: <subject>
feat(auth): add JWT token verification
打包：
poetry build
poetry publish
CI/CD 自动化测试 + 打包
11. 代码质量工具
静态检查：flake8, pylint
类型检查：mypy
依赖安全：safety, pip-audit
自动格式化：black
black src/ tests/
flake8 src/
mypy src/
12. 安全规范
不写明文密码
严格参数验证
依赖及时更新
13. 性能与可维护性
核心模块有 benchmark
避免全局变量
高内聚、低耦合
日志、异常、配置、依赖、测试覆盖
14. 核心设计原则总结
单一职责 (SRP)
高内聚、低耦合
数据不可变优先
函数短小，接口明确
类型安全，静态检查
异常透明，日志充分