"""
TCP端口探测模块（跨平台）
可移植，支持单端口/多端口批量探测，返回端口开放状态和探测耗时
"""
import socket
import time
from typing import Dict, List, Optional

def tcp_port_scan(target: str, ports: List[int], timeout: float = 1.0) -> Dict:
    """
    批量探测目标IP的TCP端口开放状态
    :param target: 目标IP/域名（如 192.168.1.1、www.baidu.com）
    :param ports: 要探测的端口列表（如 [22,23,80,443,161]）
    :param timeout: 端口连接超时时间（秒，默认1秒）
    :return: 包含所有端口探测结果的字典
    """
    print(f"\n===== TCP端口探测（{target}） =====")
    
    # 初始化结果字典
    result = {
        "target": target,
        "ports": ports,
        "timeout": timeout,
        "scan_results": [],  # 每个端口的结果：[{"port": 22, "status": "开放/关闭", "delay_ms": 12.3}]
        "open_ports_count": 0,
        "closed_ports_count": 0,
        "error": ""
    }

    try:
        # 先解析域名（如果输入的是域名）
        try:
            target_ip = socket.gethostbyname(target)
            print(f"🔍 解析目标地址：{target} → {target_ip}")
        except socket.gaierror as e:
            result["error"] = f"域名解析失败：{str(e)}"
            print(f"❌ {result['error']}")
            return result

        # 逐个探测端口
        for port in ports:
            # 端口合法性校验
            if not isinstance(port, int) or port < 1 or port > 65535:
                result["scan_results"].append({
                    "port": port,
                    "status": "无效",
                    "delay_ms": 0.0,
                    "error": "端口号必须在1-65535之间"
                })
                continue

            start_time = time.time()
            port_result = {
                "port": port,
                "status": "关闭",
                "delay_ms": 0.0,
                "error": ""
            }

            # 创建TCP socket并尝试连接
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            try:
                # 尝试连接端口
                conn_result = sock.connect_ex((target_ip, port))
                delay_ms = (time.time() - start_time) * 1000  # 转换为毫秒
                port_result["delay_ms"] = round(delay_ms, 2)

                # 判断端口状态（0表示连接成功，端口开放）
                if conn_result == 0:
                    port_result["status"] = "开放"
                    result["open_ports_count"] += 1
                else:
                    port_result["status"] = "关闭"
                    result["closed_ports_count"] += 1

            except socket.timeout:
                port_result["status"] = "超时"
                port_result["error"] = "连接超时"
            except socket.error as e:
                port_result["status"] = "错误"
                port_result["error"] = str(e)
            finally:
                sock.close()  # 确保关闭socket

            result["scan_results"].append(port_result)

        # 打印格式化结果
        print("📋 端口探测结果：")
        print(f"{'端口':<6} {'状态':<8} {'耗时(ms)':<10} {'备注'}")
        print("-" * 30)
        for res in result["scan_results"]:
            status_str = res["status"]
            delay_str = f"{res['delay_ms']:.2f}" if res["delay_ms"] > 0 else "-"
            error_str = res["error"] if res["error"] else "-"
            print(f"{res['port']:<6} {status_str:<8} {delay_str:<10} {error_str}")
        
        print(f"\n📊 统计：开放端口 {result['open_ports_count']} 个 | 关闭/超时端口 {result['closed_ports_count']} 个")

    except Exception as e:
        result["error"] = f"端口探测异常：{type(e).__name__} - {str(e)}"
        print(f"❌ {result['error']}")

    return result

# 快捷函数：探测常用端口
def scan_common_ports(target: str, timeout: float = 1.0) -> Dict:
    """
    探测网络设备常用端口：22(SSH)、23(Telnet)、80(HTTP)、443(HTTPS)、161(SNMP)、8080(WEB)
    :param target: 目标IP/域名
    :param timeout: 超时时间
    :return: 探测结果
    """
    common_ports = [22, 23, 80, 443, 161, 8080]
    return tcp_port_scan(target, common_ports, timeout)

# 模块独立测试
if __name__ == "__main__":
    # 测试1：探测指定端口
    tcp_port_scan("192.168.1.1", [22, 23, 80, 443])
    # 测试2：探测常用端口
    # scan_common_ports("www.baidu.com")