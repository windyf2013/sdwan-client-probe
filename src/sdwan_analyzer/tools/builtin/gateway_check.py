"""
网关连通性检测模块（跨平台）
修复：socket.time → time.time、编码兼容、None值处理
"""
import subprocess
import platform
import re
import socket
import time  # 新增：导入time模块
from typing import Dict, Optional, List

def gateway_connectivity_check(
    gateway_ip: str = None,
    ping_count: int = 4,
    ping_timeout: int = 2,
    check_ports: List[int] = None,
    port_timeout: float = 1.0
) -> Dict:
    """
    执行网关连通性检测，包含Ping探测+端口连通性检测
    修复：socket.time → time.time、编码兼容、None值处理
    """
    # 初始化默认值
    if gateway_ip is None:
        gateway_ip = _get_system_gateway() or "192.168.33.1"
    if check_ports is None:
        check_ports = [80, 443, 22]
    
    print(f"\n===== 网关连通性检测（{gateway_ip}） =====")
    
    # 初始化结果字典
    result = {
        "gateway_ip": gateway_ip,
        "ping_count": ping_count,
        "ping_timeout": ping_timeout,
        "check_ports": check_ports,
        "port_timeout": port_timeout,
        "ping_result": {
            "packet_sent": 0,
            "packet_received": 0,
            "packet_loss_rate": 0.0,
            "avg_delay_ms": 0.0,
            "status": "失败",
            "error": ""
        },
        "port_results": {},
        "overall_status": "失败",
        "error": ""
    }

    try:
        # 第一步：执行Ping检测
        result["ping_result"] = _ping_gateway(gateway_ip, ping_count, ping_timeout)
        
        # 第二步：执行端口连通性检测
        for port in check_ports:
            start_time = time.time()  # 修复1：socket.time → time.time
            port_status = "超时"
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(port_timeout)
                conn_result = sock.connect_ex((gateway_ip, port))
                elapsed_ms = round((time.time() - start_time) * 1000, 2)  # 修复2：socket.time → time.time
                
                if conn_result == 0:
                    port_status = "开放"
                else:
                    port_status = "关闭"
                
                sock.close()
            except Exception as e:
                port_status = "异常"
                elapsed_ms = 0.0
            
            result["port_results"][port] = {
                "status": port_status,
                "delay_ms": elapsed_ms
            }

        # 第三步：判定整体状态
        ping_success = result["ping_result"]["status"] in ["优秀", "良好", "一般"]
        port_success = any([p["status"] == "开放" for p in result["port_results"].values()])
        if ping_success or port_success:
            result["overall_status"] = "成功"

    except Exception as e:
        result["error"] = f"检测过程异常：{str(e)}"

    # 打印格式化结果
    print("📊 网关连通性检测结果：")
    print(f"  网关IP：{result['gateway_ip']}")
    print(f"  整体状态：{result['overall_status']}")
    
    print(f"\n  【Ping检测】")
    if result["ping_result"]["error"]:
        print(f"    状态：{result['ping_result']['status']}")
        print(f"    错误：{result['ping_result']['error']}")
    else:
        print(f"    发送包数：{result['ping_result']['packet_sent']} | 接收包数：{result['ping_result']['packet_received']}")
        print(f"    丢包率：{result['ping_result']['packet_loss_rate'] * 100:.1f}%")
        print(f"    平均延迟：{result['ping_result']['avg_delay_ms']:.1f}ms")
        print(f"    连通状态：{result['ping_result']['status']}")
    
    print(f"\n  【端口检测】")
    if not result["port_results"]:
        print(f"    未检测任何端口")
    else:
        for port, res in result["port_results"].items():
            delay_str = f"{res['delay_ms']}ms" if res['delay_ms'] > 0 else "-"
            print(f"    端口 {port:4d}：{res['status']:4s} | 响应时间：{delay_str}")
    
    if result["error"]:
        print(f"\n  ❌ 异常信息：{result['error']}")

    return result

def _get_system_gateway() -> Optional[str]:
    """自动获取系统默认网关（跨平台）"""
    try:
        os_type = platform.system().lower()
        if os_type == "windows":
            # 修复3：Windows编码兼容（gbk）+ None值处理
            output = subprocess.check_output(
                ["ipconfig", "/all"],
                encoding="gbk",  # 修复编码错误
                errors="ignore",  # 忽略无法解码的字符
                timeout=5
            )
            gateway_pattern = re.compile(r"默认网关[^\:]*:\s*(\d+\.\d+\.\d+\.\d+)")
            matches = gateway_pattern.findall(output)
            if matches:
                return matches[0].strip()
        else:
            output = subprocess.check_output(
                ["ip", "route"],
                encoding="utf-8",
                errors="ignore",
                timeout=5
            )
            gateway_pattern = re.compile(r"default via (\d+\.\d+\.\d+\.\d+)")
            matches = gateway_pattern.findall(output)
            if matches:
                return matches[0].strip()
    except:
        pass
    return None

def _ping_gateway(target: str, count: int = 4, timeout: int = 2) -> Dict:
    """执行网关Ping检测（修复None值处理+编码兼容）"""
    ping_result = {
        "packet_sent": count,
        "packet_received": 0,
        "packet_loss_rate": 1.0,
        "avg_delay_ms": 0.0,
        "status": "失败",
        "error": ""
    }

    try:
        os_type = platform.system().lower()
        if os_type == "windows":
            cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), target]
        else:
            cmd = ["ping", "-c", str(count), "-W", str(timeout), target]

        # 修复4：编码兼容 + None值处理
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="gbk" if os_type == "windows" else "utf-8",  # Windows用gbk编码
            errors="ignore",  # 忽略编码错误
            timeout=10
        )
        output = proc.stdout.strip() if proc.stdout else ""  # 修复None.strip()错误

        if proc.returncode != 0:
            if "请求超时" in output or "100% packet loss" in output:
                ping_result["error"] = "网关无响应（100%丢包）"
            else:
                ping_result["error"] = "Ping命令执行失败"
            return ping_result

        # 修复5：None值处理（匹配不到时不报错）
        if os_type == "windows":
            loss_match = re.search(r"(\d+)% 丢失", output)
            delay_match = re.search(r"平均 = (\d+)ms", output)
        else:
            loss_match = re.search(r"(\d+)% packet loss", output)
            delay_match = re.search(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/[\d.]+/[\d.]+ ms", output)

        # 提取丢包率（None值判断）
        if loss_match:
            loss_rate = int(loss_match.group(1)) / 100.0
            ping_result["packet_loss_rate"] = loss_rate
            ping_result["packet_received"] = int(count * (1 - loss_rate))  # 转为整数
        else:
            ping_result["error"] = "无法解析丢包率"
            return ping_result

        # 提取平均延迟（None值判断）
        if delay_match:
            ping_result["avg_delay_ms"] = float(delay_match.group(1))
        else:
            ping_result["avg_delay_ms"] = 0.0

        # 判定Ping状态
        if ping_result["packet_loss_rate"] == 0.0:
            ping_result["status"] = "优秀"
        elif ping_result["packet_loss_rate"] < 0.2:
            ping_result["status"] = "良好"
        elif ping_result["packet_loss_rate"] < 0.5:
            ping_result["status"] = "一般"
        else:
            ping_result["status"] = "较差"

    except subprocess.TimeoutExpired:
        ping_result["error"] = "Ping命令执行超时"
    except Exception as e:
        ping_result["error"] = f"Ping解析失败：{str(e)}"

    return ping_result

# 模块独立测试
if __name__ == "__main__":
    gateway_connectivity_check()