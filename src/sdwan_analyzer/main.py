import argparse
import msvcrt
import ctypes
import sys
import logging
import traceback
import os
from dataclasses import asdict
from typing import Optional, List

# ================= 标准SDWAN导入区域 =================
# 1. 标准CLI接口 - 统一管理
from sdwan_analyzer.interface.cli_adapter import CLIAdapter, CLIArgs
from sdwan_analyzer.core.contracts import AgentInput, AgentOutput, Context

# 2. 基础工具与配置
from sdwan_analyzer.utils.logger import get_logger
from sdwan_analyzer.config import BUSINESS_TARGETS, DEFAULT_PORT

# 3. 核心网络检测模块
from sdwan_analyzer.core.mtr import run_mtr
from sdwan_analyzer.core.ping import ping_check
from sdwan_analyzer.core.tracert import run_tracert
# 3.5 重构新增模块
from sdwan_analyzer.engine.smart_scheduler import DiagnosticScheduler

# 4. 业务模块
from sdwan_analyzer.models.diagnose import FinalReport, Issue
from sdwan_analyzer.modules.app_probe import detect_mtu, run_app_probe, tcping
from sdwan_analyzer.modules.dns_check import check_dns_working
from sdwan_analyzer.modules.system_diagnose import run_system_diagnose
from sdwan_analyzer.modules.local_net_config import (
    run_local_net_config_check,
    print_local_config_report
)
from sdwan_analyzer.modules.cross_border_test import run_cross_border_test, get_default_gateway
from sdwan_analyzer.modules.report import collect_cross_border_report_data, export_cross_border_html_report

# 5. 可选模块
try:
    from sdwan_analyzer.modules.proxy_check import check_windows_proxy
except ImportError:
    check_windows_proxy = None

# 6. 扩展模块
from sdwan_analyzer.tools.builtin.connectivity_probe import (
    DomainAccessibilityResult,
    TestResult
)
from sdwan_analyzer.tools.builtin.cpe_info import CpeInfoCollector  # CPE信息采集
from sdwan_analyzer.tools.builtin.dns_resolve import dns_resolve_test  # DNS解析结果采集
from sdwan_analyzer.tools.builtin.gateway_check import gateway_connectivity_check 
from sdwan_analyzer.tools.builtin.http_probe import single_http_probe 
from sdwan_analyzer.tools.builtin.loss_jitter_probe import loss_jitter_probe 
from sdwan_analyzer.tools.builtin.mtu_probe import mtu_probe
from sdwan_analyzer.tools.builtin.port_scan import tcp_port_scan
from sdwan_analyzer.tools.builtin.public_ip_check import get_public_ip 
from sdwan_analyzer.tools.builtin.telnet_client import telnet_client
from sdwan_analyzer.tools.builtin.tracert_test import tracert_test
from sdwan_analyzer.tools.builtin.net_waterfall import run_network_waterfall_diagnosis

# 初始化日志 (建议在 main 中初始化，或者这里保持基本配置)
# logging.basicConfig(level=logging.DEBUG) 

# ================= 辅助函数 =================

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def getch():
    """获取单个字符输入"""
    return msvcrt.getch().decode('utf-8')

def press_any_key():
    """按任意键继续"""
    print("按任意键继续...", end=" ")
    sys.stdout.flush()
    getch()
    print()

def safe_input(prompt: str, default: str = "", allow_empty: bool = False) -> str:
    """兼容无stdin环境的输入函数。
    
    Args:
        prompt: 提示文本
        default: 默认值（用于参数项）
        allow_empty: 是否允许空输入（True=使用默认值，False=重新等待输入）
    """
    try:
        while True:
            user_input = input(prompt).strip()
            
            if user_input == "":
                if allow_empty:
                    # 参数项：空值使用默认值
                    return default
                else:
                    # 菜单项：空值重新等待输入
                    print("  请重新输入...")
                    continue
            
            return user_input
            
    except (EOFError, RuntimeError, OSError):
        print("\n[WARN] 当前运行环境不可交互，已使用默认选项。")
        return default

def is_interactive() -> bool:
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False

def print_section(title):
    print(f"\n===== {title} =====")

def print_menu():
    """打印主菜单 - 统一接口   """
    print("========================================")
    print("   瑞斯康达跨境FAQ助手 v1.1 (标准接口)    ")
    print("========================================")
    print("【标准命令模式】    ")
    print("1. 用户环境一键自查     ")
    print("2. 跨境链路SLA测试    ")
    print("3. 网络测试工具    ")
    #print("4. 网络监控 (monitor)")
    #print("5. 系统信息 (system)")
    print("")
    print("0. 退出工具    ")
    print("========================================   ")
    
def print_test_tools_menu():
    """打印测试工具子菜单 - 精简可用版"""
    print("========================================   ")
    print("      网络诊断工具箱 (可用功能)    ")
    print("========================================   ")
    
    print("【A. 核心基础工具】    ")
    print(" 1. Ping 测试   ")
    print(" 2. 路由跟踪 MTR    ")
    print(" 3. 网关可达性检查   ")
    print(" 4. DNS 解析详情    ")
    print(" 5. 公网 IP 查询    ")
    print(" 6. 端口扫描器    ")
    print(" 7. MTU 路径探测    ")
    print(" 8. HTTP 响应头探测    ")
    print(" 9. 丢包与抖动分析    ")
    print(" 10. Telnet 连接    ")
    #print(" 11. 互联网访问全景分析    ") # 新增选项

    print("\n----------------------------------------")
    print(" 0. 返回主菜单    ")
    print("========================================")

def run_test_tools():
    """运行测试工具 - 精简可用版 (与菜单顺序严格对应)    """
    while True:
        print_test_tools_menu()
        choice = safe_input("请输入工具编号(0-11) : ", "0", allow_empty=False)
        
        if choice == "0":
            break
        
        # ==================== A. 核心基础工具 ====================
        elif choice == "1":
            # 1. Ping 测试 (core.ping)
            target = safe_input("请输入目标IP/域名：", allow_empty=True)
            if target:
                try:
                    count = safe_input("Ping次数[默认4]：", "4", allow_empty=True)
                    timeout = safe_input("超时时间[默认5秒]：", "5", allow_empty=True)
                    count = int(count) if count and count.isdigit() else 4
                    timeout = int(timeout) if timeout and timeout.isdigit() else 5
                    
                    ping_result = ping_check(target) # 来自 core.ping
                    print(f"\n[Ping Core] 测试结果:")
                    print(f"  目标: {target}")
                    print(f"  发送: {ping_result.sent}, 接收: {ping_result.received}")
                    print(f"  丢失: {ping_result.loss}%, 平均延迟: {ping_result.avg_rtt}ms")
                except Exception as e:
                    print(f"⚠️ Ping 失败: {e}")

        elif choice == "2":
            # 2. 路由跟踪 MTR (core.mtr)
            target = safe_input("请输入目标IP/域名：", allow_empty=True)
            if target:
                try:
                    max_hops = safe_input("最大跳数[默认30]：", "30", allow_empty=True)
                    max_hops = int(max_hops) if max_hops and max_hops.isdigit() else 30
                    print(f"[MTR Core] 执行路由跟踪到 {target} (最大跳数: {max_hops})")
                    run_mtr(target) # 来自 core.mtr
                except Exception as e:
                    print(f"⚠️ MTR 失败: {e}")

        elif choice == "3":
            # 3. 网关可达性检查 (tools.gateway_connectivity_check)
            print("\n[gateway_connectivity_check Tool] 正在检查网关可达性...")
            try:
                # 直接调用函数
                status = gateway_connectivity_check()
                print(f"  ✅ 检测完成，详见上方输出")
            except Exception as e:
                print(f"⚠️ 网关检查失败: {e}")

        elif choice == "4":
            # 4. DNS 解析详情 (tools.dns_resolve_test)
            domain = safe_input("请输入域名 [默认 google.com]: ", "google.com", allow_empty=True)
            if domain:
                try:
                    # 直接调用函数，它内部已经打印了详细解析结果
                    result = dns_resolve_test(domain=domain)
                    print(f"\n[DnsResolve Tool] 采集完成:")
                    if isinstance(result, dict):
                        print(f"  整体状态: {result.get('overall_status', 'Unknown')}")
                except Exception as e:
                    print(f"⚠️ DNS解析采集失败: {e}")

        elif choice == "5":
            # 5. 公网 IP 查询 (tools.get_public_ip)
            print("\n[PublicIp Tool] 正在查询公网IP...")
            try:
                # 直接调用函数，它内部已经打印了详细信息
                ip_info = get_public_ip() 
                print(f"  ✅ 查询完成，详见上方输出")
                # 如果返回的是字典，可以简单补充
                if isinstance(ip_info, dict):
                    print(f"  主要IP: {ip_info.get('ip', 'N/A')}")
            except Exception as e:
                print(f"⚠️ 公网IP查询失败: {e}")

        elif choice == "6":
            # 6. 端口扫描器 (tools.tcp_port_scan)
            target = safe_input("请输入目标IP/域名：", allow_empty=True)
            if target:
                ports_str = safe_input("请输入端口范围 [默认 80,443,8080]: ", "80,443,8080", allow_empty=True)
                try:
                    ports = [int(p.strip()) for p in ports_str.split(',')]
                    # 直接调用函数，它内部已经打印了详细表格
                    result_dict = tcp_port_scan(target=target, ports=ports)
                    
                    # 这里只需要打印简单的总结，因为函数内部已经打印了详细列表
                    print(f"\n[tcp_port_scan Tool] 扫描总结:")
                    if isinstance(result_dict, dict):
                        open_count = result_dict.get('open_ports_count', 0)
                        print(f"  ✅ 发现 {open_count} 个开放端口")
                    else:
                        print(f"  ✅ 扫描完成")
                except Exception as e:
                    print(f"⚠️ 端口扫描失败: {e}")

        elif choice == "7":
            # 7. MTU 路径探测 (modules.app_probe)
            target = safe_input("请输入目标IP/域名：")
            if target:
                try:
                    mtu = detect_mtu(target) # 来自 modules.app_probe
                    print(f"[MTU Core] 最佳MTU: {mtu}")
                    print(f"  状态: {'正常' if mtu >= 1400 else '偏低/异常'}")
                except Exception as e:
                    print(f"⚠️ MTU探测失败: {e}")

        # ==================== B. 扩展高级工具 ====================
        elif choice == "8":
            # 8. HTTP 响应头探测 (tools.single_http_probe)
            url = safe_input("请输入URL [默认 https://www.baidu.com]: ", "https://www.baidu.com", allow_empty=True)
            if url:
                try:
                    # 直接调用函数
                    res = single_http_probe(url=url, count=1)
                    print(f"\n[single_http_probe Tool] 响应 ({url}):")
                except Exception as e:
                    print(f"⚠️ single_http_probe 失败: {e}")

        # ==================== C. 专项深度诊断 ====================
        elif choice == "9":
            # 9. 丢包与抖动分析 (tools.loss_jitter_probe)
            target = safe_input("请输入目标IP/域名 [默认 google.com]: ", "google.com", allow_empty=True)
            if target:
                try:
                    # 直接调用函数
                    res = loss_jitter_probe(target=target) 
                    
                    print(f"\n[LossJitter Tool] 结果 ({target}):")
                    if isinstance(res, dict):
                        print(f"  丢包率: {res.get('packet_loss', res.get('loss', 0)):.1f}%")
                        print(f"  抖动: {res.get('jitter', 0):.1f}ms")
                        print(f"  平均延迟: {res.get('avg_rtt', res.get('avg_delay', 0)):.1f}ms")
                    else:
                        print(f"  原始结果: {res}")
                except Exception as e:
                    print(f"⚠️ 丢包抖动测试失败: {e}")
        elif choice == "10":
            # 10. Telnet 真实连接 (交互式)
            target = safe_input("请输入目标IP/域名：", allow_empty=True)
            if target:
                port = safe_input("请输入端口 [默认 23]: ", "23", allow_empty=True)
                port = int(port) if port.isdigit() else 23
                
                try:
                    print(f"\n[Telnet Tool] 正在初始化连接到 {target}:{port} ...")
                    print("[提示] 连接成功后将进入交互模式。按 Ctrl+C 退出会话。")
                    
                    # 1. 实例化 telnet_client 类
                    client = telnet_client()
                    
                    # 2. 手动设置目标参数
                    client.ip = target
                    client.port = port
                    
                    # 3. 直接调用同步的 connect 方法
                    # 注意：telnet_client.connect() 是同步方法，内部已处理 asyncio 循环
                    if client.connect():
                        print(f"\n✅ 已连接到 {target}:{port}，进入交互模式...")
                        # 4. 启动交互式会话 (也是同步方法，内部阻塞直到断开)
                        client.telnet_interactive()
                    else:
                        print(f"\n❌ 无法连接到 {target}:{port}")
                    
                except KeyboardInterrupt:
                    print("\n⚠️ 用户中断连接")
                except Exception as e:
                    print(f"⚠️ Telnet 连接异常: {e}")
                    # traceback.print_exc() # 调试时可开启
        elif choice == "11":
            # 11. 互联网访问全景分析
            target_url = safe_input("请输入目标URL [默认 https://www.baidu.com]: ", "https://www.baidu.com", allow_empty=True)
            if target_url:
                try:
                    report_dir = os.path.join(os.getcwd(), "reports", "waterfall")
                    
                    print("\n[提示] 该功能将启动无头浏览器，进行请求捕获、出口IP探测及一致性分析。")
                    print("[提示] 根据页面复杂度，可能耗时 30-60 秒，请耐心等待...\n")
                    
                    result = run_network_waterfall_diagnosis(target_url, output_dir=report_dir)
                    
                    if result.get("status") == "success":
                        print("\n✅ 分析完成！")
                        print(f"📄 可视化 HTML 报告: {result['html_report']}")
                        print(f"📦 Playwright Trace: {result['trace_file']}")
                        
                        # 直接在控制台展示关键发现
                        summary = result.get('consistency_summary', {})
                        if summary:
                            print("\n--- 智能分析摘要 ---")
                            if summary.get('multi_egress'):
                                print(f"⚠️ 多出口负载: 检测到 {len(summary['http_ips'])} 个不同出口IP")
                                for ip_detail in summary.get('ip_details', []):
                                    print(f"   - {ip_detail['ip']} ({ip_detail['region']}): {ip_detail['percentage']}")
                            
                            if summary.get('mismatches'):
                                print(f"⚠️ 路径分离: {len(summary['mismatches'])} 个域名的 DNS 解析出口与 HTTP 实际出口不一致")
                                print("   (建议检查本地代理设置或 DNS 污染情况)")
                            
                            if not summary.get('multi_egress') and not summary.get('mismatches'):
                                print("✅ 链路一致性检查通过，未发现明显异常。")
                        
                        print("\n💡 如何查看？")
                        print(f"   1. 用浏览器打开 HTML 报告查看全景图和建議。")
                        print(f"   2. 命令行运行: playwright show-trace \"{result['trace_file']}\" 查看底层时序。")
                        
                    else:
                        print(f"\n⚠️ 诊断失败: {result.get('message', '未知错误')}")
                        
                except Exception as e:
                    print(f"⚠️ 工具执行异常: {e}")
                    # traceback.print_exc()
        
        else:
            print("输入有误，请重新输入")
        
        press_any_key()

def run_cross_border_detection():
    """跨境链路专项测试 - 包含MTU探测等深度测试功能"""
    print("==================================================")
    print("          跨境链路专项测试")
    print("==================================================")
    
    # 获取目标列表
    from sdwan_analyzer.config import BUSINESS_TARGETS
    if not BUSINESS_TARGETS:
        print("[ERROR] 未配置业务目标")
        return
    
    target_list = [item['target'] for item in BUSINESS_TARGETS]
    
    try:
        # 执行跨境链路测试
        cross_result = run_cross_border_test(target_list)
        
        # 【简化】直接从 cross_result 中提取 MTU 结果，无需再次探测
        print_section("[MTU] MTU路径探测专项测试 (集成于链路测试)")
        mtu_results = []
        if not hasattr(cross_result, 'link_results') or not cross_result.link_results:
            print("  [WARN] 无链路测试结果，无法提取 MTU 数据")
        else:
            for link in cross_result.link_results:
                mtu_val = getattr(link, 'mtu', 0)
                if mtu_val > 0:
                    status = "[OK] 正常" if mtu_val >= 1400 else ("[WARN] 偏低" if mtu_val > 576 else "[ERROR] 极低/受限")
                    print(f"  {link.target:<25} | MTU={mtu_val} {status}")
                    mtu_results.append({"target": link.target, "mtu": mtu_val, "status": status})
                else:
                    # 如果 MTU 为 0，说明目标不可达或探测失败
                    if link.stability_score == 0:
                        print(f"  {link.target:<25} | [SKIP] 目标不可达")
                        mtu_results.append({"target": link.target, "mtu": 0, "status": "目标不可达"})
                    else:
                        print(f"  {link.target:<25} | [ERROR] 探测失败")
                        mtu_results.append({"target": link.target, "mtu": 0, "status": "探测异常"})
        
        # 2. 提取 DNS 对比测试结果
        dns_comp_obj = getattr(cross_result, 'dns_comparison', None)
        dns_comparison_results = []
        
        if dns_comp_obj:
            current_gateway_ip = get_default_gateway()
            
            # 【优化】直接获取清洗后的系统 DNS IP
            # 由于 cross_border_test.py 中的 get_system_primary_dns 已经过滤了 fe80，
            # 这里直接使用 system_dns_server 字段，如果为空则显示一个更友好的默认提示
            system_dns_ip = getattr(dns_comp_obj, 'system_dns_server', '')
            
            # 如果还是没拿到（极端情况），尝试从 resolved_ips 反推或者给个通用提示
            if not system_dns_ip or system_dns_ip == "N/A":
                # 尝试从解析结果中找线索，或者干脆显示“系统默认”
                system_dns_ip = "系统默认配置"

            dns_comparison_results.append({
                "server_local": current_gateway_ip or "默认网关", 
                "ip_local": getattr(dns_comp_obj, 'gateway_resolved_ips', []),
                "status_local": getattr(dns_comp_obj, 'gateway_dns_status', 'unknown'),
                
                "server_system": system_dns_ip, # 直接展示清洗后的 IP 或友好提示
                "ip_system": getattr(dns_comp_obj, 'system_resolved_ips', []), 
                "status_system": getattr(dns_comp_obj, 'system_dns_status', 'unknown'), 

                "server_public": "8.8.8.8",
                "ip_public": getattr(dns_comp_obj, 'local_resolved_ips', []),
                "status_public": getattr(dns_comp_obj, 'public_dns_status', 'unknown'),
                "note": getattr(dns_comp_obj, 'comparison_note', '')
            })
            
        # 3. 提取 Google DNS (8.8.8.8) 连通性状态
        precheck = getattr(cross_result, 'precheck', None)
        google_dns_ok = False
        if precheck:
            google_dns_ok = getattr(precheck, 'gateway_ping_success', False)
        
        # 输出专项报告
        _print_cross_border_summary(cross_result, mtu_results)
        
        print_section("[DEBUG] 检查链路结果数据")
        for link in cross_result.link_results:
            print(f"Target: {link.target}, Jitter: {link.jitter}, Avg_Latency: {link.avg_latency}")

        # 生成HTML报告
        print_section("[报告] 生成跨境链路专项报告")
        try:
            # 【修复点】传入正确提取的 dns_comparison_results
            report = collect_cross_border_report_data(
                cross_result, 
                mtu_results=mtu_results, 
                dns_comparison_results=dns_comparison_results
            )
            
            # 【修复点】确保 report 对象中也有 google_dns_ok 状态
            # 虽然 collect_cross_border_report_data 内部尝试从 cross_result 获取，
            # 但显式设置更稳妥，或者修改 collect 函数以接收此参数
            setattr(report, 'google_dns_reachable', google_dns_ok)
            html_success = export_cross_border_html_report(report, cross_result)
            
            if html_success:
                print("[OK] 跨境链路HTML报告生成成功")
            else:
                print("⚠ 跨境链路HTML报告生成失败")
                
        except Exception as report_error:
            print(f"⚠ HTML报告生成异常: {report_error}")
            traceback.print_exc()
            
    except Exception as e:
        print(f"[ERROR] 跨境链路测试异常: {e}")
        traceback.print_exc()
    
    if is_interactive():
        press_any_key()

def _print_cross_border_summary(cross_result, mtu_results):
    """输出跨境链路专项测试摘要"""
    print_section("[SUMMARY] 跨境链路专项测试报告")
    print("=" * 60)
    
    # 链路质量摘要
    print("〓链路质量评估：")
    for link in cross_result.link_results:
        status_icon = "[OK]" if link.stability_score >= 80 else ("[WARN]" if link.stability_score >= 60 else "[ERROR]")
        print(f"  {link.target:<25} | 评分: {link.stability_score:5.1f} {status_icon} | 延迟: {link.avg_latency:4.0f}ms | 丢包: {link.packet_loss:4.1f}%")
    
    # MTU探测摘要
    print("")
    print("〓MTU路径探测：")
    for mtu_info in mtu_results:
        print(f"  {mtu_info['target']:<25} | MTU: {mtu_info['mtu']:4d} | {mtu_info['status']}")
    
    # 整体评估
    print("")
    print(f"〓整体评估：{cross_result.summary}")
    print(f"〓总体评分：{cross_result.overall_score:.1f}/100")



def _print_simple_summary(results):
    """简化结果摘要输出"""
    print("\n[SUMMARY] 简化检测摘要")
    print("=" * 40)
    reachable_count = sum(1 for r in results if r.basic_reachable)
    print(f"  检测目标：{len(results)} 个")
    print(f"  可达目标：{reachable_count} 个")
    print(f"  深度分析：{sum(1 for r in results if r.deep_check_completed)} 个")


def parse_args_legacy(argv: list[str]) -> argparse.Namespace:
    """旧版参数解析 - 保持向后兼容"""
    parser = argparse.ArgumentParser(prog="sdwan-analyzer")
    sub = parser.add_subparsers(dest="cmd")

    one_click = sub.add_parser("one-click", help="一键检测（非交互）")
    one_click.add_argument("--target", action="append", default=None, help="目标IP/域名，可重复")

    tools = sub.add_parser("tools", help="常用测试工具（非交互）")
    tools_sub = tools.add_subparsers(dest="tool")

    ping_p = tools_sub.add_parser("ping", help="Ping 测试")
    ping_p.add_argument("target")

    mtr_p = tools_sub.add_parser("mtr", help="MTR 测试")
    mtr_p.add_argument("target")

    tcp_p = tools_sub.add_parser("tcp", help="TCP 端口测试")
    tcp_p.add_argument("target")
    tcp_p.add_argument("--port", type=int, default=443)

    dns_p = tools_sub.add_parser("dns", help="DNS 解析测试")

    mtu_p = tools_sub.add_parser("mtu", help="MTU 探测")
    mtu_p.add_argument("target")

    cross_border_p = tools_sub.add_parser("cross-border", help="跨境链路专项测试")

    sub.add_parser("system-info", help="系统信息查看（非交互）")

    return parser.parse_args(argv)

def parse_args_standard(argv: list[str]) -> CLIArgs:
    """标准CLI参数解析 - 统一接口"""
    adapter = CLIAdapter()
    return adapter.parse_args(argv)

def process_standard_command(args: CLIArgs) -> int:
    """处理标准CLI命令 - 统一接口实现"""
    # 根据实际的CLI适配器命令结构进行分发
    if args.command == "oneclick":
        return handle_oneclick_diagnosis(args)
    elif args.command == "test":
        return handle_test_command(args)
    elif args.command == "crossborder":
        return handle_cross_border_test(args)
    elif args.command == "monitor":
        return handle_monitor_command(args)
    
    print(f"未知命令: {args.command}")
    return 2

def handle_oneclick_diagnosis(args: CLIArgs) -> int:
    """处理一键诊断命令"""
    print(f"执行一键诊断，输出格式: {args.output_format}")
    run_diagnosis()
    return 0

def handle_test_command(args: CLIArgs) -> int:
    """处理测试命令"""
    # 测试命令需要通过CLI适配器解析实际的请求
    adapter = CLIAdapter()
    parsed_args = adapter.parse_args()
    
    # 检查是否有有效的命令和目标
    if not parsed_args.target:
        print("请使用标准命令行格式: sdwan-analyzer test <test_type> <target>")
        print("可用测试类型: ping, port, dns, trace")
        return 1
    
    # 使用命令行参数的command字段来识别测试类型
    if parsed_args.command == "test":
        # 在交互式模式下，我们需要通过其他方式确定具体的测试类型
        print("在交互式测试工具菜单中选择具体测试功能")
        return run_test_tools()
    
    # 如果直接通过命令行调用，需要有具体的test_type信息
    # 由于CLIArgs的结构限制，这里建议用户使用完整的命令行格式
    print("请使用: sdwan-analyzer test <类型> <目标>")
    print("例如: sdwan-analyzer test ping google.com")
    print("       sdwan-analyzer test port google.com 443")
    return 1

def handle_monitor_command(args: CLIArgs) -> int:
    """处理监控命令"""
    print(f"启动监控模式，目标: {args.targets}")
    return handle_monitor_implementation(args)

def handle_monitor_implementation(args: CLIArgs) -> int:
    """监控命令实现"""
    # 这是一个基础的监控实现
    print("监控功能开发中...")
    return 0

def run_interactive_mode(args: CLIArgs) -> int:
    """运行交互式菜单模式 - 统一接口"""
    main()
    return 0

def run_standard_diagnosis(args: CLIArgs) -> int:
    """统一接口的一键检测实现"""
    if args.targets:
        # 使用指定的目标进行检测
        return run_custom_diagnosis(args.targets)
    else:
        # 使用默认的业务目标进行检测
        return run_default_diagnosis()

def run_custom_diagnosis(targets: List[str]) -> int:
    """使用自定义目标进行检测"""
    print(f"执行自定义目标检测: {targets}")
    # 实现自定义检测逻辑
    run_diagnosis_with_targets(targets)
    return 0

def run_default_diagnosis() -> int:
    """使用默认业务目标检测"""
    run_diagnosis()
    return 0

def handle_test_tools(args: CLIArgs) -> int:
    """处理测试工具相关命令"""
    if not args.subcommand:
        print("请指定具体的测试工具")
        return 1
    
    if args.subcommand == "ping":
        return run_ping_check(args.target)
    elif args.subcommand == "mtr":
        return run_mtr_check(args.target)
    elif args.subcommand == "tcp":
        return run_tcp_check(args.target, args.port)
    elif args.subcommand == "dns":
        return run_dns_check()
    elif args.subcommand == "mtu":
        return run_mtu_check(args.target)
    elif args.subcommand == "app_probe":
        return run_app_probe_check(args.target)
    
    print(f"未知测试工具: {args.subcommand}")
    return 2

def handle_cross_border_test(args: CLIArgs) -> int:
    """处理跨境链路测试命令"""
    run_cross_border_detection()
    return 0

def handle_system_info(args: CLIArgs) -> int:
    """处理系统信息查看命令"""
    run_system_info_check()
    return 0

def run_ping_check(target: str) -> int:
    """执行Ping检测"""
    if not target:
        print("请指定目标IP/域名")
        return 1
    
    try:
        result = ping_check(target)
        print(f"\nPing 测试结果:")
        print(f"  目标: {target}")
        print(f"  发送: {result.sent}")
        print(f"  接收: {result.received}")
        print(f"  丢失: {result.loss}%")
        print(f"  平均延迟: {result.avg_rtt}ms")
        return 0
    except Exception as e:
        print(f"Ping检测失败: {e}")
        return 1

def run_mtr_check(target: str) -> int:
    """执行MTR检测"""
    if not target:
        print("请指定目标IP/域名")
        return 1
    
    try:
        run_mtr(target)
        return 0
    except Exception as e:
        print(f"MTR检测失败: {e}")
        return 1

def run_tcp_check(target: str, port: int = 443) -> int:
    """执行TCP端口检测"""
    if not target:
        print("请指定目标IP/域名")
        return 1
    
    try:
        result = tcping(target, port)
        print(f"TCP端口 {port} 开放: {result}")
        return 0
    except Exception as e:
        print(f"TCP端口检测失败: {e}")
        return 1

def run_dns_check() -> int:
    """执行DNS检测"""
    try:
        result = check_dns_working()
        print(f"DNS解析正常: {result}")
        return 0
    except Exception as e:
        print(f"DNS检测失败: {e}")
        return 1

def run_mtu_check(target: str) -> int:
    """执行MTU检测"""
    if not target:
        print("请指定目标IP/域名")
        return 1
    
    try:
        mtu = detect_mtu(target)
        print(f"最佳MTU: {mtu}")
        print(f"MTU正常: {mtu >= 1400}")
        return 0
    except Exception as e:
        print(f"MTU检测失败: {e}")
        return 1

def run_app_probe_check(target: str) -> int:
    """执行应用探测"""
    if not target:
        print("请指定目标IP/域名")
        return 1
    
    try:
        result = run_app_probe(target)
        print(f"应用探测结果:")
        print(f"  TCP端口开放: {result.tcp_open}")
        print(f"  HTTP可用性: {result.http_available}")
        return 0
    except Exception as e:
        print(f"应用探测失败: {e}")
        return 1

def cli(argv: list[str] | None = None) -> int:
    """统一的命令行入口点 - 主入口函数"""
    if argv is None:
        argv = sys.argv[1:]

    # 如果没有任何参数，进入交互模式
    if len(argv) == 0:
        if is_interactive():
            main()  # 启动交互式主菜单
            return 0
        else:
            # 非交互环境显示帮助
            print("使用 'sdwan-analyzer -h' 查看可用命令")
            return 1

    # 优先使用标准CLI适配器
    try:
        args = parse_args_standard(argv)
        return process_standard_command(args)
    except Exception as e:
        # 如果标准适配器失败，回退到旧版解析（向后兼容）
        print(f"标准CLI适配器异常，回退到旧版解析: {e}")
        return cli_legacy(argv)

def cli_legacy(argv: list[str]) -> int:
    """旧版CLI实现 - 向后兼容"""
    args = parse_args_legacy(argv)

    if args.cmd is None:
        if is_interactive():
            main()
            return 0
        print("非交互模式下暂不支持完整一键检测，请使用子命令。")
        return 1

    if args.cmd == "one-click":
        run_diagnosis()
        return 0

    if args.cmd == "system-info":
        print("System info command placeholder.")
        return 0

    if args.cmd == "tools":
        if args.tool == "ping":
            ping_check(args.target)
            return 0
        if args.tool == "mtr":
            run_mtr(args.target)
            return 0
        if args.tool == "tcp":
            tcping(args.target, args.port)
            return 0
        if args.tool == "dns":
            check_dns_working()
            return 0
        if args.tool == "mtu":
            detect_mtu(args.target)
            return 0
        if args.tool == "cross-border":
            from sdwan_analyzer.config import BUSINESS_TARGETS
            target_list = [item['target'] for item in BUSINESS_TARGETS]
            run_cross_border_detection()
            return 0

    return 2

def run_diagnosis_with_targets(targets: List[str]):
    """支持自定义目标的检测实现"""
    # 临时修改业务目标以使用自定义目标
    from sdwan_analyzer.config import BUSINESS_TARGETS
    
    # 保存原始配置
    original_targets = BUSINESS_TARGETS.copy()
    
    try:
        # 设置自定义目标
        custom_targets = [{"target": target, "description": "自定义目标"} for target in targets]
        
        # 这里需要修改BUSINESS_TARGETS的引用，实际实现需要根据具体情况调整
        print(f"使用自定义目标执行检测: {targets}")
        run_diagnosis()  # 目前的实现会使用全局BUSINESS_TARGETS
        
    finally:
        # 恢复原始配置（在实际实现中需要对BUSINESS_TARGETS进行适当的修改）
        pass

def run_system_info_check():
    """系统信息检测实现"""
    print("系统信息查看功能开发中...")
    # 可以调用现有的系统信息收集功能

def run_diagnosis():
    """客户端一键检测 - 完整功能并按network_result.txt标准化格式输出"""
    
    try:
        # 导入所有必要的模块
        from sdwan_analyzer.modules.system_collector import collect_system_environment
        from sdwan_analyzer.config import BUSINESS_TARGETS
        from sdwan_analyzer.core.ping import ping_check
        from sdwan_analyzer.core.tracert import run_tracert
        from sdwan_analyzer.modules.app_probe import run_app_probe
        from sdwan_analyzer.modules.cross_border_test import run_cross_border_test
        import subprocess
        import time
        
        # 记录开始时间
        start_time = time.time()
        
        # 收集系统环境信息
        print("正在收集系统环境信息...")
        env_res = collect_system_environment()
        
        # =============== 第一部分：系统环境基础检测 ===============
        
        print("【1. 系统环境基础检测】")
        print("*********************************************************")
        
        enabled_nics = [nic for nic in env_res.interfaces if nic.status == "Connected" and nic.ip_addresses]
        disabled_nics = [nic for nic in env_res.interfaces if nic not in enabled_nics]
        
        print(f"启用网卡数量：{len(enabled_nics)}")
        print(f"未启用网卡数量：{len(disabled_nics)}")
        print("*********************************************************")
        print("")
        
        if enabled_nics:
            print("启用网卡：")
            for nic in enabled_nics:
                # 显示详细的网卡信息：名称、IP、网关、DNS、MAC
                adapter_type = "无线局域网适配器" if "wireless" in nic.description.lower() else "以太网适配器"
                print(f"  {adapter_type} {nic.name}:")
                # IP地址
                if nic.ip_addresses:
                    print(f"    IP地址: {', '.join(nic.ip_addresses)}")
                
                # 【新增】子网掩码
                if nic.subnet_masks:
                    # 通常IP和掩码是一一对应的，这里简单展示所有掩码，或者取第一个
                    # 如果希望更精确对应，可以 zip(nic.ip_addresses, nic.subnet_masks)
                    print(f"    子网掩码: {', '.join(nic.subnet_masks)}")
                else:
                    print(f"    子网掩码: 未知")

                if nic.gateways:
                    print(f"    网关: {', '.join(nic.gateways)}")
                if nic.dns_servers:
                    print(f"    DNS: {', '.join(nic.dns_servers)}")
                if nic.mac_address:
                    print(f"    MAC: {nic.mac_address}")
        else:
            print("启用网卡：无")
            
        print("")
        
        if disabled_nics:
            print("未启用网卡：")
            for nic in disabled_nics:
                adapter_type = "无线局域网适配器" if "wireless" in nic.description.lower() else "以太网适配器"
                status_info = f" ({nic.status})" if nic.status != "Connected" else ""
                print(f"  - {adapter_type} {nic.name}{status_info}")
        else:
            print("未启用网卡：无")
        
        print("")
        
        # =============== 第二部分：网络安全与配置检测 ===============
        
        # 多网关检测告警
        if env_res.has_multiple_gateways:
            all_gateways = []
            for nic in env_res.interfaces:
                all_gateways.extend(nic.gateways)
            unique_gws = list(set(all_gateways))
            print("【多网关告警】")
            print("*********************************************************")
            print(f"检测到 {len(unique_gws)} 个活跃网关: {', '.join(unique_gws)}")
            print("⚠️ 多个网关可能导致路由冲突")
            print("*********************************************************")
            print("")
        
        # 防火墙状态
        print("【防火墙状态】")
        print("*********************************************************")
        firewall_status = "开启" if env_res.firewall_enabled else "关闭"
        print(f"Windows防火墙: {firewall_status}")
        print("*********************************************************")
        print("")
        
        # 代理状态
        print("【代理状态】")
        print("*********************************************************")
        proxy_status = "开启" if env_res.proxy_enabled else "关闭"
        if env_res.proxy_enabled and env_res.proxy_server:
            print(f"系统代理: {proxy_status} ({env_res.proxy_server})")
        else:
            print(f"系统代理: {proxy_status}")
        print("*********************************************************")
        print("")
        
        # 2. DNS服务器地址
        print("【2. DNS服务器地址】")
        print("*********************************************************")
        dns_gateway_warning = []
        if env_res.primary_interface and env_res.primary_interface.dns_servers:
            dns_servers = env_res.primary_interface.dns_servers
            for dns in dns_servers:
                print(f"DNS服务器：{dns}")
                
                # 检查DNS服务器与网关地址差异
                if env_res.primary_interface.gateways:
                    gateways = env_res.primary_interface.gateways
                    # 如果DNS服务器地址不是网关地址，收集告警信息
                    for gw in gateways:
                        # 检查是否是同一子网的IP（检查前三个八位组是否匹配）
                        gw_prefix = '.'.join(gw.split('.')[:3])
                        dns_prefix = '.'.join(dns.split('.')[:3])
                        if gw_prefix != dns_prefix:
                            dns_gateway_warning.append(f"DNS服务器{dns}与网关{gw}不在相同网段")
                            
        else:
            print("DNS服务器：未配置")
        print("*********************************************************")
        print("")
        
        # 3. 缺省路由
        print("【3. 缺省路由】")
        print("*********************************************************")
        
        # 检查活动的默认路由，过滤掉接口名称和标识，只显示核心路由信息
        unique_default_routes = set()
        try:
            route_out = subprocess.check_output(["route", "print", "0.0.0.0"], text=True, encoding="gbk", errors="ignore")
            lines = route_out.split('\n')
            
            for line in lines:
                if '0.0.0.0' in line and len(line.split()) >= 5:
                    parts = line.split()
                    # 只提取网络目标、网络掩码、网关、接口IP、跃点数
                    if parts[0] == '0.0.0.0' and parts[1] == '0.0.0.0':
                        core_info = f"{parts[0]}  {parts[1]}  {parts[2]}  {parts[3]}  {parts[4]}"
                        unique_default_routes.add(core_info)
        except Exception as e:
            print(f"路由查询失败: {e}")
            
        # 转换为列表并排序
        default_routes = sorted(list(unique_default_routes))
        setattr(env_res, 'default_routes', default_routes)
        
        print(f"缺省路由数量：{len(default_routes)}")
        print("*********************************************************")
        
        if default_routes:
            for route in default_routes:
                print(f"  {route}")
        else:
            print("  无缺省路由")
        
        print("")
        
        # =============== 第二部分：基本网络连通性检测 ===============
        
        # =============== 第三部分：网络连通性检测 ===============
        
        # 4. Ping 网关 (优先检测内网网关)
        if env_res.primary_interface and env_res.primary_interface.gateways:
            primary_gateway = env_res.primary_interface.gateways[0]
            print("【4. Ping 网关检测】")
            print("*********************************************************")
            print("正在测试到网关的连通性...")
            gw_ping_result = ping_check(primary_gateway)
            if gw_ping_result.is_success:
                print(f"数据包: 已发送 = 4，已接收 = {gw_ping_result.received}，丢失 = {gw_ping_result.loss} ({gw_ping_result.loss}% 丢失)，")
                print(f"最短 = {gw_ping_result.min_rtt}ms，最长 = {gw_ping_result.max_rtt}ms，平均 = {gw_ping_result.avg_rtt}ms")
            print("*********************************************************")
            if gw_ping_result.is_success:
                print(f"ping {primary_gateway} 结果：通")
            else:
                print(f"ping {primary_gateway} 结果：不通")
            print("*********************************************************")
            print("")
        

        

        
        # =============== 第四部分：业务连通性检测 ===============
        
        print("【5. 业务连通性检测】")
        print("*********************************************************")
        print("正在执行业务连通性检测...")
        print("*********************************************************")
        print("")
        
        # 执行业务连通性检测
        business_results = []
        if BUSINESS_TARGETS:
            for target_config in BUSINESS_TARGETS:
                target = target_config.get("target", "")
                if target:
                    print(f"  {target}:")
                    
                    # 🚀 优化：先执行Ping检测，如果不通则不进行后续测试
                    # 使用智能超时配置，区分国内和跨境目标
                    is_crossborder_target = any(domain in target.lower() for domain in ['youtube.com', 'tiktok.com', 'google.com'])
                    business_ping = ping_check(target, is_crossborder=is_crossborder_target)
                    
                    # 应用层检测：如果Ping不通，直接跳过TCP和HTTP测试
                    app_result = None
                    app_status = "未检测"
                    
                    if business_ping.is_success:
                        # Ping可达才进行应用层检测
                        try:
                            app_result = run_app_probe(target)
                            app_status = "正常" if app_result.tcp_open and app_result.http_available else "异常"
                        except Exception as e:
                            app_result = None
                            app_status = f"检测失败: {str(e)}"
                    else:
                        # Ping不通，直接标记应用状态为不可达
                        app_status = "Ping不可达，跳过详细检测"
                    
                    # 记录结果
                    if business_ping.is_success:
                        ping_status = f"{business_ping.avg_rtt}ms, 丢包{business_ping.loss}%"
                    else:
                        ping_status = "不通"
                        
                    business_results.append({
                        "target": target,
                        "ping_status": ping_status,
                        "ping_reachable": business_ping.is_success,
                        "app_status": app_status,
                        "app_res": app_result,
                        "description": target_config.get("description", "")
                    })

                    print("")
        else:
            print("  未配置业务目标")
        
        print("")
        
        # =============== 第四部分：检测总结 ===============
        
        print("【6. 检测总结】")
        print("*********************************************************")
        
        # 【修复点】优化评分逻辑：将基础环境检测与业务连通性检测合并计算
        
        # 1. 基础环境评分 (权重 40%)
        base_total = 3 # 网关, DNS, 路由
        base_passed = 0
        if env_res.primary_interface and env_res.primary_interface.gateways and 'gw_ping_result' in locals() and gw_ping_result.is_success:
            base_passed += 1
        if env_res.primary_interface and env_res.primary_interface.dns_servers:
            base_passed += 1
        if len(default_routes) > 0:
            base_passed += 1
        
        base_score = (base_passed / base_total * 100) if base_total > 0 else 0
        
        # 2. 业务连通性评分 (权重 60%)
        biz_total = len(business_results)
        biz_passed = sum(1 for res in business_results if res.get('ping_reachable', False))
        biz_score = (biz_passed / biz_total * 100) if biz_total > 0 else 100 # 如果没有业务目标，默认为满分
        
        # 3. 综合加权评分
        final_success_rate = (base_score * 0.4) + (biz_score * 0.6)
        
        print(f"基础环境得分: {base_score:.1f}/100")
        print(f"业务连通得分: {biz_score:.1f}/100")
        print(f"综合健康评分: {final_success_rate:.1f}/100")
        
        # 4. 生成综合结论
        has_proxy = env_res.proxy_enabled
        has_multiple_gw = env_res.has_multiple_gateways
        has_firewall = env_res.firewall_enabled
        
        status_notes = []
        if has_proxy:
            status_notes.append("系统代理已开启")
        if has_multiple_gw:
            status_notes.append("存在多网关路由")
        if has_firewall:
            status_notes.append("防火墙已开启")
        
        # 添加DNS网关差异告警
        if dns_gateway_warning:
            status_notes.extend(dns_gateway_warning)
            
        # 添加业务不通的具体告警
        failed_targets = [res['target'] for res in business_results if not res.get('ping_reachable', False)]
        if failed_targets:
            status_notes.append(f"{len(failed_targets)}个业务目标不可达({','.join(failed_targets)})")

        # 根据综合评分判定结论
        if final_success_rate >= 90:
            conclusion = "网络状态良好"
        elif final_success_rate >= 70:
            conclusion = "网络基本正常"
        else:
            conclusion = "网络存在较多问题"
        
        if status_notes:
            conclusion += f"，注意: {'，'.join(status_notes)}"
            
        print(f"检测结论：{conclusion}")
        
        # 计算总耗时
        end_time = time.time()
        duration = end_time - start_time
        print(f"检测耗时：{duration:.1f}秒")
        
        print("*********************************************************")
        
        # =============== 第六部分：生成和保存详细报告 ===============
        
        
        print("【7. 报告生成】")
        print("*********************************************************")
        print("正在生成详细报告...")
        
        try:
            # 引入HTML报告生成模块
            from sdwan_analyzer.modules.report import collect_report_data, export_html_report
            
            # 生成HTML报告数据
            print("收集报告数据...")
            
            # 【修复点】将之前计算的 conclusion 和 status_notes 传入
            report = collect_report_data(
                env_res, 
                business_results, 
                status_notes=status_notes, 
                detailed_conclusion=conclusion
            )
            
            # 导出HTML报告
            print("生成HTML格式报告...")
            html_success = export_html_report(report)
                
        except Exception as report_error:
            print(f"报告生成失败: {report_error}")
            import traceback
            traceback.print_exc()
            print("基础检测完成")
            
        print("*********************************************************")
        
        return True
        
    except Exception as e:
        print(f"诊断执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    # 1. 权限检查
    if not is_admin():
        print("警告：部分网络诊断功能需要管理员权限才能正常执行。")
        # 可选：自动提权
        # ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        # sys.exit()

    # 2. 初始化日志 - 【修改点】日志文件保存到当前目录
    #log_dir = os.getcwd()  # 或者使用 config.REPORT_DIR
    #log_file = os.path.join(log_dir, "sdwan_analyzer.log")
    
    #logging.basicConfig(
    #    level=logging.INFO, 
    #    format='%(asctime)s - %(levelname)s - %(message)s',
    #    handlers=[
    #        logging.FileHandler(log_file, encoding='utf-8'), # 写入文件
    #        logging.StreamHandler() # 同时输出到控制台
    #    ]
    #)
    
    #logging.info(f"日志文件已创建：{log_file}")
    
    print("瑞斯康达跨境FAQ助手 启动...")
    
    # 3. 主循环
    while True:
        print_menu()
        choice = safe_input("请输入功能编号（0-3）：", "0", allow_empty=False)
        
        if choice == "0":
            print("退出工具，谢谢使用 瑞斯康达跨境FAQ助手！")
            break
        elif choice == "1":
            # 一键诊断功能 - 统一接口
            print("\n==================================================")
            print("          终端一键诊断")
            print("==================================================")
            run_diagnosis()
        elif choice == "2":
            # 跨境链路测试 - 统一接口
            print("\n==================================================")
            print("          跨境链路分析")
            print("==================================================")
            run_cross_border_detection()
        elif choice == "3":
            # 网络测试工具 - 统一接口
            run_test_tools()
        else:
            print("输入有误，请重新输入")
"""
        elif choice == "4":
            # 网络监控功能 - 统一接口
            print("\n==================================================")
            print("          网络监控 (monitor 命令)")
            print("==================================================")
            print("监控功能开发中...")
            press_any_key()
        elif choice == "5":
            # 系统信息查看 - 统一接口
            print("\n==================================================")
            print("          系统信息 (system 命令)")
            print("==================================================")
            print("系统信息查看功能开发中...")
            press_any_key()
"""

if __name__ == "__main__":
    raise SystemExit(cli())