数据结构&模型规范
1️⃣ DomainModel 粒度规范（核心数据模型）
1.1 接口模型 Interface
字段	类型	必填	约束	说明
name	str	是	唯一标识	接口名称，例如 GigabitEthernet0/0
ip	List[IPvAnyAddress]	否	0~多 IP	支持多 IP，统一 IPv4/IPv6 格式
mask	List[str]	否	与 ip 对应	子网掩码，数量和 ip 对应
status	"up" / "down"	是	必须为 up 或 down	接口启用状态
subinterfaces	List[str]	否	可空	子接口列表
mtu	int（可选）	否	68~9216	可选超大 MTU
description	str（可选）	否	任意字符串	接口描述
mac	str（可选）	否	正确 MAC 格式	用于唯一性判断

校验规则：

所有 IP 自动归一化为标准 IPv4/IPv6
status 统一映射 “up” / “down”
子接口列表排序保证幂等性
1.2 路由模型 Route
字段	类型	必填	约束	说明
prefix	str	是	CIDR 格式	目标网络前缀
next_hop	IPvAnyAddress	是	有效 IP	下一跳地址
interface	str（可选）	否	已存在 Interface	出接口
protocol	"static" / "ospf" / "bgp" / "rip"	是	协议类型	路由来源
metric	int（可选）	否	>=0	路由度量
admin_distance	int（可选）	否	0~255	管理距离

校验规则：

prefix 必须合法 CIDR
next_hop 必须可达（可选 ping 验证）
协议类型必须在枚举内
1.3 VLAN 模型
字段	类型	必填	约束	说明
id	int	是	1~4095	VLAN 编号
name	str（可选）	否	非空字符串	VLAN 名称
interfaces	List[str]	否	已存在接口	VLAN 绑定接口列表
1.4 Tunnel 模型
字段	类型	必填	约束	说明
type	"ipsec" / "gre" / "vxlan"	是	协议类型	隧道类型
local_ip	IPvAnyAddress	是	有效 IP	本地 IP
remote_ip	IPvAnyAddress	是	有效 IP	对端 IP
status	"up" / "down"	是	状态	隧道状态
1.5 VRF 模型
字段	类型	必填	约束	说明
name	str	是	唯一标识	VRF 名称
rd	str（可选）	否	route-distinguisher 格式	VRF 唯一标识符
interfaces	List[str]	否	已存在接口	绑定接口列表
routes	List[Route]	否	Route 列表	VRF 内路由表

每个 DomainModel 均必须实现 validate() 方法保证合法性

2️⃣ Adapter 粒度规范（厂商数据解析）
2.1 BaseAdapter 接口规范
class BaseAdapter:
    def parse_interfaces(self, raw_data: str) -> List[Interface]:
        """解析接口信息，返回标准 Interface 对象列表"""
        pass

    def parse_routes(self, raw_data: str) -> List[Route]:
        """解析路由信息，返回标准 Route 对象列表"""
        pass

    def parse_vlans(self, raw_data: str) -> List[VLAN]:
        pass

    def parse_tunnels(self, raw_data: str) -> List[Tunnel]:
        pass

    def parse_vrfs(self, raw_data: str) -> List[VRF]:
        pass
2.2 VendorAdapter 实现要求
必须继承 BaseAdapter
幂等性：相同 raw_data 输出完全一致
职责单一：只解析数据，不做规则判断
输出 DomainModel 必须通过 validate()
字段标准化：禁止直接使用厂商原字段名
3️⃣ 输出结果标准化
3.1 RuleResult
class RuleResult:
    rule_name: str
    severity: "HIGH" / "MEDIUM" / "LOW"
    message: str
    target: str  # 影响对象，例如接口名
幂等性：相同 DomainModel + 相同 Rule → 输出完全一致
可序列化：JSON/YAML
排序：保证序列化前后结果幂等
3.2 TestResult（功能 Pipeline）
class TestResult:
    test_name: str
    target: str
    status: "success" / "fail"
    latency_ms: float (可选)
    loss_percent: float (可选)
功能 Pipeline 输出也必须结构化
序列化、排序保证幂等性
4️⃣ 核心模块边界与依赖规范
模块	可依赖	不可依赖	说明
domain	无	无	核心数据模型，所有模块共享
device_adapter/base	domain	vendors/pipelines/rules	基础解析能力
device_adapter/vendors	base, domain	pipelines/rules	厂商实现
pipelines/*	domain, vendors, rules	跨 pipeline	单向执行
rules	domain	vendors/adapters/pipelines	仅依赖 DomainModel
executor	domain, vendors	rules/pipelines	功能执行层
engine/dispatcher	pipelines	domain/vendors/rules/executor	调度多 pipeline

所有依赖必须单向、可追踪，避免跨模块调用破坏一致性
1️⃣ Pipeline 粒度规范
1.1 Pipeline 类型
Pipeline 类型	说明	输入	输出
AnalysisPipeline	一键分析 pipeline	DomainModel	RuleResult 列表
FunctionalPipeline	功能 pipeline（如 ping/traceroute 测试）	DomainModel / TestTarget	TestResult 列表
TopologyPipeline	网络拓扑分析 pipeline	DomainModel	TopologyModel

约束：

每个 pipeline 单向执行，禁止跨 pipeline 调用其他 pipeline
输入必须是标准化的 DomainModel
输出必须结构化并可序列化
Pipeline 内步骤必须幂等（相同输入 → 相同输出）
1.2 Pipeline 步骤粒度
每个 pipeline 分为 步骤 Step，每个 Step 单独执行 DomainModel 转换或 Rule 调用
Step 输入：标准化 DomainModel / 上一步输出
Step 输出：更新后的 DomainModel 或 Result 对象
Step 规则：
不直接操作 Adapter 原始数据
不跨 Step 依赖未暴露的状态
Step 失败必须可捕获并记录，不影响整体幂等性
1.3 Pipeline 调度示例
class AnalysisPipeline:
    def __init__(self, domain: DomainModel):
        self.domain = domain
        self.results: List[RuleResult] = []

    def run(self):
        self.step_parse_routes()
        self.step_check_routes()
        self.step_check_interfaces()
        return self.results
每个 Step 输出 RuleResult / TestResult
结果按排序存储保证幂等性
可单独执行任意 Step（功能 pipeline 支持按需执行）
2️⃣ Rule 执行粒度规范
2.1 Rule 类型
Rule 类型	输入	输出	说明
单对象规则	DomainModel 单个对象	RuleResult	例如 Interface 状态检查
全局规则	DomainModel 集合	RuleResult 列表	例如 路由下一跳可达性检查
组合规则	依赖多个对象	RuleResult	例如 VLAN + Interface 配置匹配
2.2 Rule 执行约束
幂等性：相同 DomainModel → 相同输出
独立性：Rule 不依赖其他 Rule 输出
输入约束：仅操作 DomainModel，不直接调用 Adapter 或 Vendor 数据
输出标准化：返回 RuleResult 对象列表，保证序列化一致性
错误处理：任何异常必须捕获并记录，不破坏 Pipeline 执行
日志记录：每条 Rule 执行必须记录目标对象和执行状态
2.3 RuleResult 标准字段复用
class RuleResult:
    rule_name: str
    severity: "HIGH" / "MEDIUM" / "LOW"
    message: str
    target: str
severity 枚举确保统一风险等级
message 可包含详细诊断信息
target 指向唯一 DomainModel 对象标识（如接口名、VLAN id）
2.4 Rule 执行流程示例
def RouteNextHopReachableRule(route: Route) -> RuleResult:
    if not ping(route.next_hop):
        return RuleResult(
            rule_name="RouteNextHopReachableRule",
            severity="HIGH",
            message=f"Next-hop {route.next_hop} seems unreachable",
            target=route.prefix
        )
    return RuleResult(
        rule_name="RouteNextHopReachableRule",
        severity="LOW",
        message=f"Next-hop {route.next_hop} reachable",
        target=route.prefix
    )
可独立调用
与 Pipeline 步骤组合，保证幂等性
输出统一 RuleResult
3️⃣ Pipeline 与 Rule 幂等性规范
Pipeline 输入：标准化 DomainModel
Pipeline 输出：RuleResult / TestResult，保证序列化顺序一致
Rule 输出：独立且幂等
Step 执行异常不会破坏整个 Pipeline
日志记录必须包含：
输入对象标识
Rule/Step 执行状态
时间戳
1️⃣ Dispatcher / Engine 粒度规范
1.1 Dispatcher 角色
管理 多个 pipeline 的统一入口
按 执行顺序或策略 调度 AnalysisPipeline / FunctionalPipeline / TopologyPipeline
输入：DomainModel / pipeline 配置
输出：统一的 RuleResult / TestResult 集合
1.2 Dispatcher 约束
单向调用：Dispatcher 调用 Pipeline，不允许 Pipeline 调用 Dispatcher
幂等性：相同 DomainModel + 配置 → 相同输出结果
错误隔离：Pipeline 异常必须捕获，不影响其他 pipeline 执行
可扩展性：新 pipeline 注册时只需增加到 Dispatcher 配置
日志记录：执行状态、开始/结束时间、结果数量、错误信息
1.3 Engine 角色
负责 Pipeline 内部执行顺序管理
Step 级调度与资源控制
支持 按需执行单步 Step 或完整 Pipeline
1.4 Engine 约束
Step 单向执行：Step 仅依赖上一步输出
幂等性：Step 输入 → 输出固定
错误处理：Step 异常必须捕获并返回标准错误对象
可追踪性：Step 执行日志必须记录：
Step 名称
输入对象标识
输出对象标识
执行时间
异常或错误信息
2️⃣ 模块边界与依赖规则
模块	可依赖	不可依赖	说明
domain	无	无	核心数据模型，所有模块共享
device_adapter/base	domain	vendors/pipelines/rules	基础解析能力
device_adapter/vendors	base, domain	pipelines/rules	厂商实现
pipelines/*	domain, vendors, rules	跨 pipeline	单向执行
rules	domain	vendors/adapters/pipelines	仅依赖 DomainModel
executor	domain, vendors	rules/pipelines	功能执行层
engine/dispatcher	pipelines	domain/vendors/rules/executor	调度多 pipeline

约束说明：

单向依赖：禁止跨模块调用未声明依赖模块
职责清晰：每个模块只实现自己职责
依赖追踪：所有模块依赖必须文档化
3️⃣ 执行日志规范
3.1 日志内容要求
统一格式（JSON 或结构化文本）
日志必须包含以下字段：
timestamp：事件时间
module：所属模块
pipeline_name / step_name：步骤或 pipeline 名称
input：输入对象标识（DomainModel）
output：输出对象标识（RuleResult / TestResult）
status：success / fail
error_message：异常信息（可选）
3.2 日志用途
支持 调试与追踪
支持 执行结果复现
保证 幂等性验证
4️⃣ 幂等性与一致性保证
Dispatcher / Engine 级别：
相同 DomainModel + 相同 Pipeline 配置 → 输出固定
Step 异常捕获 → 输出标准化错误，不影响整体执行
日志记录完整 → 支持审计与追踪
Pipeline 输出序列化 → JSON/YAML 排序固定，保证幂等
1️⃣ 扩展规范
1.1 新 Pipeline 注册规范
所有新 pipeline 必须：
实现 PipelineInterface（定义 run() 方法）
输入必须是标准 DomainModel
输出必须结构化（RuleResult / TestResult / TopologyModel）
注册到 Dispatcher 配置中
禁止直接修改已有 pipeline 步骤，只允许新增 Step 或新 pipeline
class PipelineInterface:
    def run(self) -> List:
        """执行 pipeline，返回结果列表"""
        pass
1.2 新 Adapter / Rule 注册规范
Adapter：
必须继承 BaseAdapter
输出 DomainModel 必须通过 validate()
幂等、职责单一
Rule：
输入 DomainModel
输出 RuleResult
注册到 Pipeline 时必须遵守依赖约束
新增模块：
必须在模块依赖文档中声明
避免跨模块调用
2️⃣ 校验机制
2.1 DomainModel 校验
每个 DomainModel 必须实现 validate()：
检查必填字段
检查字段类型
检查约束条件（范围、枚举、格式）
校验异常返回统一 ValidationError 对象
class ValidationError(Exception):
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
2.2 Pipeline 校验
Pipeline 输入必须通过 DomainModel validate()
Pipeline 输出必须是标准化 Result 对象
Pipeline 内每个 Step 必须可独立校验：
输入 DomainModel 是否完整
输出 Result 是否符合规范
2.3 Rule 校验
Rule 输出必须：
返回标准 RuleResult
包含必要字段：rule_name, severity, message, target
severity 必须在枚举内
Rule 异常必须捕获并生成标准 RuleResult（异常状态）
3️⃣ 不变性规则
数据不变性：
Pipeline 执行过程中，输入的 DomainModel 不可被原地修改
必须生成副本用于 Step / Rule 执行
执行顺序不变性：
Pipeline 步骤顺序固定
Step 不能跨 pipeline 调用
输出不变性：
相同输入 → 相同输出
排序和字段固定，保证幂等性
模块依赖不变性：
模块间依赖单向，禁止破坏模块边界
4️⃣ 扩展约束示例
# 新增功能 pipeline
class LatencyTestPipeline(PipelineInterface):
    def __init__(self, domain: DomainModel):
        self.domain = domain
        self.results: List[TestResult] = []

    def run(self):
        for iface in self.domain.interfaces:
            self.results.append(self.step_ping(iface))
        return self.results

    def step_ping(self, iface):
        # 输入 DomainModel 副本，输出标准 TestResult
        return TestResult(
            test_name="ping",
            target=iface.name,
            status="success",
            latency_ms=12.3
        )
输入 DomainModel 副本
输出 TestResult，保证幂等性
Pipeline 顺序固定，可独立 Step 执行