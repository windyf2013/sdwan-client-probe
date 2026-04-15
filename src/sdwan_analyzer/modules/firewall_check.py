import subprocess

def check_windows_firewall() -> bool:
    """True=开启，False=关闭"""
    try:
        out = subprocess.check_output(
            ["netsh", "advfirewall", "show", "allprofiles", "state"],
            text=True, encoding="gbk", errors="ignore"
        )
        return "on" in out.lower()
    except:
        return True  # 异常默认视为开启