1️⃣ DomainModel 粒度规范（核心数据模型）
1.1 接口模型 Interface
字段	类型	必填	约束	说明
name	str	是	唯一标识	接口名称，例如 GigabitEthernet0/0
ip	List[IPvAnyAddress]	否	0~多 IP	支持多 IP，统一 IPv4/IPv6 格式
mask	List[str]	否	与 ip 对应	子网掩码，数量和 ip 对应
status	"up" / "down"	是	必须为 up/down	接口启用状态
subinterfaces	List[str]	否	可空	子接口列表
mtu	int（可选）	否	68~9216	可选超大 MTU
description	str（可选）	否	任意字符串	接口描述
mac	str（可选）	否	正确 MAC 格式	用于唯一性判断

校验规则：

IP 自动归一化为标准 IPv4/IPv6
status 统一映射 up / down
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

每个 DomainModel 必须实现 validate() 方法

2️⃣ Adapter 粒度规范
2.1 BaseAdapter 接口
class BaseAdapter:
    def parse_interfaces(self, raw_data: str) -> List[Interface]: pass
    def parse_routes(self, raw_data: str) -> List[Route]: pass
    def parse_vlans(self, raw_data: str) -> List[VLAN]: pass
    def parse_tunnels(self, raw_data: str) -> List[Tunnel]: pass
    def parse_vrfs(self, raw_data: str) -> List[VRF]: pass
2.2 VendorAdapter 要求
必须继承 BaseAdapter
输出 DomainModel 必须通过 validate()
幂等、职责单一
禁止直接使用厂商原字段名
3️⃣ Pipeline 粒度规范
3.1 Pipeline 类型
类型	输入	输出	说明
AnalysisPipeline	DomainModel	RuleResult 列表	一键分析
FunctionalPipeline	DomainModel / TestTarget	TestResult 列表	功能测试
TopologyPipeline	DomainModel	TopologyModel	拓扑分析
3.2 Step 约束
输入标准 DomainModel 或上一步输出
输出更新后的 DomainModel 或 Result
不直接操作 Adapter 原始数据
可单独执行，幂等性保证
4️⃣ Rule 执行规范
4.1 Rule 类型
类型	输入	输出	说明
单对象规则	DomainModel 单对象	RuleResult	Interface 状态等
全局规则	DomainModel 集合	RuleResult 列表	路由下一跳可达性等
组合规则	多对象依赖	RuleResult	VLAN + Interface 配置匹配
4.2 Rule 输出标准
class RuleResult:
    rule_name: str
    severity: "HIGH" / "MEDIUM" / "LOW"
    message: str
    target: str
相同输入 → 相同输出
输出序列化、排序保证幂等
5️⃣ Dispatcher / Engine 规范
5.1 Dispatcher
管理多 pipeline
单向调用 pipeline
幂等性：相同输入 → 相同输出
异常隔离，不影响其他 pipeline
5.2 Engine
Step 内部调度
单向执行
幂等性保证
日志记录 Step 执行状态、输入输出、异常
6️⃣ 模块依赖规范
模块	可依赖	不可依赖
domain	无	无
device_adapter/base	domain	vendors/pipelines/rules
device_adapter/vendors	base, domain	pipelines/rules
pipelines/*	domain, vendors, rules	跨 pipeline
rules	domain	vendors/adapters/pipelines
executor	domain, vendors	rules/pipelines
engine/dispatcher	pipelines	domain/vendors/rules/executor
单向依赖，职责清晰
所有依赖必须文档化
7️⃣ 校验与不变性
DomainModel validate()
Pipeline Step 校验：输入合法，输出标准化
Rule 校验：输出 RuleResult，severity 在枚举内
不变性：
输入 DomainModel 不可原地修改
Pipeline 执行顺序固定
相同输入 → 相同输出
模块依赖单向
8️⃣ 扩展规范
新 Pipeline / Adapter / Rule 必须注册到配置
输出必须标准化
支持 Step 独立执行
幂等性和日志完整
9️⃣ 日志规范
统一结构化格式（JSON/YAML）
必须包含：
timestamp, module, pipeline_name/step_name, input, output, status, error_message
支持调试、审计和幂等性验证