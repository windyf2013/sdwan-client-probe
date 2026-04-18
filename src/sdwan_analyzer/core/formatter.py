"""
商业级信息输出格式化器
设计原则：串口输出简洁精确，文件输出详细完整
"""
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

def format_console_header(title: str, width: int = 60) -> str:
    """格式化控制台标题（简洁版）"""
    return f"\n┏{'━' * width}┓\n┃ {title:<{width-2}} ┃\n┗{'━' * width}┛"

def format_console_section(title: str) -> str:
    """格式化控制台小节标题（简洁版）"""
    return f"\n▸ {title}:"

def format_console_item(label: str, value: Any, status: str = "") -> str:
    """格式化控制台单项信息（简洁版）"""
    if status:
        return f"  {label}: {value} {status}"
    return f"  {label}: {value}"

def format_console_metric(label: str, value: float, unit: str, threshold: Optional[Dict] = None) -> str:
    """格式化控制台度量指标（简洁版）"""
    if not threshold:
        return f"  {label}: {value} {unit}"
    
    status = ""
    if "ok" in threshold and value <= threshold["ok"]:
        status = "✓"
    elif "warn" in threshold and value <= threshold["warn"]:
        status = "⚠"
    else:
        status = "✗"
    
    return f"  {label}: {value:.1f} {unit} {status}"

def format_file_header(title: str, timestamp: str, report_id: str = "", version: str = "1.0") -> str:
    """格式化文件报告标题（详细版）"""
    header = f"""
{'='*80}
SD-WAN 分析报告
{'='*80}
报告标题: {title}
生成时间: {timestamp}
{('报告ID: ' + report_id + '\\n') if report_id else ''}版本信息: v{version}
{'='*80}

"""
    return header

def format_report_summary(report_data: Dict) -> str:
    """格式化报告摘要（与report.py协同工作）"""
    if not report_data:
        return "  [INFO] 报告数据为空"
    
    output = format_file_section("检测报告摘要")
    
    # 核心评分指标
    output += format_file_metric("整体评分", 
                                report_data.get('overall_score', 0), "分",
                                {"ok": 80, "warn": 60, "error": 40})
    
    output += format_file_metric("环境配置评分", 
                                report_data.get('environment_score', 0), "分",
                                {"ok": 85, "warn": 70, "error": 50})
    
    output += format_file_metric("连通性评分", 
                                report_data.get('connectivity_score', 0), "分",
                                {"ok": 85, "warn": 70, "error": 50})
    
    # 问题统计
    issues = report_data.get('issues', [])
    error_count = len([i for i in issues if i.get('level') == 'error'])
    warning_count = len([i for i in issues if i.get('level') == 'warning'])
    
    output += f"\n  • 检测结果统计:"
    output += f"\n    严重问题: {error_count} 个" if error_count > 0 else "\n    严重问题: 无"
    output += f"\n    警告事项: {warning_count} 个" if warning_count > 0 else "\n    警告事项: 无"
    
    # 检测结论
    if report_data.get('conclusion'):
        output += f"\n  • 检测结论: {report_data['conclusion']}"
    
    return output

def format_file_section(title: str) -> str:
    """格式化文件小节（详细版）"""
    return f"\n{'─'*60}\n{title.upper()}\n{'─'*60}\n"

def format_file_subsection(title: str) -> str:
    """格式化文件子小节（详细版）"""
    return f"\n{title}\n{'-'*40}"

def format_file_metric(label: str, value: Any, unit: str = "", 
                       threshold: Optional[Dict] = None, details: str = "") -> str:
    """格式化文件度量指标（详细版）"""
    if threshold:
        level = "正常"
        if "error" in threshold and (isinstance(value, (int, float)) and value > threshold["error"]):
            level = "异常"
        elif "warn" in threshold and (isinstance(value, (int, float)) and value > threshold["warn"]):
            level = "警告"
        
        output = f"  • {label}: {value} {unit} [{level}]"
        if details:
            output += f"\n    {details}"
        return output
    
    return f"  • {label}: {value} {unit}"

def format_file_table(headers: List[str], rows: List[List[str]], col_widths: List[int]) -> str:
    """格式化文件表格（详细版）"""
    table = "\n"
    # 表头
    header_line = "| " + " | ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths)) + " |"
    separator = "|" + "|".join("-" * (w + 2) for w in col_widths) + "|"
    
    table += header_line + "\n"
    table += separator + "\n"
    
    # 数据行
    for row in rows:
        table += "| " + " | ".join(f"{cell:<{w}}" for cell, w in zip(row, col_widths)) + " |\n"
    
    return table

def format_summary_critical_issues(issues: List[Dict]) -> str:
    """格式化关键问题摘要"""
    if not issues:
        return "  无关键问题"
    
    output = ""
    critical_count = len([i for i in issues if i.get('level') in ['error', 'critical']])
    warning_count = len([i for i in issues if i.get('level') == 'warning'])
    
    if critical_count > 0:
        output += f"  ✗ 关键问题: {critical_count} 个\n"
    if warning_count > 0:
        output += f"  ⚠ 警告问题: {warning_count} 个\n"
    
    return output.strip() if output else "  无关键问题"

def format_performance_meter(value: float, max_value: float, width: int = 20) -> str:
    """格式化性能计量条"""
    filled = int((value / max_value) * width)
    meter = "█" * filled + "░" * (width - filled)
    return f"[{meter}] {value:.1f}/{max_value}"

class ConsoleOutput:
    """控制台输出管理器（简洁精确）"""
    
    @staticmethod
    def system_status(env_data: Dict) -> str:
        """系统状态输出（简洁版）"""
        output = format_console_header("系统状态检查")
        
        # 主网络状态
        if env_data.get('primary_interface'):
            nic = env_data['primary_interface']
            output += f"\n  ▪ 网络: {nic.get('name', '未知')} ({nic.get('status', '未知')})"
            output += f"\n    IPv4: {', '.join(nic.get('ip_addresses', [])) or '未配置'}"
            output += f"\n    网关: {', '.join(nic.get('gateways', [])) or '未配置'}"
        
        # 关键状态
        output += f"\n  ▪ DNS解析: {'✓ 正常' if env_data.get('dns_resolution_working') else '✗ 失败'}"
        output += f"\n  ▪ 代理状态: {'⚠ 开启' if env_data.get('proxy_enabled') else '✓ 关闭'}"
        
        # 健康评分
        if env_data.get('config_score'):
            score = env_data['config_score']
            status = "✓" if score >= 80 else "⚠" if score >= 60 else "✗"
            output += f"\n  ▪ 配置健康度: {score}/100 {status}"
        
        return output
    
    @staticmethod
    def connectivity_results(results: List[Dict]) -> str:
        """连通性检测结果（简洁版）"""
        output = format_console_header("业务连通性检测")
        
        for result in results:
            target = result.get('target', '')
            reachable = result.get('basic_reachable', False)
            
            status_icon = "✓" if reachable else "✗"
            output += f"\n  {status_icon} {target}"
            
            if result.get('ping_result'):
                ping = result['ping_result']
                output += f" | 延迟: {ping.get('avg_rtt', 0):.1f}ms"
                output += f" | 丢包: {ping.get('loss', 0):.1f}%".ljust(12)
        
        return output
    
    @staticmethod
    def cross_border_summary(cross_result: Dict, mtu_results: List[Dict]) -> str:
        """跨境链路专项测试摘要（简洁版）"""
        output = format_console_header("跨境链路专项测试")
        
        # 链路质量汇总
        if cross_result.get('link_results'):
            output += "\n  ▪ 链路质量评估:"
            for link in cross_result['link_results'][:3]:  # 显示前3个重要链路
                score = link.get('stability_score', 0)
                status = "✓" if score >= 80 else "⚠" if score >= 60 else "✗"
                output += f"\n    {status} {link.get('target', '')}: {score:.1f}/100"
        
        # MTU探测摘要
        if mtu_results:
            output += "\n  ▪ MTU路径探测:"
            for mtu in mtu_results[:3]:
                status = "✓" if mtu.get('mtu', 0) >= 1400 else "⚠" if mtu.get('mtu', 0) >= 1300 else "✗"
                output += f"\n    {status} {mtu.get('target', '')}: MTU={mtu.get('mtu', 0)}"
        
        return output

def format_console_report_summary(report_data: Dict) -> str:
    """格式化控制台报告摘要（简洁版）"""
    if not report_data:
        return "  [INFO] 报告数据为空"
    
    output = "\n📊 检测摘要:"
    
    # 核心评分
    overall_score = report_data.get('overall_score', 0)
    status = "✓" if overall_score >= 80 else "⚠" if overall_score >= 60 else "✗"
    output += f"\n  ▪ 整体评分: {overall_score:.1f}/100 {status}"
    
    # 问题统计
    issues = report_data.get('issues', [])
    error_count = len([i for i in issues if i.get('level') == 'error'])
    warning_count = len([i for i in issues if i.get('level') == 'warning'])
    
    if error_count > 0:
        output += f"\n  ✗ 问题: {error_count}个严重/{warning_count}个警告"
    elif warning_count > 0:
        output += f"\n  ⚠ 关注: {warning_count}个警告事项"
    else:
        output += f"\n  ✓ 状态: 系统运行正常"
    
    return output

class FileOutput:
    """文件输出管理器（详细完整）"""
    
    @staticmethod
    def system_detailed_report(env_data: Dict) -> str:
        """系统详细报告（详细版）"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output = format_file_header("系统环境详细报告", timestamp)
        
        output += format_file_section("网络接口配置")
        
        if env_data.get('interfaces'):
            for nic in env_data['interfaces']:
                output += format_file_subsection(f"接口: {nic.get('name', '未知')}")
                output += format_file_metric("状态", nic.get('status', '未知'), "")
                output += format_file_metric("MAC地址", nic.get('mac_address', '未知'), "")
                output += format_file_metric("IP地址", ', '.join(nic.get('ip_addresses', [])), "")
                output += format_file_metric("网关", ', '.join(nic.get('gateways', [])), "")
                output += format_file_metric("DNS服务器", ', '.join(nic.get('dns_servers', [])), "")
        
        output += format_file_section("系统配置检测")
        output += format_file_metric("DNS解析状态", 
                                    "正常" if env_data.get('dns_resolution_working') else "异常", "",
                                    {"normal": "正常"}, "域名解析功能检测")
        output += format_file_metric("代理状态", 
                                    "开启" if env_data.get('proxy_enabled') else "关闭", "", 
                                    {"normal": "关闭"}, "HTTP代理配置检测")
        
        if env_data.get('config_score'):
            output += format_file_metric("配置健康度评分", env_data['config_score'], "分", 
                                        {"ok": 80, "warn": 60}, "基于网络配置完整性的综合评分")
        
        return output
    
    @staticmethod
    def connectivity_detailed_report(results: List[Dict]) -> str:
        """连通性详细报告（详细版）"""
        output = format_file_section("业务连通性详细测试")
        
        headers = ["目标", "协议", "延迟(ms)", "丢包率(%)", "状态", "深度检测"]
        col_widths = [25, 8, 10, 10, 8, 8]
        
        rows = []
        for result in results:
            ping = result.get('ping_result', {})
            app = result.get('app_probe_result', {})
            
            row = [
                result.get('target', ''),
                "TCP/443" if app else "ICMP",
                f"{ping.get('avg_rtt', 0):.1f}",
                f"{ping.get('loss', 0):.1f}",
                "正常" if result.get('basic_reachable') else "异常",
                "已执行" if result.get('deep_check_completed') else "未执行"
            ]
            rows.append(row)
        
        output += format_file_table(headers, rows, col_widths)
        
        # 详细分析
        output += format_file_subsection("连接质量分析")
        for result in results:
            if result.get('ping_result'):
                ping = result['ping_result']
                output += f"\n  • {result.get('target')}:"
                output += format_file_metric("平均延迟", ping.get('avg_rtt', 0), "ms", 
                                            {"ok": 50, "warn": 100, "error": 200})
                output += format_file_metric("抖动方差", ping.get('variance', 0), "ms", 
                                            {"ok": 10, "warn": 20, "error": 50})
                output += format_file_metric("丢包率", ping.get('loss', 0), "%", 
                                            {"ok": 1, "warn": 3, "error": 5})
        
        return output
    
    @staticmethod
    def cross_border_detailed_report(cross_result: Dict, mtu_results: List[Dict]) -> str:
        """跨境链路详细报告（详细版）"""
        output = format_file_section("跨境链路专项测试详细报告")
        
        # 链路质量详细表
        if cross_result.get('link_results'):
            output += format_file_subsection("链路质量评估")
            
            headers = ["目标", "稳定性评分", "延迟(ms)", "丢包率(%)", "抖动(ms)", "DNS质量"]
            col_widths = [25, 12, 10, 10, 10, 8]
            
            rows = []
            for link in cross_result['link_results']:
                row = [
                    link.get('target', ''),
                    f"{link.get('stability_score', 0):.1f}/100",
                    f"{link.get('avg_latency', 0):.0f}",
                    f"{link.get('packet_loss', 0):.1f}",
                    f"{link.get('jitter', 0):.1f}",
                    "正常" if link.get('dns_quality', 0) >= 80 else "异常"
                ]
                rows.append(row)
            
            output += format_file_table(headers, rows, col_widths)
        
        # MTU探测详情
        if mtu_results:
            output += format_file_subsection("MTU路径探测")
            for mtu in mtu_results:
                status = "正常" if mtu.get('mtu', 0) >= 1400 else "偏低" if mtu.get('mtu', 0) >= 1300 else "异常"
                output += format_file_metric(mtu.get('target', ''), mtu.get('mtu', 0), "字节", 
                                            {"ok": 1400, "warn": 1300, "error": 1200}, f"状态: {status}")
        
        # 整体评估
        if cross_result.get('overall_score'):
            output += format_file_subsection("整体评估")
            output += format_file_metric("总体评分", cross_result['overall_score'], "分", 
                                        {"ok": 80, "warn": 60, "error": 40})
            output += format_file_metric("测试结论", cross_result.get('summary', ''), "", {})
        
        return output