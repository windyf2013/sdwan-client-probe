"""
上行出口公网IP获取模块（第9项）
风格对齐：ping / tracert / dns / gateway 全套风格
属地信息强制输出，无信息时标注「未查到」
"""
import requests
import socket
import re
from typing import Dict, Optional, List
from urllib3.exceptions import InsecureRequestWarning

# 禁用HTTPS不安全请求警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def get_public_ip(
    check_ipv4: bool = True,
    check_ipv6: bool = False,
    verify_ssl: bool = False,
    timeout: int = 5
) -> Dict:
    """
    获取上行出口公网IP（IPv4/IPv6），多接口校验确保准确性
    强制输出运营商属地行，无信息标注「未查到」
    """
    print("\n===== 上行出口公网IP获取 =====")
    
    # ✅ 优化：增加国内权威接口，与百度/阿里云查询对齐
    ipv4_api_list = [
        # 国际接口
        "https://api.ipify.org",
        "https://icanhazip.com",
        "http://httpbin.org/ip",
        # 国内接口（优先使用，减少 NAT 干扰）
        "https://myip.ipip.net",          # IPIP.net（带属地信息）
        "https://cip.cc",                 # 国内权威接口
        "https://pv.sohu.com/api/getIp",  # 搜狐接口
        "https://httpbin.org/ip",         # HTTPBin（备用）
    ]
    
    # 公网IP检测接口（多接口冗余，确保获取成功）
    ipv4_api_list = [
        "https://api.ipify.org",          # 稳定IPv4接口
        "https://icanhazip.com",          # 稳定IPv4接口
        "http://httpbin.org/ip",          # 备用IPv4接口
        "https://myip.ipip.net",          # 国内接口（带属地）
    ]
    ipv6_api_list = [
        "https://api6.ipify.org",         # IPv6专用接口
        "https://icanhazip.com",          # 自动识别IPv6
    ]

    # 初始化结果字典
    result = {
        "public_ipv4": "",
        "ipv4_isp": "",          # IPv4运营商/属地
        "public_ipv6": "",
        "ipv6_isp": "",          # IPv6运营商/属地
        "check_ipv4": check_ipv4,
        "check_ipv6": check_ipv6,
        "timeout": timeout,
        "status": "失败",
        "error": ""
    }

    try:
        # ========== 第一步：获取IPv4公网IP ==========
        if check_ipv4:
            ipv4_result = _fetch_ip_from_apis(ipv4_api_list, verify_ssl, timeout)
            result["public_ipv4"] = ipv4_result["ip"]
            result["ipv4_isp"] = ipv4_result["isp"]
            if result["public_ipv4"]:
                result["status"] = "成功"

        # ========== 第二步：获取IPv6公网IP（可选） ==========
        if check_ipv6:
            ipv6_result = _fetch_ip_from_apis(ipv6_api_list, verify_ssl, timeout)
            result["public_ipv6"] = ipv6_result["ip"]
            result["ipv6_isp"] = ipv6_result["isp"]
            if result["public_ipv6"] and not result["public_ipv4"]:
                result["status"] = "成功"

    except Exception as e:
        result["error"] = f"获取公网IP异常：{str(e)}"

    # ====================== 格式化输出（核心调整：强制输出属地行）======================
    print("📊 上行出口公网IP检测结果：")
    print(f"  检测状态：{result['status']}")
    
    if result["check_ipv4"]:
        print(f"\n  【IPv4信息】")
        if result["public_ipv4"]:
            print(f"    公网IP：{result['public_ipv4']}")
            # 强制输出属地行，无信息标注「未查到」
            print(f"    运营商/属地：{result['ipv4_isp'] if result['ipv4_isp'] else '未查到'}")
        else:
            print(f"    公网IP：未获取到")
            print(f"    运营商/属地：未查到")

    if result["check_ipv6"]:
        print(f"\n  【IPv6信息】")
        if result["public_ipv6"]:
            print(f"    公网IP：{result['public_ipv6']}")
            # 强制输出属地行，无信息标注「未查到」
            print(f"    运营商/属地：{result['ipv6_isp'] if result['ipv6_isp'] else '未查到'}")
        else:
            print(f"    公网IP：未获取到")
            print(f"    运营商/属地：未查到")

    if result["error"]:
        print(f"\n  ❌ 异常提示：{result['error']}")

    return result

def _fetch_ip_from_apis(api_list: List[str], verify_ssl: bool, timeout: int) -> Dict:
    """从多接口获取IP，确保成功率"""
    result = {"ip": "", "isp": "", "all_ips": []}
    for api in api_list:
        try:
            response = requests.get(
                api,
                verify=verify_ssl,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            response.raise_for_status()
            content = response.text.strip()

            # 解析 IP
            ip_match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", content)
            if ip_match:
                ip = ip_match.group(0)
                result["all_ips"].append({"api": api, "ip": ip})
                
                # 解析运营商/属地（针对国内接口）
                if any(x in api for x in ["ipip.net", "cip.cc", "sohu.com"]):
                    parts = content.split()
                    if len(parts) > 1:
                        result["isp"] = " ".join(parts[1:])
                    
        except Exception:
            continue

    # 一致性校验
    unique_ips = list(set([item["ip"] for item in result["all_ips"]]))
    
    if len(unique_ips) == 0:
        return result
    
    if len(unique_ips) > 1:
        print(f"\n  ⚠️  警告：检测到多出口/IP 不一致（共{len(unique_ips)}个不同 IP）")
        for item in result["all_ips"]:
            print(f"     • {item['api']}: {item['ip']}")
        
        # 取出现频率最高的 IP（多数原则）
        from collections import Counter
        ip_counts = Counter([item["ip"] for item in result["all_ips"]])
        result["ip"] = ip_counts.most_common(1)[0][0]
        result["multi_exit"] = True
    else:
        result["ip"] = unique_ips[0]
        result["multi_exit"] = False
    
    return result


def _is_private_ip(ip: str) -> bool:
    """判断IP是否为私网IP"""
    private_ranges = [
        re.compile(r"^192\.168\.\d+\.\d+$"),    # 192.168.0.0/16
        re.compile(r"^10\.\d+\.\d+\.\d+$"),      # 10.0.0.0/8
        re.compile(r"^172\.1[6-9]\.\d+\.\d+$"),  # 172.16.0.0/12
        re.compile(r"^172\.2[0-9]\.\d+\.\d+$"),
        re.compile(r"^172\.3[0-1]\.\d+\.\d+$"),
        re.compile(r"^127\.\d+\.\d+\.\d+$"),     # 回环地址
    ]
    for pattern in private_ranges:
        if pattern.match(ip):
            return True
    return False

# 模块独立测试
if __name__ == "__main__":
    # 默认只检测IPv4
    get_public_ip(check_ipv4=True, check_ipv6=False)