from sdwan_analyzer.models.diagnose import DiagnoseContext, FinalDiagnosis

class SdwanDecisionEngine:
    def __init__(self, ctx: DiagnoseContext):
        self.ctx = ctx

    def analyze(self) -> FinalDiagnosis:
        """主推理入口（企业级SD-WAN故障决策树）"""
        sys = self.ctx.sys_result
        sdwan = self.ctx.sdwan_result
        ping = self.ctx.ping_result

        # ==========================
        # 层级判决：从本地到远端
        # ==========================

        # 1. 本地接入域故障
        if not sys.gateway_reachable:
            return FinalDiagnosis(
                level="故障",
                fault_domain="本地接入域",
                reason="PC到CPE网关链路中断",
                suggestion="检查网线、WiFi、交换机或CPE本地端口状态",
                score=0
            )

        # 2. 路由缺失
        if not sys.default_route_valid:
            return FinalDiagnosis(
                level="故障",
                fault_domain="本地配置域",
                reason="默认路由不存在，无法访问SD-WAN承载网络",
                suggestion="检查网卡路由配置或CPE下发策略",
                score=10
            )

        # 3. DNS故障（影响业务可达性判断）
        if not sys.dns_working:
            return FinalDiagnosis(
                level="异常",
                fault_domain="本地解析域",
                reason="DNS解析异常，可能导致业务域名无法访问",
                suggestion="检查DNS地址或手动配置公共DNS",
                score=30
            )

        # 4. CPE在线但隧道端口不通 → SD-WAN隧道未建立
        if sdwan.cpe_reachable and not sdwan.ipsec_port_open:
            return FinalDiagnosis(
                level="故障",
                fault_domain="CPE隧道域",
                reason="CPE可达，但IPsec隧道端口不通，Overlay未建立",
                suggestion="检查CPE上线状态、控制器注册、隧道配置及NAT环境",
                score=20
            )

        # 5. 承载网络正常，但业务完全不可达
        if ping and not ping.is_reachable and ping.loss >= 99:
            return FinalDiagnosis(
                level="故障",
                fault_domain="SD-WAN跨境/POP域",
                reason="承载网络正常，但Overlay业务完全中断",
                suggestion="排查POP节点、云专网、跨境承载链路及对端路由",
                score=15
            )

        # 6. 严重丢包
        if ping and ping.loss > 2:
            return FinalDiagnosis(
                level="异常",
                fault_domain="承载链路域",
                reason=f"链路质量劣化，丢包率{ping.loss:.1f}%",
                suggestion="检查运营商链路拥塞、信号干扰或带宽瓶颈",
                score=50
            )

        # 7. 延迟偏高
        if ping and ping.avg_rtt > 300:
            return FinalDiagnosis(
                level="一般",
                fault_domain="跨境链路域",
                reason=f"端到端延迟偏高({ping.avg_rtt:.0f}ms)",
                suggestion="可优化路由调度或避开高峰时段",
                score=70
            )

        # 8. 全部正常
        return FinalDiagnosis(
            level="正常",
            fault_domain="全链路正常",
            reason="SD-WAN客户端、承载网络、业务链路均正常",
            suggestion="保持当前运行状态",
            score=100
        )