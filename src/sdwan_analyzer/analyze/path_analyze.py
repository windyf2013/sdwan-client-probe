from sdwan_analyzer.core.mtr import MtrResult, MtrHop
from sdwan_analyzer.utils.ip_info import get_ip_country

# 跨境判断阈值
CROSS_BORDER_HOPS_THRESHOLD = 8
CRITICAL_LOSS = 2.0
CRITICAL_LATENCY = 250

def analyze_path(mtr_result: MtrResult) -> dict:
    """
    完整路径分析：
    1. 是否跨境
    2. 故障点定位
    3. 跨境段是否拥塞
    4. 路径是否异常
    """
    hops = mtr_result.hops
    target = mtr_result.target
    problem_hop = None
    border_hop = None
    is_cross_border = False

    # 遍历每一跳，定位异常节点
    for idx, hop in enumerate(hops):
        country = get_ip_country(hop.ip)

        # 判断是否出现跨境（非CN）
        if country != "CN" and not border_hop:
            border_hop = hop
            is_cross_border = True

        # 定位高丢包/高延迟节点
        if hop.loss >= CRITICAL_LOSS or hop.avg_rtt >= CRITICAL_LATENCY:
            problem_hop = hop
            break

    # 故障点位置判断
    problem_location = "unknown"
    if problem_hop:
        hop_pos = problem_hop.hop
        if hop_pos <= 4:
            problem_location = "国内接入段"
        elif hop_pos <= 10:
            problem_location = "跨境出口段"
        else:
            problem_location = "境外/云端段"

    # 是否绕路（跳数过多 = 跨境绕路）
    is_route_bad = len(hops) > 12

    return {
        "target": target,
        "is_cross_border": is_cross_border,
        "border_hop": border_hop.hop if border_hop else None,
        "problem_hop": problem_hop,
        "problem_location": problem_location,
        "is_route_bad": is_route_bad,
        "total_hops": len(hops)
    }