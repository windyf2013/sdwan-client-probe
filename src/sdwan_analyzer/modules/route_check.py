import subprocess

def check_default_route() -> bool:
    """检查是否存在默认路由（0.0.0.0）"""
    try:
        out = subprocess.check_output(
            ["route", "print", "0.0.0.0"], text=True, encoding="gbk", errors="ignore"
        )
        return "0.0.0.0" in out
    except:
        return False

def check_gateway_reachable(gateway: str) -> bool:
    """检测网关是否可通"""
    if not gateway:
        return False
    try:
        ret = subprocess.run(
            ["ping", "-n", "1", "-w", "500", gateway],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return ret.returncode == 0
    except:
        return False