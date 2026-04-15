import subprocess
import re

from sdwan_analyzer.models.diagnose import NicInfo

def get_main_nic_info() -> NicInfo:
    try:
        out = subprocess.check_output(
            ["ipconfig", "/all"], text=True, encoding="gbk", errors="ignore"
        )
    except:
        return NicInfo(0, "获取失败", "异常", [], [], [], False)

    lines = out.splitlines()
    adapters = []
    current = None

    for idx, line in enumerate(lines):
        raw = line
        line = line.strip()

        # 新网卡
        if "适配器" in line and line.endswith(":"):
            if current:
                adapters.append(current)
            current = {
                "name": line.replace(":", "").strip(),
                "status": "Connected",
                "ips": [],
                "gateways": [],
                "dns": [],
                "dhcp": False
            }
            continue

        if not current:
            continue

        # 媒体状态
        if "媒体状态" in line:
            current["status"] = "Disconnected" if "已断开" in line else "Connected"

        # DHCP
        if "DHCP" in line and "是" in line:
            current["dhcp"] = True

        # ======================
        # 强识别 IPv4
        # ======================
        if "IPv4 地址" in line:
            ips = re.findall(r"\d+\.\d+\.\d+\.\d+", line)
            current["ips"].extend(ips)

        # ======================
        # 强识别 网关（支持换行）
        # ======================
        if "默认网关" in line:
            current["gateways"] = []
            # 搜当前行
            current["gateways"] += re.findall(r"\d+\.\d+\.\d+\.\d+", line)
            # 搜下几行（适配你这种换行网关）
            for i in [1, 2]:
                if idx + i < len(lines):
                    next_line = lines[idx + i].strip()
                    # 只添加IP地址，避免包含DNS服务器信息
                    if not "DNS" in next_line and not "IPv4" in next_line:
                        current["gateways"] += re.findall(r"\d+\.\d+\.\d+\.\d+", next_line)

        # ======================
        # 强识别 DNS（支持换行）
        # ======================
        if "DNS 服务器" in line:
            current["dns"] = []
            current["dns"] += re.findall(r"\d+\.\d+\.\d+\.\d+", line)
            for i in [1, 2]:
                if idx + i < len(lines):
                    current["dns"] += re.findall(r"\d+\.\d+\.\d+\.\d+", lines[idx + i])

    if current:
        adapters.append(current)

    # 取有IP的第一个网卡
    valid = [a for a in adapters if a["ips"]]
    if valid:
        a = valid[0]
        return NicInfo(
            index=0,
            name=a["name"],
            status=a["status"],
            ip=a["ips"],
            gateway=list(set(a["gateways"])),
            dns=list(set(a["dns"])),
            is_dhcp=a["dhcp"]
        )

    return NicInfo(0, "未检测到网卡", "未知", [], [], [], False)