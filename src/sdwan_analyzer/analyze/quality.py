from sdwan_analyzer.core.ping import PingResult

MAX_LATENCY = 300
MAX_LOSS = 2.0
MAX_JITTER = 30

def calculate_health_score(ping_result: PingResult) -> dict:
    score = 100
    latency = ping_result.avg_rtt
    loss = ping_result.loss
    jitter = ping_result.jitter

    # 丢包权重最高
    if loss > 0:
        score -= min(loss * 20, 50)

    # 延迟扣分
    if latency > 100:
        score -= min((latency - 100) / 10, 30)

    # 抖动扣分
    if jitter > 10:
        score -= min((jitter - 10) / 2, 20)

    score = max(round(score, 1), 0)

    if score >= 85:
        level = "健康"
    elif score >= 60:
        level = "一般"
    elif score >= 30:
        level = "较差"
    else:
        level = "故障"

    return {
        "target": ping_result.target,
        "score": score,
        "level": level,
        "latency": latency,
        "loss": loss,
        "jitter": jitter
    }