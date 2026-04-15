from dataclasses import dataclass
from sdwan_analyzer.core.ping import PingResult
from sdwan_analyzer.core.mtr import MtrResult

@dataclass
class DiagnoseResult:
    target: str
    level: str
    problem: str
    reason: str
    suggestion: str

def auto_diagnose(ping_result: PingResult, mtr_result: MtrResult) -> DiagnoseResult:
    target = ping_result.target
    loss = ping_result.loss
    latency = ping_result.avg_rtt

    #
    # 稳健、诚实、工程级诊断逻辑
    # 不越权、不瞎猜、只给出ICMP探测能支撑的结论
    #
    if loss >= 99:
        return DiagnoseResult(
            target=target,
            level="故障",
            problem="目标完全不可达",
            reason="业务访问中断，故障域可能位于SD-WAN跨境链路或POP节点区间",
            suggestion="建议结合Tracert结果定位超时跳点，并协同运维排查隧道、路由及承载链路"
        )

    elif loss > 2:
        return DiagnoseResult(
            target=target,
            level="异常",
            problem=f"链路不稳定（丢包 {loss:.1f}%）",
            reason="SD-WAN承载链路存在质量劣化或拥塞",
            suggestion="关注运营商线路质量、带宽占用及链路抖动情况"
        )

    elif latency > 300:
        return DiagnoseResult(
            target=target,
            level="一般",
            problem=f"延迟偏高（{latency:.0f}ms）",
            reason="跨境链路距离较长或高峰时段拥塞",
            suggestion="可根据业务策略调整路由选路或错峰调度"
        )

    else:
        return DiagnoseResult(
            target=target,
            level="健康",
            problem="无异常",
            reason="SD-WAN业务链路连通与质量正常",
            suggestion="保持当前运行状态"
        )