"""
DNS解析测试模块（跨平台）
可移植，支持自定义DNS服务器，统计解析耗时、记录类型，符合运维场景需求
"""
import socket
import time
import platform
from typing import Dict, List, Optional
try:
    import dns.resolver
    import dns.exception
    import dns.rdatatype
except ImportError:
    print("❌ 缺少依赖！请先执行：pip install dnspython")
    raise SystemExit(1)

def dns_resolve_test(
    domain: str = "www.baidu.com",
    dns_servers: List[str] = None,
    record_types: List[str] = None,
    timeout: int = 5
) -> Dict:
    """
    执行DNS解析测试，返回详细统计指标
    :param domain: 目标域名（如 www.baidu.com）
    :param dns_servers: DNS服务器列表（默认：系统DNS）
    :param record_types: 解析记录类型（默认：["A", "AAAA"]）
    :param timeout: 解析超时时间（秒，默认5）
    :return: 包含详细解析结果的字典
    """
    print(f"\n===== DNS解析测试（{domain}） =====")
    
    # 初始化默认值
    if dns_servers is None:
        dns_servers = _get_system_dns_servers()
        if dns_servers is None:
            # ⚠️ 获取系统 DNS 失败时提示
            print("⚠️ 警告：无法获取系统 DNS 服务器，将使用默认 DNS")
            print("   默认 DNS：114.114.114.114, 8.8.8.8")
            dns_servers = ["114.114.114.114", "8.8.8.8"]
        else:
            print(f"✓ 已获取系统 DNS：{', '.join(dns_servers)}")
    
    if record_types is None:
        record_types = ["A", "AAAA"]
    
    # 初始化结果字典（对齐Ping/Tracert的结果格式）
    result = {
        "domain": domain,
        "dns_servers": dns_servers,
        "record_types": record_types,
        "timeout": timeout,
        "resolve_results": {},  # {记录类型: {"ips": [], "elapsed_ms": 0, "status": "成功/失败", "error": ""}}
        "overall_status": "失败",
        "raw_output": "",
        "error": ""
    }

    try:
        # 初始化DNS解析器
        resolver = dns.resolver.Resolver()
        resolver.timeout = timeout
        resolver.lifetime = timeout
        resolver.nameservers = dns_servers

        # 遍历解析各类型记录
        for rtype in record_types:
            start_time = time.time()
            type_result = {
                "ips": [],
                "elapsed_ms": 0.0,
                "status": "失败",
                "error": ""
            }

            try:
                # 执行解析
                answers = resolver.resolve(domain, rtype)
                type_result["elapsed_ms"] = round((time.time() - start_time) * 1000, 2)
                type_result["ips"] = [str(ans) for ans in answers]
                type_result["status"] = "成功"
                
            except dns.resolver.NXDOMAIN:
                type_result["error"] = "域名不存在（NXDOMAIN）"
            except dns.resolver.NoAnswer:
                type_result["error"] = "无该类型解析记录"
            except dns.resolver.Timeout:
                type_result["error"] = f"解析超时（{timeout}秒）"
            except dns.resolver.NoNameservers:
                type_result["error"] = "DNS服务器不可达"
            except Exception as e:
                type_result["error"] = f"解析失败：{str(e)}"

            result["resolve_results"][rtype] = type_result

        # 判定整体状态（只要有一个记录类型解析成功则为成功）
        if any([res["status"] == "成功" for res in result["resolve_results"].values()]):
            result["overall_status"] = "成功"

    except Exception as e:
        result["error"] = f"解析器初始化失败：{str(e)}"

    # 打印格式化结果（对齐Ping/Tracert的输出风格）
    print("📊 DNS解析结果：")
    print(f"  目标域名：{result['domain']}")
    print(f"  DNS服务器：{', '.join(result['dns_servers'])}")
    print(f"  解析类型：{', '.join(result['record_types'])}")
    print(f"  整体状态：{result['overall_status']}")
    
    if result["error"]:
        print(f"  错误信息：{result['error']}")
    else:
        for rtype, res in result["resolve_results"].items():
            print(f"\n  【{rtype}记录】")
            print(f"    状态：{res['status']}")
            if res["elapsed_ms"] > 0:
                print(f"    解析耗时：{res['elapsed_ms']}ms")
            if res["ips"]:
                print(f"    解析结果：{', '.join(res['ips'])}")
            if res["error"]:
                print(f"    错误信息：{res['error']}")

    return result

def _get_system_dns_servers() -> Optional[List[str]]:
    """
    自动获取系统默认 DNS 服务器（跨平台，Windows 11 适配）
    :return: DNS 服务器列表，失败返回 None
    """
    try:
        os_type = platform.system().lower()
        if os_type == "windows":
            import subprocess
            # ✅ Windows 11: 尝试多种编码
            encodings = ["gbk", "utf-8", "cp437"]
            output = None
            
            for encoding in encodings:
                try:
                    output = subprocess.check_output(
                        ["ipconfig", "/all"],
                        encoding=encoding,
                        timeout=5,
                        stderr=subprocess.DEVNULL
                    )
                    break
                except UnicodeDecodeError:
                    continue
            
            if output is None:
                return None
                
            dns_ips = []
            for line in output.split("\n"):
                # ✅ 兼容中英文输出
                if ("DNS 服务器" in line or "DNS Servers" in line) and ":" in line:
                    ip_part = line.split(":")[-1].strip()
                    # ✅ 更宽松的 IP 验证
                    if ip_part and "." in ip_part:
                        # 提取 IPv4 地址
                        import re
                        ipv4 = re.findall(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", ip_part)
                        if ipv4:
                            dns_ips.extend(ipv4)
            
            return dns_ips if dns_ips else None
            
        else:
            # Linux/Mac
            with open("/etc/resolv.conf", "r") as f:
                lines = f.readlines()
            dns_ips = [line.strip().split()[-1] for line in lines if line.startswith("nameserver")]
            return dns_ips if dns_ips else None
            
    except Exception as e:
        # ✅ 使用 stderr 确保输出不被捕获
        import sys
        print(f"⚠️ [调试] 获取系统 DNS 失败：{str(e)}", file=sys.stderr)
        return None

# 模块独立测试
if __name__ == "__main__":
    # 测试1：默认参数解析百度
    dns_resolve_test("www.baidu.com")
    # 测试2：自定义DNS解析谷歌
    # dns_resolve_test("www.google.com", dns_servers=["8.8.8.8", "8.8.4.4"], record_types=["A"])