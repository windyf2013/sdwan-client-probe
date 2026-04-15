import requests

def get_ip_info(ip: str) -> dict:
    """
    获取 IP 信息：国家、运营商、ASN
    不需要 pyasn、不需要本地库、Windows 直接跑
    """
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}", timeout=3)
        data = resp.json()

        country = data.get("countryCode", "Unknown")
        isp = data.get("isp", "Unknown")
        org = data.get("org", "Unknown")

        return {
            "country": country,
            "isp": isp,
            "org": org,
            "carrier": _parse_carrier(isp, org)  # 自动识别电信/联通/移动
        }
    except:
        return {
            "country": "Unknown",
            "isp": "Unknown",
            "org": "Unknown",
            "carrier": "Unknown"
        }

def _parse_carrier(isp: str, org: str) -> str:
    """自动识别运营商"""
    isp = isp.lower() + " " + org.lower()
    if "china telecom" in isp:
        return "中国电信"
    elif "china unicom" in isp:
        return "中国联通"
    elif "china mobile" in isp:
        return "中国移动"
    else:
        return "境外运营商"

def get_ip_country(ip: str) -> str:
    return get_ip_info(ip)["country"]

def get_ip_carrier(ip: str) -> str:
    """给外部调用的运营商获取方法"""
    return get_ip_info(ip)["carrier"]