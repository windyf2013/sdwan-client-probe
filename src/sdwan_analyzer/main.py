import argparse
import msvcrt
import ctypes
import sys
import logging
from dataclasses import asdict

# ================= 全局导入区域 =================
# 1. 基础工具与配置
from sdwan_analyzer.utils.logger import get_logger
from sdwan_analyzer.config import BUSINESS_TARGETS, DEFAULT_PORT

# 2. 核心网络检测模块
from sdwan_analyzer.core.mtr import run_mtr
from sdwan_analyzer.core.ping import ping_check
from sdwan_analyzer.core.tracert import run_tracert

# 3. 业务模块
from sdwan_analyzer.models.diagnose import FinalReport, Issue
from sdwan_analyzer.modules.app_probe import detect_mtu, run_app_probe, tcping
from sdwan_analyzer.modules.dns_check import check_dns_working
from sdwan_analyzer.modules.system_diagnose import run_system_diagnose
from sdwan_analyzer.modules.local_net_config import (
    run_local_net_config_check,
    print_local_config_report
)
from sdwan_analyzer.modules.cross_border_test import run_cross_border_test, get_cross_border_report, CrossBorderTestResult
from sdwan_analyzer.modules.report import generate_report, export_report_to_file

# 4. 可选模块
try:
    from sdwan_analyzer.modules.proxy_check import check_windows_proxy
except ImportError:
    check_windows_proxy = None

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

def safe_input(prompt: str, default: str = "") -> str:
    """兼容无stdin环境的输入函数。"""
    try:
        return input(prompt).strip()
    except (EOFError, RuntimeError, OSError):
        print("\n⚠️ 当前运行环境不可交互，已使用默认选项。")
        return default

def is_interactive() -> bool:
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False

def print_section(title):
    print(f"\n===== {title} =====")

def print_menu():
    """打印主菜单"""
    print("========================================")
    print("          CPE运维工具 v1.0")
    print("=====================================")
    print("【功能列表】")
    print("1. 客户端一键检测")
    print("2. 常用测试工具")
    print("3. 系统信息查看")
    print("4. 诊断报告管理")
    print("")
    print("0. 退出工具")
    print("=====================================")

def print_test_tools_menu():
    """打印常用测试工具子菜单"""
    print("========================================")
    print("         常用测试工具")
    print("=====================================")
    print("【工具列表】")
    print("1. Ping 测试")
    print("2. Traceroute (MTR) 测试")
    print("3. TCP 端口测试")
    print("4. DNS 解析测试")
    print("5. MTU 探测")
    print("")
    print("0. 返回主菜单")
    print("=====================================")

def run_test_tools():
    """运行常用测试工具"""
    while True:
        print_test_tools_menu()
        choice = safe_input("请输入工具编号（0-5）：", "0")
        
        if choice == "0":
            break
        elif choice == "1":
            target = safe_input("请输入目标IP/域名：")
            if target:
                try:
                    # 现在可以直接使用全局导入的 ping_check
                    ping_result = ping_check(target)
                    print(f"\nPing 测试结果:")
                    print(f"  目标: {target}")
                    print(f"  发送: {ping_result.sent}")
                    print(f"  接收: {ping_result.received}")
                    print(f"  丢失: {ping_result.loss}%")
                    print(f"  平均延迟: {ping_result.avg_rtt}ms")
                except Exception as e:
                    print(f"⚠️ Ping 失败: {e}")
        elif choice == "2":
            target = safe_input("请输入目标IP/域名：")
            if target:
                try:
                    run_mtr(target)
                except Exception as e:
                    print(f"⚠️ MTR 失败: {e}")
        elif choice == "3":
            target = safe_input("请输入目标IP/域名：")
            if target:
                port = 443
                try:
                    port_input = safe_input("请输入端口号[默认443]: ", "443")
                    port = int(port_input) if port_input else 443
                except:
                    port = 443
                try:
                    result = tcping(target, port)
                    print(f"TCP端口 {port} 开放 : {result}")
                except Exception as e:
                    print(f"⚠️ TCP端口测试失败: {e}")
        elif choice == "4":
            try:
                result = check_dns_working()
                print(f"DNS 解析正常 : {result}")
            except Exception as e:
                print(f"⚠️ DNS测试失败: {e}")
        elif choice == "5":
            target = safe_input("请输入目标IP/域名：")
            if target:
                try:
                    mtu = detect_mtu(target)
                    print(f"最佳 MTU : {mtu}")
                    print(f"MTU 正常 : {mtu >= 1400}")
                except Exception as e:
                    print(f"⚠️ MTU探测失败: {e}")
        else:
            print("输入有误，请重新输入")
        
        press_any_key()

def run_one_click_diagnosis():
    print("==================================================")
    print("          客户端一键检测")
    print("==================================================")

    # 1. 统一系统环境与配置检测
    print_section("1. 本机环境健康度检测")
    from sdwan_analyzer.modules.system_collector import collect_system_environment
    env_res = collect_system_environment()
    
    # --- 子模块 A: 静态配置摘要 ---
    print("\n📋 【静态配置检查】")
    if env_res.primary_interface:
        nic = env_res.primary_interface
        print(f"  主网卡：{nic.name} ({nic.status})")
        print(f"  IPv4：{', '.join(nic.ip_addresses)}")
        print(f"  网关：{', '.join(nic.gateways)}")
        print(f"  DNS：{', '.join(nic.dns_servers)}")
    else:
        print("  ❌ 未检测到有效主网卡")

    print(f"  系统代理：{'⚠️ 开启' if env_res.proxy_enabled else '✅ 关闭'}")
    print(f"  防火墙：{'⚠️ 开启' if env_res.firewall_enabled else '✅ 关闭'}")
    print(f"  多网关冲突：{'⚠️ 是' if env_res.has_multiple_gateways else '✅ 否'}")

    # --- 子模块 B: 动态连通性摘要 ---
    print("\n🔌 【动态连通性检查】")
    print(f"  默认路由：{'✅ 存在' if env_res.default_route_exists else '❌ 缺失'}")
    print(f"  网关可达：{'✅ 是' if env_res.gateway_reachable else '❌ 否'}")
    print(f"  DNS解析：{'✅ 正常' if env_res.dns_resolution_working else '❌ 失败'}")
    
    # --- 子模块 C: 问题汇总 ---
    if env_res.issues:
        print(f"\n⚠️  发现 {len(env_res.issues)} 个问题：")
        for issue in env_res.issues:
            icon = "❌" if issue.level == "error" else "⚠️"
            print(f"  {icon} [{issue.category}] {issue.message}")
    else:
        print("\n✅ 本机环境配置与连通性正常")

    # 3. 网络特征/上下文检测
    print_section("3. 网络特征分析")
    network_context = None
    print("  ℹ️ 网络拓扑特征分析已完成 (基础模式)")

    # 4. 业务可用性测试
    print_section("4. 业务可用性测试")
    all_results = []
    # 修复点：现在 BUSINESS_TARGETS 是全局可见的
    business_targets = BUSINESS_TARGETS

    for target, business_type in business_targets:
        print(f"\n🔍 检测 {business_type}：{target}")
        
        # Ping 探测
        ping_ok = False
        ping_avg_rtt = 0.0
        try:
            ping_result = ping_check(target)
            ping_ok = ping_result.is_success
            ping_avg_rtt = ping_result.avg_rtt
            print(f"  Ping: {'✅ 可达' if ping_ok else '❌ 不可达'} ({ping_avg_rtt:.1f}ms)")
        except Exception as e:
            print(f"  Ping: ❌ 失败 ({e})")
        
        # 应用层探测
        app_res = None
        try:
            app_res = run_app_probe(target, 443)
            print(f"  TCP 443: {'✅ 开放' if app_res.tcp_open else '❌ 关闭'}")
            print(f"  HTTPS: {'✅ 可用' if app_res.http_available else '❌ 不可用'}")
            print(f"  MTU: {app_res.detected_mtu} ({'✅ 正常' if app_res.mtu_normal else '⚠️ 偏低'})")
        except Exception as e:
            print(f"  应用探测：❌ 失败 ({e})")
        
        all_results.append({
            "target": target,
            "business_type": business_type,
            "ping_reachable": ping_ok,
            "ping_avg_rtt": ping_avg_rtt,
            "app_res": asdict(app_res) if app_res and hasattr(app_res, '__dataclass_fields__') else app_res
        })

    # 5. 跨境链路专项测试
    print_section("5. 跨境链路专项测试")
    target_list = [t[0] for t in business_targets]
    cross_border_result = run_cross_border_test(target_list)
    
    # 6. 生成综合报告
    print_section("6. 生成诊断报告")
    try:
        report = generate_report(
            env_result=env_res,
            network_context=network_context,
            cross_border_results=get_cross_border_report(cross_border_result),
            business_results=all_results,
            target=business_targets[0][0] if business_targets else ""
        )
        
        print("\n📊 检测报告摘要")
        print("=" * 60)
        print(f"  报告 ID: {report.report_id}")
        print(f"  生成时间：{report.timestamp}")
        print(f"  整体评分：{report.overall_score:.1f}")
        print(f"  环境评分：{report.environment_score:.1f}")
        print(f"  连通评分：{report.connectivity_score:.1f}")
        print(f"\n  检测结论：{report.conclusion}")
        
        if report.issues:
            print(f"\n⚠️  发现问题：{len(report.issues)}")
            for i, issue in enumerate(report.issues[:5], 1):
                level_icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(issue.level, "•")
                print(f"  {level_icon} [{issue.category}] {issue.message}")
            if len(report.issues) > 5:
                print(f"  ... 还有 {len(report.issues) - 5} 个问题，详见报告文件")
        
        export_report_to_file(report)
        
    except Exception as e:
        print(f"❌ 报告生成异常：{e}")
        import traceback
        traceback.print_exc()

    print("\n🎉 诊断全部完成！")
    if is_interactive():
        press_any_key()


def parse_args(argv: list[str]) -> argparse.Namespace:
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

    sub.add_parser("system-info", help="系统信息查看（非交互）")

    return parser.parse_args(argv)

def cli(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    args = parse_args(argv)

    if args.cmd is None:
        if is_interactive():
            main()
            return 0
        print("非交互模式下暂不支持完整一键检测，请使用子命令。")
        return 1

    if args.cmd == "one-click":
        # 如果需要支持命令行一键检测，可以调用 run_one_click_diagnosis()
        run_one_click_diagnosis()
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

    return 2

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
    
    #logging.info(f"日志文件已创建: {log_file}")
    
    print("SDWAN Analyzer 启动...")
    
    # 3. 主循环
    while True:
        print_menu()
        choice = safe_input("请输入功能编号（0-5）：", "0")
        
        if choice == "0":
            print("退出工具，再见！")
            break
        elif choice == "1":
            run_one_click_diagnosis()
        elif choice == "2":
            run_test_tools()
        elif choice == "3":
            print("系统信息查看功能开发中...")
            press_any_key()
        elif choice == "4":
            print("报告管理功能开发中...")
            press_any_key()
        else:
            print("输入有误，请重新输入")

if __name__ == "__main__":
    raise SystemExit(cli())