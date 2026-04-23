# d:/AI/testing/proj5/sdwan_analyzer/src/sdwan_analyzer/modules/report.py
# 恢复HTML报告功能（保留JSON报告删除状态）

import os
from datetime import datetime
from typing import Optional, Any
from dataclasses import dataclass, field, asdict

from sdwan_analyzer.models.diagnose import FinalReport, Issue, SystemEnvironmentResult

# 导入配置以获取 REPORT_DIR
from sdwan_analyzer.config import REPORT_DIR

def export_html_report(report: FinalReport, path: Optional[str] = None):
    """导出HTML格式报告"""
    
    # 第一节: 处理路径参数
    if path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"瑞斯康达跨境FAQ--用户环境一键自查报告_{timestamp}.html"
        path = os.path.join(REPORT_DIR, filename)
    
    # 第二节: 生成HTML内容
    html_content = generate_commercial_html_report(report)
    
    # 第三节: 文件保存过程
    try:
        # 确保目录存在
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # 写入文件
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"HTML报告已保存至: {path}")
        
        return True
        
    except Exception as e:
        print(f"HTML报告保存失败: {e}")
        return False

def generate_commercial_html_report(report: FinalReport) -> str:
    """生成商用级HTML格式报告 - SDWAN诊断驾驶舱版"""
    
    # 1. 数据提取
    report_id = getattr(report, 'report_id', 'N/A')
    timestamp = getattr(report, 'timestamp', 'N/A')
    overall_score = getattr(report, 'overall_score', 0)
    
    detailed_conclusion = getattr(report, 'detailed_conclusion', '')
    conclusion = getattr(report, 'conclusion', '')
    display_conclusion = detailed_conclusion if detailed_conclusion else conclusion
    
    status_notes = getattr(report, 'status_notes', [])
    system = getattr(report, 'system', {})
    app_probes = getattr(report, 'app_probes', [])
    issues = getattr(report, 'issues', [])
    recommendations = getattr(report, 'recommendations', [])

    # 2. 生成模块 HTML
    # 核心生命体征 (网关/DNS/路由)
    vitals_html = _generate_vitals_cards(system)
    # 环境合规性 (防火墙/代理)
    compliance_html = _generate_compliance_badges(system)
    # 业务应用列表
    apps_html = _generate_app_list(app_probes)
    # 详细网卡与路由 (证据层)
    details_html = _generate_evidence_section(system)
    # 问题与建议
    issues_html = _generate_issues_and_actions(issues, recommendations)
    # 风险标签
    tags_html = _generate_risk_tags(status_notes)

    # 3. 动态样式计算
    score_color = "#10b981" if overall_score >= 80 else "#f59e0b" if overall_score >= 60 else "#ef4444"
    score_bg = "#ecfdf5" if overall_score >= 80 else "#fffbeb" if overall_score >= 60 else "#fef2f2"
    score_icon = "🟢" if overall_score >= 80 else "🟡" if overall_score >= 60 else "🔴"

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>瑞斯康达跨境FAQ--用户环境一键自查报告 - {report_id}</title>
    <style>
        :root {{
            --primary: #2563eb; --success: #10b981; --warning: #f59e0b; --danger: #ef4444;
            --gray-50: #f9fafb; --gray-100: #f3f4f6; --gray-200: #e5e7eb; --gray-600: #4b5563; --gray-800: #1f2937;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.5; color: var(--gray-800); background: #fff; font-size: 14px; }}
        
        .container {{ max-width: 1000px; margin: 0 auto; padding: 40px 20px; }}
        
        /* --- 头部：决策层 --- */
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 1px solid var(--gray-200); }}
        .title-group h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 5px; }}
        .title-group p {{ font-size: 13px; color: var(--gray-600); }}
        
        .score-box {{ text-align: right; }}
        .score-val {{ font-size: 48px; font-weight: 800; color: {score_color}; line-height: 1; }}
        .score-lbl {{ font-size: 12px; color: var(--gray-600); font-weight: 600; text-transform: uppercase; }}

        /* --- 结论横幅 --- */
        .conclusion-banner {{ background: {score_bg}; border-left: 5px solid {score_color}; padding: 20px; border-radius: 6px; margin-bottom: 30px; display: flex; align-items: start; gap: 15px; }}
        .conclusion-icon {{ font-size: 24px; }}
        .conclusion-content h3 {{ font-size: 16px; font-weight: 700; margin-bottom: 5px; }}
        .conclusion-content p {{ font-size: 14px; color: var(--gray-600); margin-bottom: 10px; }}
        
        /* --- 风险标签 --- */
        .risk-tags {{ display: flex; flex-wrap: wrap; gap: 8px; }}
        .tag {{ font-size: 12px; padding: 4px 10px; border-radius: 12px; background: #fff; border: 1px solid var(--gray-200); color: var(--gray-600); }}
        .tag.warn {{ background: #fffbeb; border-color: #fcd34d; color: #b45309; }}

        /* --- 核心生命体征 (3列网格) --- */
        .vitals-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 30px; }}
        .vital-card {{ background: #fff; border: 1px solid var(--gray-200); border-radius: 8px; padding: 15px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }}
        .vital-title {{ font-size: 12px; font-weight: 600; color: var(--gray-600); text-transform: uppercase; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; }}
        .vital-value {{ font-size: 18px; font-weight: 700; color: var(--gray-800); margin-bottom: 4px; word-break: break-all; }}
        .vital-status {{ font-size: 12px; font-weight: 600; }}
        .st-ok {{ color: var(--success); }} .st-fail {{ color: var(--danger); }} .st-warn {{ color: var(--warning); }}

        /* --- 中间层：合规性与业务 (2列网格) --- */
        .mid-grid {{ display: grid; grid-template-columns: 1fr 1.5fr; gap: 20px; margin-bottom: 30px; }}
        .panel {{ background: #fff; border: 1px solid var(--gray-200); border-radius: 8px; overflow: hidden; }}
        .panel-head {{ padding: 12px 16px; background: var(--gray-50); border-bottom: 1px solid var(--gray-200); font-weight: 600; font-size: 14px; }}
        .panel-body {{ padding: 16px; }}

        /* 合规性徽章 */
        .badge-row {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px dashed var(--gray-100); }}
        .badge {{ padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
        .b-green {{ background: #d1fae5; color: #065f46; }}
        .b-red {{ background: #fee2e2; color: #991b1b; }}
        
        /* 应用列表 */
        .app-item {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--gray-100); }}
        .app-item:last-child {{ border-bottom: none; }}
        .app-name {{ font-weight: 500; font-size: 14px; }}
        .app-desc {{ font-size: 12px; color: var(--gray-500); }}
        .app-res {{ text-align: right; }}
        
        /* --- 底层：证据层 (紧凑表格) --- */
        .evidence-section {{ margin-bottom: 30px; }}
        .evidence-grid {{ display: flex; gap: 20px; flex-wrap: wrap; }} 
        .data-list {{ max-height: 300px; overflow-y: auto; font-size: 12px; padding-right: 5px; }}
        /* 自定义滚动条样式 */
        .data-list::-webkit-scrollbar {{ width: 6px; }}
        .data-list::-webkit-scrollbar-thumb {{ background: #cbd5e1; border-radius: 3px; }}
        .data-row {{ padding: 6px 0; border-bottom: 1px solid var(--gray-100); display: flex; justify-content: space-between; }}
        .data-row span:first-child {{ color: var(--gray-600); }}
        .data-row span:last-child {{ font-family: monospace; color: var(--gray-800); }}

        /* --- 问题与建议 --- */
        .action-panel {{ background: #fff; border: 1px solid var(--gray-200); border-radius: 8px; padding: 20px; }}
        .issue-box {{ padding: 12px; background: #fef2f2; border-left: 4px solid var(--danger); margin-bottom: 10px; border-radius: 4px; }}
        .issue-box.warn {{ background: #fffbeb; border-left-color: var(--warning); }}
        .rec-list {{ list-style: none; margin-top: 20px; }}
        .rec-item {{ padding: 8px 0; border-bottom: 1px solid var(--gray-100); font-size: 14px; display: flex; gap: 10px; }}
        
        .footer {{ text-align: center; font-size: 12px; color: #9ca3af; margin-top: 40px; }}
        
        @media print {{ .container {{ width: 100%; max-width: none; }} .panel {{ break-inside: avoid; }} }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 1. 头部 -->
        <div class="header">
            <div class="title-group">
                <h1>瑞斯康达跨境FAQ--用户环境一键自查报告</h1>
                <p>ID: {report_id} | 时间: {timestamp}</p>
            </div>
            <div class="score-box">
                <div class="score-val">{overall_score:.0f}</div>
                <div class="score-lbl">健康评分</div>
            </div>
        </div>

        <!-- 2. 结论与风险 -->
        <div class="conclusion-banner">
            <div class="conclusion-icon">{score_icon}</div>
            <div class="conclusion-content">
                <h3>诊断结论</h3>
                <p>{display_conclusion}</p>
                {tags_html}
            </div>
        </div>

        <!-- 3. 核心生命体征 (Vitals) -->
        <h4 style="font-size:14px; color:var(--gray-600); margin-bottom:10px;">📡 核心网络诊断结果</h4>
        <div class="vitals-grid">
            {vitals_html}
        </div>

        <!-- 4. 环境与业务 (Mid Layer) -->
        <div class="mid-grid">
            <!-- 左：合规性 -->
            <div class="panel">
                <div class="panel-head">🛡️ 环境合规性</div>
                <div class="panel-body">
                    {compliance_html}
                </div>
            </div>
            <!-- 右：业务应用 -->
            <div class="panel">
                <div class="panel-head">🌐 业务应用可达性</div>
                <div class="panel-body">
                    {apps_html}
                </div>
            </div>
        </div>

        <!-- 5. 证据层 (Details) -->
        <div class="evidence-section">
            <h4 style="font-size:14px; color:var(--gray-600); margin-bottom:10px;">💻 网络配置详情 (Evidence)</h4>
            <div class="panel">
                <div class="panel-body">
                    {details_html}
                </div>
            </div>
        </div>

        <!-- 6. 行动指南 -->
        <div class="action-panel">
            {issues_html}
        </div>

        <div class="footer">Generated by SD-WAN Intelligent Analyzer v1.2</div>
    </div>
</body>
</html>
'''

# ================= 辅助函数 =================

def _generate_vitals_cards(system) -> str:
    """生成3个核心生命体征卡片"""
    metrics = _extract_system_metrics(system)
    
    # 1. 网关
    gw_ok = metrics['gateway_reachable']
    gw_html = f'''
    <div class="vital-card">
        <div class="vital-title">🚪 默认网关</div>
        <div class="vital-value">{metrics['primary_gateway']}</div>
        <div class="vital-status {'st-ok' if gw_ok else 'st-fail'}">{'✅ 连通' if gw_ok else '❌ 不可达'}</div>
    </div>'''
    
    # 2. DNS
    dns_ok = metrics['dns_resolution_working']
    dns_str = metrics['dns_servers'][0] if metrics['dns_servers'] else '未配置'
    dns_html = f'''
    <div class="vital-card">
        <div class="vital-title">📞 DNS 解析</div>
        <div class="vital-value" style="font-size:14px">{dns_str}</div>
        <div class="vital-status {'st-ok' if dns_ok else 'st-warn'}">{'✅ 正常' if dns_ok else '⚠️ 异常/未知'}</div>
    </div>'''
    
    # 3. 路由
    route_ok = metrics['default_route_exists']
    route_html = f'''
    <div class="vital-card">
        <div class="vital-title">🗺️ 缺省路由</div>
        <div class="vital-value">{len(metrics['default_routes'])} 条</div>
        <div class="vital-status {'st-ok' if route_ok else 'st-fail'}">{'✅ 存在' if route_ok else '❌ 缺失'}</div>
    </div>'''
    
    return gw_html + dns_html + route_html

def _generate_compliance_badges(system) -> str:
    """生成合规性徽章"""
    metrics = _extract_system_metrics(system)
    
    fw_badge = '<span class="badge b-red">已开启</span>' if metrics['firewall_enabled'] else '<span class="badge b-green">已关闭</span>'
    proxy_badge = '<span class="badge b-red">已开启</span>' if metrics['proxy_enabled'] else '<span class="badge b-green">未开启</span>'
    
    return f'''
    <div class="badge-row">
        <span>Windows 防火墙</span>
        {fw_badge}
    </div>
    <div class="badge-row">
        <span>系统代理</span>
        {proxy_badge}
    </div>
    '''

def _generate_app_list(app_probes) -> str:
    """生成应用列表"""
    if not app_probes:
        return '<div style="color:#999;text-align:center">无数据</div>'
    
    html = ''
    for probe in app_probes:
        target = probe.get('target', 'Unknown') if isinstance(probe, dict) else getattr(probe, 'target', 'Unknown')
        reachable = probe.get('ping_reachable', False) if isinstance(probe, dict) else getattr(probe, 'ping_reachable', False)
        desc = probe.get('description', '') if isinstance(probe, dict) else getattr(probe, 'description', '')
        ping_status = probe.get('ping_status', '') if isinstance(probe, dict) else getattr(probe, 'ping_status', '')
        
        status_badge = '<span class="badge b-green">正常</span>' if reachable else '<span class="badge b-red">异常</span>'
        
        html += f'''
        <div class="app-item">
            <div>
                <div class="app-name">{target}</div>
                <div class="app-desc">{desc}</div>
            </div>
            <div class="app-res">
                {status_badge}
                <div style="font-size:11px;color:#666;margin-top:2px">{ping_status}</div>
            </div>
        </div>
        '''
    return html

def _generate_evidence_section(system) -> str:
    """生成证据层：网卡和路由详情 (优化版：布局宽松 + 路由子网掩码)"""
    metrics = _extract_system_metrics(system)
    
    # --- 1. 网卡部分 (优化布局) ---
    all_interfaces = metrics.get('interfaces', [])
    
    # 分类：已连接 vs 其他
    enabled_nics = [nic for nic in all_interfaces if _safe_get(nic, 'status') == 'Connected']
    disabled_nics = [nic for nic in all_interfaces if _safe_get(nic, 'status') != 'Connected']
    
    html_parts = []
    
    # A. 已启用网卡 (使用更宽松的卡片布局)
    html_parts.append('<div style="margin-bottom: 25px;">')
    html_parts.append('<strong style="font-size:14px; display:block; margin-bottom:12px; color:var(--gray-800); border-left:4px solid var(--success); padding-left:10px;">✅ 已启用网络接口</strong>')
    html_parts.append('<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px;">')
    
    if enabled_nics:
        for nic in enabled_nics:
            name = _safe_get(nic, 'name', 'Unknown')
            desc = _safe_get(nic, 'description', '')
            mac = _safe_get(nic, 'mac_address', '')
            ips = _safe_get(nic, 'ip_addresses', [])
            masks = _safe_get(nic, 'subnet_masks', [])
            gateways = _safe_get(nic, 'gateways', [])
            dns_servers = _safe_get(nic, 'dns_servers', [])
            is_primary = _safe_get(nic, 'is_primary', False)
            
            # 智能识别类型
            nic_type = "Ethernet"
            desc_lower = desc.lower()
            name_lower = name.lower()
            if any(k in desc_lower or k in name_lower for k in ['wireless', 'wi-fi', 'wlan', '802.11']):
                nic_type = "WLAN"
            elif any(k in desc_lower or k in name_lower for k in ['vpn', 'virtual', 'tunnel', 'ppp']):
                nic_type = "VPN/Virtual"
            
            # 构建 IP/Mask 显示
            ip_details = []
            for i, ip in enumerate(ips):
                mask = masks[i] if i < len(masks) else "?"
                ip_details.append(f"{ip} <span style='color:#999'>/{mask}</span>")
            ip_html = "<br>".join(ip_details) if ip_details else "<span style='color:#999'>未获取IP</span>"
            
            gw_html = ", ".join(gateways) if gateways else "<span style='color:#999'>无</span>"
            dns_html = ", ".join(dns_servers) if dns_servers else "<span style='color:#999'>无</span>"
            
            primary_tag = '<span style="background:var(--danger); color:white; font-size:10px; padding:2px 6px; border-radius:4px; margin-left:8px; vertical-align:middle;">主网卡</span>' if is_primary else ''
            
            html_parts.append(f'''
            <div style="background:#fff; border:1px solid var(--gray-200); border-radius:8px; padding:15px; box-shadow:0 2px 4px rgba(0,0,0,0.02);">
                <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom:10px; border-bottom:1px solid var(--gray-100); padding-bottom:8px;">
                    <div>
                        <div style="font-weight:700; color:var(--gray-800); font-size:14px;">{name}{primary_tag}</div>
                        <div style="font-size:12px; color:var(--gray-500); margin-top:2px;">{desc} ({nic_type})</div>
                    </div>
                    <div style="font-family:monospace; font-size:11px; color:var(--gray-400);">{mac}</div>
                </div>
                <div style="font-size:13px; line-height:1.8; color:var(--gray-700);">
                    <div><strong style="color:var(--gray-500); width:60px; display:inline-block;">IP地址:</strong> {ip_html}</div>
                    <div><strong style="color:var(--gray-500); width:60px; display:inline-block;">网关:</strong> {gw_html}</div>
                    <div><strong style="color:var(--gray-500); width:60px; display:inline-block;">DNS:</strong> {dns_html}</div>
                </div>
            </div>
            ''')
    else:
        html_parts.append('<div style="grid-column:1/-1; padding:20px; text-align:center; color:#999; background:var(--gray-50); border-radius:8px;">无已连接网卡</div>')
    
    html_parts.append('</div></div>') # End grid and section

    # B. 未启用/未连接网卡 (简化列表，避免占用过多空间)
    if disabled_nics:
        html_parts.append('<div style="margin-bottom: 25px; opacity:0.8;">')
        html_parts.append('<strong style="font-size:14px; display:block; margin-bottom:12px; color:var(--gray-500); border-left:4px solid var(--gray-300); padding-left:10px;">⚪ 未启用/未连接接口</strong>')
        html_parts.append('<div style="background:var(--gray-50); border-radius:8px; padding:10px 15px; max-height:200px; overflow-y:auto;">')
        
        for nic in disabled_nics:
            name = _safe_get(nic, 'name', 'Unknown')
            desc = _safe_get(nic, 'description', '')
            status = _safe_get(nic, 'status', 'Unknown')
            
            html_parts.append(f'''
            <div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px dashed var(--gray-200); font-size:12px;">
                <span style="color:var(--gray-600);"><strong>{name}</strong> <span style="color:#999">({desc})</span></span>
                <span style="color:var(--gray-400); font-family:monospace;">{status}</span>
            </div>
            '''
            )
        html_parts.append('</div></div>')

    # --- 2. 路由部分 (增强：显示子网掩码) ---
    html_parts.append('<div style="margin-bottom: 10px;">')
    html_parts.append('<strong style="font-size:14px; display:block; margin-bottom:12px; color:var(--gray-800); border-left:4px solid var(--primary); padding-left:10px;">🗺️ 缺省路由 (Default Routes)</strong>')
    
    if metrics['default_routes']:
        html_parts.append('''
        <div style="overflow-x:auto;">
            <table style="width:100%; border-collapse:collapse; font-size:13px; background:#fff; border:1px solid var(--gray-200); border-radius:8px; overflow:hidden;">
                <thead>
                    <tr style="background:var(--gray-50); text-align:left;">
                        <th style="padding:10px 15px; color:var(--gray-600); font-weight:600; border-bottom:1px solid var(--gray-200);">目标网络</th>
                        <th style="padding:10px 15px; color:var(--gray-600); font-weight:600; border-bottom:1px solid var(--gray-200);">子网掩码</th>
                        <th style="padding:10px 15px; color:var(--gray-600); font-weight:600; border-bottom:1px solid var(--gray-200);">网关地址</th>
                        <th style="padding:10px 15px; color:var(--gray-600); font-weight:600; border-bottom:1px solid var(--gray-200);">接口 IP</th>
                        <th style="padding:10px 15px; color:var(--gray-600); font-weight:600; border-bottom:1px solid var(--gray-200);">Metric</th>
                    </tr>
                </thead>
                <tbody>
        ''')
        
        for r in metrics['default_routes']:
            # r 格式通常为: "0.0.0.0  0.0.0.0  10.10.100.1  10.10.100.161  281"
            parts = r.split()
            if len(parts) >= 5:
                target_net = parts[0]
                subnet_mask = parts[1]  # 【新增】提取子网掩码
                gw = parts[2]
                iface_ip = parts[3]
                metric = parts[4]
                
                html_parts.append(f'''
                <tr style="border-bottom:1px solid var(--gray-100);">
                    <td style="padding:10px 15px; font-family:monospace; color:var(--gray-800);">{target_net}</td>
                    <td style="padding:10px 15px; font-family:monospace; color:var(--gray-600);">{subnet_mask}</td>
                    <td style="padding:10px 15px; font-family:monospace; font-weight:600; color:var(--primary);">{gw}</td>
                    <td style="padding:10px 15px; font-family:monospace; color:var(--gray-600);">{iface_ip}</td>
                    <td style="padding:10px 15px; color:#999;">{metric}</td>
                </tr>
                '''
                )
        html_parts.append('</tbody></table></div>')
    else:
        html_parts.append('<div style="padding:15px; background:#fef2f2; border:1px solid #fecaca; border-radius:8px; color:var(--danger); font-size:13px;">⚠️ 未检测到缺省路由，可能导致无法访问互联网。</div>')
    
    html_parts.append('</div>')

    return "".join(html_parts)

def _generate_issues_and_actions(issues, recommendations) -> str:
    """生成问题与建议"""
    html = ''
    
    # 问题
    active_issues = [i for i in issues if _safe_get(i, 'level', 'info') != 'info']
    if active_issues:
        html += '<h4 style="font-size:14px;margin-bottom:10px;">⚠️  detected Issues</h4>'
        for issue in active_issues:
            level = _safe_get(issue, 'level', 'error')
            msg = _safe_get(issue, 'message', '')
            cls = "warn" if level == 'warning' else ""
            html += f'<div class="issue-box {cls}"><strong>[{level.upper()}]</strong> {msg}</div>'
    else:
        html += '<div style="color:var(--success);font-weight:600;margin-bottom:15px;">✅ 未发现严重配置或连通性问题</div>'
    
    # 建议
    if recommendations:
        html += '<h4 style="font-size:14px;margin-bottom:10px;margin-top:20px;">💡 优化建议</h4><ul class="rec-list">'
        for rec in recommendations:
            html += f'<li class="rec-item"><span style="color:var(--primary)">➤</span> {rec}</li>'
        html += '</ul>'
        
    return html

def _generate_risk_tags(status_notes) -> str:
    if not status_notes: return ''
    tags = []
    for note in status_notes:
        is_warn = any(k in note for k in ['代理', '多网关', '防火墙'])
        cls = "warn" if is_warn else ""
        tags.append(f'<span class="tag {cls}">{note}</span>')
    return f'<div class="risk-tags">{"".join(tags)}</div>'

# 保持之前的 _extract_system_metrics 和 _safe_get 不变
def _safe_get(obj, key, default=None):
    if isinstance(obj, dict): return obj.get(key, default)
    else: return getattr(obj, key, default)

def _extract_system_metrics(system):
    # ... (保持之前修复后的逻辑不变) ...
    if not system:
        return {'gateway_reachable': False, 'primary_gateway': 'N/A', 'dns_resolution_working': False, 'dns_servers': [], 'default_route_exists': False, 'default_routes': [], 'firewall_enabled': False, 'proxy_enabled': False, 'proxy_server': '', 'interfaces': []}
    
    fw_enabled = _safe_get(system, 'firewall_enabled', False)
    proxy_enabled = _safe_get(system, 'proxy_enabled', False)
    proxy_server = _safe_get(system, 'proxy_server', '')
    interfaces = _safe_get(system, 'interfaces', [])
    
    primary_nic = None
    for nic in interfaces:
        if _safe_get(nic, 'status', '') == 'Connected' and _safe_get(nic, 'ip_addresses', []):
            primary_nic = nic; break
            
    primary_gw = 'N/A'
    gw_reachable = _safe_get(system, 'gateway_reachable', False)
    if primary_nic:
        gws = _safe_get(primary_nic, 'gateways', [])
        if gws: primary_gw = gws[0]
        
    dns_servers = _safe_get(primary_nic, 'dns_servers', []) if primary_nic else []
    dns_working = _safe_get(system, 'dns_resolution_working', False)
    
    default_routes = _safe_get(system, 'default_routes', [])
    
    return {
        'gateway_reachable': gw_reachable, 'primary_gateway': primary_gw,
        'dns_resolution_working': dns_working, 'dns_servers': dns_servers,
        'default_route_exists': len(default_routes) > 0, 'default_routes': default_routes,
        'firewall_enabled': fw_enabled, 'proxy_enabled': proxy_enabled,
        'proxy_server': proxy_server, 'interfaces': interfaces
    }


# 生成报告数据的核心函数
def collect_report_data(env_result, business_results, cross_border_results=None, status_notes: list = None, detailed_conclusion: str = None):
    """收集报告所需数据（不生成JSON文件，仅供HTML报告使用）
    
    Args:
        env_result: 系统环境检测结果
        business_results: 业务连通性检测结果
        cross_border_results: 跨境测试结果(可选)
        status_notes: 状态备注列表 (如: ['系统代理已开启', '存在多网关路由'])
        detailed_conclusion: 详细的检测结论字符串
    """
    import uuid
    from datetime import datetime
    
    # 创建基础报告结构
    report = FinalReport(
        report_id=str(uuid.uuid4())[:8],
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        target=""
    )
    
    # 基础数据填充
    report.system = env_result
    report.app_probes = []
    report.issues = []
    
    # 【新增】保存状态备注和详细结论到报告对象中，供HTML渲染使用
    # 注意：FinalReport是dataclass，如果未定义这些字段，getattr在HTML生成时需做兼容处理，
    # 或者我们可以直接利用Python对象的动态特性添加属性（如果FinalReport允许）
    # 为了稳健性，我们这里直接赋值，假设FinalReport允许动态属性或通过asdict转换时能处理
    setattr(report, 'status_notes', status_notes or [])
    setattr(report, 'detailed_conclusion', detailed_conclusion or '')
    
    if business_results:
        for res in business_results:
            if res.get("target"):
                app_probe = {
                    "target": res.get("target"),
                    "ping_status": res.get("ping_status", "未检测"),
                    "ping_reachable": res.get("ping_reachable", False),
                    "description": res.get("description", "")
                }
                report.app_probes.append(app_probe)
    
    # 简单评分计算 (保持原有逻辑作为保底，但如果传入了detailed_conclusion，HTML中会优先使用传入的结论)
    total_items = len(business_results) if business_results else 1
    failed_items = sum(1 for res in business_results if not res.get("ping_reachable", True)) if business_results else 0
    
    report.overall_score = max(0, 100 - (failed_items * 100 / total_items))
    report.environment_score = 100
    report.connectivity_score = 100 - (failed_items * 100 / total_items) if total_items > 0 else 100
    
    # 如果没有传入详细结论，则使用默认生成的
    if not detailed_conclusion:
        if failed_items > 0:
            report.conclusion = f"发现 {failed_items} 个连通性问题"
            report.all_ok = False
        else:
            report.conclusion = "所有检测项正常"
            report.all_ok = True
    else:
        # 使用传入的详细结论
        report.conclusion = detailed_conclusion
        report.all_ok = failed_items == 0
        
    return report


# ================= 跨境链路专项测试报告功能 =================

def collect_cross_border_report_data(cross_border_result, mtu_results=None, dns_comparison_results=None):
    """收集跨境链路专项测试报告所需数据"""
    import uuid
    from datetime import datetime
    
    # 创建基础报告结构
    report = FinalReport(
        report_id=str(uuid.uuid4())[:8],
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        target="跨境链路专项测试"
    )
    
    # 基础数据填充
    report.system = {}
    report.app_probes = []
    report.issues = []
    
    # 计算跨境链路测试评分
    total_links = len(cross_border_result.link_results) if cross_border_result.link_results else 1
    passed_links = sum(1 for link in cross_border_result.link_results if link.stability_score >= 80) 
    
    report.overall_score = cross_border_result.overall_score
    report.environment_score = 0  # 跨境链路测试不涉及系统环境评分
    report.connectivity_score = cross_border_result.overall_score
    
    # 计算成功链接比例作为参考
    success_ratio = passed_links / total_links * 100 if total_links > 0 else 100
    
    # 生成结论
    if success_ratio >= 90:
        report.conclusion = "跨境链路质量优秀"
    elif success_ratio >= 70:
        report.conclusion = "跨境链路质量良好"
    elif success_ratio >= 50:
        report.conclusion = "跨境链路质量一般"
    else:
        report.conclusion = "跨境链路质量较差"
    
    report.all_ok = success_ratio >= 70

    # 【新增】将深度诊断数据动态绑定到 report 对象，供 HTML 渲染
    setattr(report, 'mtu_results', mtu_results or [])
    setattr(report, 'dns_comparison_results', dns_comparison_results or [])
    
    # 假设 cross_border_result 中已经包含了 google_dns_reachable 状态
    # 如果没有，需要在 main.py 中计算并传入，这里暂存一个占位符
    google_dns_ok = getattr(cross_border_result, 'google_dns_reachable', False)
    setattr(report, 'google_dns_reachable', google_dns_ok)
    
    return report


def generate_cross_border_html_report(report: FinalReport, cross_border_result) -> str:
    """生成商用级跨境链路专项测试HTML报告 - SLA仪表盘风格"""
    
    # 1. 数据提取
    report_id = getattr(report, 'report_id', 'N/A')
    timestamp = getattr(report, 'timestamp', 'N/A')
    overall_score = getattr(report, 'overall_score', 0)
    
    link_results = getattr(cross_border_result, 'link_results', [])
    test_duration = getattr(cross_border_result, 'test_duration', 0)
    
    # 【新增】提取深度诊断数据
    mtu_results = getattr(report, 'mtu_results', [])
    dns_comparison = getattr(report, 'dns_comparison_results', [])
    google_dns_ok = getattr(report, 'google_dns_reachable', False)
    
    # 计算细分维度得分 (模拟算法，实际可根据权重调整)
    avg_latency = sum(getattr(l, 'avg_latency', 0) for l in link_results) / len(link_results) if link_results else 0
    avg_loss = sum(getattr(l, 'packet_loss', 0) for l in link_results) / len(link_results) if link_results else 0
    avg_jitter = sum(getattr(l, 'jitter', 0) for l in link_results) / len(link_results) if link_results else 0
    
    # 简单换算成百分制得分
    latency_score = max(0, 100 - (avg_latency / 5)) # 假设500ms为0分
    loss_score = max(0, 100 - (avg_loss * 20))      # 假设5%丢包为0分
    jitter_score = max(0, 100 - (avg_jitter * 2))   # 假设50ms抖动为0分
    
    # 确定主色调
    score_color = "#10b981" if overall_score >= 80 else "#f59e0b" if overall_score >= 60 else "#ef4444"
    score_bg = "#ecfdf5" if overall_score >= 80 else "#fffbeb" if overall_score >= 60 else "#fef2f2"
    
    # 2. 生成模块 HTML
    links_matrix_html = _generate_links_matrix(link_results)
    #benchmark_html = _generate_benchmark_table(avg_latency, avg_loss, overall_score)
    recommendations_html = _generate_cross_border_recommendations_html(link_results, overall_score)
    
    # 【新增】生成独立链路 SLA 表
    link_sla_html = _generate_link_sla_table(link_results)
    
    # 【新增】提取 DNS 测试的目标域名，如果没有则默认
    dns_target = "www.google.com"
    if dns_comparison and len(dns_comparison) > 0:
        # 尝试从第一个对比结果中获取目标，如果数据结构支持
        # 注意：当前的 dns_comparison_list 结构可能在 main.py 中构建时没有存 target，
        # 所以这里主要依赖默认值，或者你可以修改 main.py 传入 target
        pass 
        
    # 【新增】提取网关 DNS IP
    gw_dns_ip = "N/A"
    if dns_comparison and len(dns_comparison) > 0:
        gw_dns_ip = dns_comparison[0].get("server_local", "N/A")

    deep_dive_html = _generate_deep_dive_section(
        mtu_results, 
        google_dns_ok, 
        dns_comparison,
        dns_target_domain=dns_target,
        gateway_dns_ip=gw_dns_ip
    )

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>瑞斯康达跨境FAQ--跨境链路SLA测试报告 - {report_id}</title>
    <style>
        :root {{
            --primary: #2563eb; --success: #10b981; --warning: #f59e0b; --danger: #ef4444;
            --gray-50: #f9fafb; --gray-100: #f3f4f6; --gray-200: #e5e7eb; --gray-600: #4b5563; --gray-800: #1f2937;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.5; color: var(--gray-800); background: #fff; font-size: 14px; }}
        
        .container {{ max-width: 1100px; margin: 0 auto; padding: 40px 20px; }}
        
        /* --- 头部 --- */
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 1px solid var(--gray-200); }}
        .title-group h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 5px; }}
        .title-group p {{ font-size: 13px; color: var(--gray-600); }}
        .badge-intl {{ background: #dbeafe; color: #1e40af; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-left: 10px; }}
        
        /* --- SLA 仪表盘 (4列) --- */
        .sla-dashboard {{ display: grid; grid-template-columns: 1.5fr 1fr 1fr 1fr; gap: 20px; margin-bottom: 30px; }}
        .sla-card {{ background: #fff; border: 1px solid var(--gray-200); border-radius: 8px; padding: 20px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
        .sla-card.main {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); color: white; border: none; }}
        
        .sla-val {{ font-size: 42px; font-weight: 800; line-height: 1; margin-bottom: 5px; }}
        .sla-lbl {{ font-size: 12px; opacity: 0.8; text-transform: uppercase; letter-spacing: 1px; }}
        .sla-sub {{ font-size: 12px; margin-top: 5px; opacity: 0.7; }}
        
        .score-green {{ color: var(--success); }} .score-yellow {{ color: var(--warning); }} .score-red {{ color: var(--danger); }}
        .main .sla-val {{ color: #fff; }}
        
        /* --- 链路矩阵 --- */
        .section-title {{ font-size: 16px; font-weight: 700; margin-bottom: 15px; display: flex; align-items: center; gap: 8px; }}
        .link-matrix {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; margin-bottom: 30px; }}
        .link-card {{ border: 1px solid var(--gray-200); border-radius: 8px; overflow: hidden; }}
        .link-header {{ padding: 12px 15px; background: var(--gray-50); border-bottom: 1px solid var(--gray-200); display: flex; justify-content: space-between; align-items: center; }}
        .link-name {{ font-weight: 700; font-size: 15px; }}
        .link-score {{ font-weight: 800; font-size: 18px; }}
        
        .link-body {{ padding: 15px; }}
        .metric-row {{ display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 13px; }}
        .metric-label {{ color: var(--gray-600); }}
        .metric-val {{ font-weight: 600; font-family: monospace; }}
        
        .status-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }}
        .dot-green {{ background: var(--success); }} .dot-yellow {{ background: var(--warning); }} .dot-red {{ background: var(--danger); }}
        
        /* --- 行业对标表格 --- */
        .benchmark-table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; font-size: 13px; }}
        .benchmark-table th {{ text-align: left; padding: 12px; background: var(--gray-50); border-bottom: 2px solid var(--gray-200); color: var(--gray-600); font-weight: 600; }}
        .benchmark-table td {{ padding: 12px; border-bottom: 1px solid var(--gray-100); }}
        .benchmark-table tr:last-child td {{ border-bottom: none; }}
        
        /* --- 建议面板 --- */
        .rec-panel {{ background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 20px; }}
        .rec-item {{ display: flex; gap: 10px; margin-bottom: 10px; font-size: 14px; color: #0c4a6e; }}
        .rec-icon {{ color: #0284c7; }}
        
        .footer {{ text-align: center; font-size: 12px; color: #9ca3af; margin-top: 40px; }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 1. 头部 -->
        <div class="header">
            <div class="title-group">
                <h1>瑞斯康达跨境FAQ--跨境链路SLA测试报告 <span class="badge-intl">🌍 Cross-Border</span></h1>
                <p>ID: {report_id} | 测试时长: {test_duration:.1f}s | 时间: {timestamp}</p>
            </div>
        </div>

        <!-- 2. SLA 仪表盘 -->
        <div class="sla-dashboard">
            <div class="sla-card main">
                <div class="sla-val" style="color: {score_color}">{overall_score:.0f}</div>
                <div class="sla-lbl">综合健康分</div>
                <div class="sla-sub">基于延迟/丢包/抖动加权</div>
            </div>
            <div class="sla-card">
                <div class="sla-val {'score-green' if latency_score>=80 else 'score-yellow' if latency_score>=60 else 'score-red'}">{latency_score:.0f}</div>
                <div class="sla-lbl">延迟得分</div>
                <div class="sla-sub">Avg: {avg_latency:.1f}ms</div>
            </div>
            <div class="sla-card">
                <div class="sla-val {'score-green' if loss_score>=80 else 'score-yellow' if loss_score>=60 else 'score-red'}">{loss_score:.0f}</div>
                <div class="sla-lbl">丢包得分</div>
                <div class="sla-sub">Avg: {avg_loss:.2f}%</div>
            </div>
            <div class="sla-card">
                <div class="sla-val {'score-green' if jitter_score>=80 else 'score-yellow' if jitter_score>=60 else 'score-red'}">{jitter_score:.0f}</div>
                <div class="sla-lbl">稳定性得分</div>
                <div class="sla-sub">Jitter: {avg_jitter:.1f}ms</div>
            </div>
        </div>

        <!-- 3. 链路质量矩阵 -->
        <div class="section-title">📊 链路质量对比矩阵</div>
        <div class="link-matrix">
            {links_matrix_html}
        </div>

        <!-- 4. 深度诊断洞察 (Deep Dive) -->
        <div class="section-title">🔍 深度诊断洞察 (Deep Dive)</div>
        {deep_dive_html}

        <!-- 5. 行业对标 -->
        {link_sla_html}

        <!-- 6. 优化建议 -->
        <div class="section-title">💡 SD-WAN 优化建议</div>
        <div class="rec-panel">
            {recommendations_html}
        </div>

        <div class="footer">Generated by SD-WAN Intelligent Analyzer v1.2 | Confidential</div>
    </div>
</body>
</html>
'''

def _generate_deep_dive_section(mtu_results, google_dns_ok, dns_comparison_list, dns_target_domain="www.google.com", gateway_dns_ip="N/A") -> str:
    """生成深度诊断板块 HTML (支持三源 DNS 对比)"""
    
    # 1. MTU 部分 (保持原有逻辑)
    mtu_html = ''
    if mtu_results:
        mtu_rows = ''
        for m in mtu_results:
            target = m.get('target', 'N/A')
            mtu_val = m.get('mtu', 0)
            status_text = m.get('status', 'Unknown')
            
            if '正常' in status_text:
                status_display = '<span style="color:var(--success)">✅ 正常</span>'
            elif '偏低' in status_text:
                status_display = '<span style="color:var(--warning)">⚠️ 偏低</span>'
            elif '不可达' in status_text:
                status_display = '<span style="color:var(--gray-400)">⚪ 不可达</span>'
            else:
                status_display = '<span style="color:var(--danger)">❌ 异常</span>'
            
            mtu_rows += f'<tr><td>{target}</td><td>{mtu_val} Bytes</td><td>{status_display}</td></tr>'
        
        mtu_html = f'''
        <div class="panel">
            <div class="panel-head">📏 MTU 路径探测</div>
            <div class="panel-body" style="padding:0;">
                <table class="benchmark-table" style="margin-bottom:0;">
                    <thead><tr><th>目标</th><th>最佳 MTU</th><th>状态</th></tr></thead>
                    <tbody>{mtu_rows}</tbody>
                </table>
            </div>
        </div>
        '''
    else:
        mtu_html = '<div class="panel"><div class="panel-head">📏 MTU 路径探测</div><div class="panel-body"><p style="color:#999;text-align:center">未执行 MTU 探测</p></div></div>'

    # 2. DNS 综合诊断面板 (升级为三源对比)
    dns_status_badge = '<span class="badge b-green">连通</span>' if google_dns_ok else '<span class="badge b-red">不可达</span>'
    dns_hint = "基础网络可达性正常" if google_dns_ok else "国际出口可能受阻或存在 ICMP 拦截"
    
    # 构建 DNS 对比表格行
    dns_table_rows = ''
    if dns_comparison_list:
        for d in dns_comparison_list:
            # 提取三源数据
            gw_ips = d.get("ip_local", [])
            sys_ips = d.get("ip_system", []) # 新增：系统DNS结果
            pub_ips = d.get("ip_public", [])
            
            # 格式化 IP 显示
            gw_ip_str = ", ".join(gw_ips) if isinstance(gw_ips, list) and gw_ips else "-"
            sys_ip_str = ", ".join(sys_ips) if isinstance(sys_ips, list) and sys_ips else "-"
            pub_ip_str = ", ".join(pub_ips) if isinstance(pub_ips, list) and pub_ips else "-"
            
            # 状态图标
            gw_status_icon = "✅" if d.get('status_local') == 'success' else "❌"
            sys_status_icon = "✅" if d.get('status_system') == 'success' else "❌" # 新增
            pub_status_icon = "✅" if d.get('status_public') == 'success' else "❌"
            
            # 对比结论
            comparison_note = d.get("note", "未对比")
            if not comparison_note:
                # 简单兜底逻辑
                if d.get('status_public') == 'success':
                    comparison_note = "以公共DNS为基准对比完成"
                else:
                    comparison_note = "公共DNS解析失败，无法对比"

            # 获取具体的 DNS 服务器地址
            server_local = d.get("server_local", gateway_dns_ip)
            server_system = d.get("server_system", "System Default") # 新增
            server_public = d.get("server_public", "8.8.8.8")

            # --- 第一行：网关 DNS ---
            dns_table_rows += f'''
            <tr>
                <td style="font-weight:600; color:var(--gray-600)">{server_local}<br><span style="font-size:11px;color:#999">(默认网关)</span></td>
                <td>{gw_status_icon} {d.get("status_local", "")}</td>
                <td style="font-family:monospace; font-size:12px; word-break:break-all;">{gw_ip_str}</td>
                <td rowspan="3" style="vertical-align:middle; font-size:12px; color:#666; border-left:1px solid #eee; background:#f9fafb;">
                    <div style="font-weight:600; margin-bottom:4px;">深度分析:</div>
                    {comparison_note}
                </td>
            </tr>
            '''
            
            # --- 第二行：系统默认 DNS (新增) ---
            dns_table_rows += f'''
            <tr>
                <td style="font-weight:600; color:var(--gray-600)">{server_system}<br><span style="font-size:11px;color:#999">(系统配置)</span></td>
                <td>{sys_status_icon} {d.get("status_system", "")}</td>
                <td style="font-family:monospace; font-size:12px; word-break:break-all;">{sys_ip_str}</td>
            </tr>
            '''

            # --- 第三行：公共 DNS ---
            dns_table_rows += f'''
            <tr>
                <td style="font-weight:600; color:var(--gray-600)">{server_public}<br><span style="font-size:11px;color:#999">(公共参考)</span></td>
                <td>{pub_status_icon} {d.get("status_public", "")}</td>
                <td style="font-family:monospace; font-size:12px; word-break:break-all;">{pub_ip_str}</td>
            </tr>
            '''
    else:
        dns_table_rows = '<tr><td colspan="4" style="text-align:center;color:#999;">无 DNS 对比数据</td></tr>'

    # 组合 DNS 面板
    dns_panel_html = f'''
    <div class="panel">
        <div class="panel-head">
            <span>⚖️ DNS 解析深度对比 (三源)</span>
            <span style="float:right; font-size:12px; font-weight:normal; color:var(--gray-600)">
                测试域名: <strong>{dns_target_domain}</strong>
            </span>
        </div>
        <div class="panel-body">
            <!-- 顶部：Google DNS 连通性概览 -->
            <div style="display:flex; justify-content:space-between; align-items:center; background:#f0f9ff; padding:10px 15px; border-radius:6px; margin-bottom:15px; border:1px solid #bae6fd;">
                <div>
                    <div style="font-size:12px; color:#0369a1; font-weight:600;">🌐 Google DNS (8.8.8.8) 基础连通性</div>
                    <div style="font-size:12px; color:#0c4a6e; margin-top:2px;">{dns_hint}</div>
                </div>
                <div>{dns_status_badge}</div>
            </div>

            <!-- 下部：详细对比表格 -->
            <table class="benchmark-table" style="margin-bottom:0;">
                <thead>
                    <tr>
                        <th style="width:25%">DNS 服务器来源</th>
                        <th style="width:15%">解析状态</th>
                        <th style="width:35%">解析 IP 地址</th>
                        <th style="width:25%">对比结论</th>
                    </tr>
                </thead>
                <tbody>
                    {dns_table_rows}
                </tbody>
            </table>
        </div>
    </div>
    '''

    return f'''
    <div style="display:grid; gap:20px;">
        {mtu_html}
        {dns_panel_html}
    </div>
    '''

def _generate_links_matrix(link_results: list) -> str:
    """生成链路卡片矩阵"""
    if not link_results:
        return '<div style="grid-column: 1/-1; text-align:center; color:#999; padding:20px;">无链路测试数据</div>'
    
    html = ''
    for link in link_results:
        name = getattr(link, 'link_name', getattr(link, 'target', 'Unknown Link'))
        target = getattr(link, 'target', '')
        latency = getattr(link, 'avg_latency', 0)
        loss = getattr(link, 'packet_loss', 0)
        jitter = getattr(link, 'jitter', 0)
        score = getattr(link, 'stability_score', 0)
        
        # 状态颜色
        if score >= 80: color_cls = "dot-green"; score_cls = "score-green"
        elif score >= 60: color_cls = "dot-yellow"; score_cls = "score-yellow"
        else: color_cls = "dot-red"; score_cls = "score-red"
        
        html += f'''
        <div class="link-card">
            <div class="link-header">
                <div>
                    <span class="status-dot {color_cls}"></span>
                    <span class="link-name">{name}</span>
                </div>
                <span class="link-score {score_cls}">{score:.0f}</span>
            </div>
            <div class="link-body">
                <div class="metric-row">
                    <span class="metric-label">目标</span>
                    <span class="metric-val">{target}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">平均延迟</span>
                    <span class="metric-val {'score-red' if latency>300 else 'score-yellow' if latency>200 else ''}">{latency:.1f} ms</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">丢包率</span>
                    <span class="metric-val {'score-red' if loss>2 else 'score-yellow' if loss>0.5 else ''}">{loss:.2f} %</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">网络抖动</span>
                    <span class="metric-val">{jitter:.1f} ms</span>
                </div>
            </div>
        </div>
        '''
    return html

def _generate_link_sla_table(link_results: list) -> str:
    """
    生成各链路独立 SLA 达标详情表
    替代原有的平均值对标，确保每条业务链路都被独立评估
    """
    if not link_results:
        return '<p style="text-align:center; color:#999;">无链路数据</p>'

    rows_html = ""
    for link in link_results:
        target = getattr(link, 'target', 'Unknown')
        lat = getattr(link, 'avg_latency', 0)
        loss = getattr(link, 'packet_loss', 0)
        jitter = getattr(link, 'jitter', 0)
        score = getattr(link, 'stability_score', 0)

        # --- 初始化变量，防止 UnboundLocalError ---
        lat_class = "" 
        lat_status = ""
        loss_status = ""
        overall_verdict = ""
        score_color = "#999" # 默认灰色

        # --- 单项指标判定逻辑 (可根据实际 SLA 要求调整阈值) ---
        
        # 1. 延迟判定 & 2. 丢包判定 (联合判断不可达)
        # 如果丢包100% 或者 延迟大于 5000ms (我们设定的不可达阈值)，则视为不可达
        is_unreachable = (loss >= 100.0) or (lat > 5000) or (score == 0 and loss > 90)
        
        if is_unreachable:
            # 不可达状态
            # lat_display 变量在此处未使用，可移除或保留用于调试
            lat_status = '<span class="badge b-red">失败</span>'
            # loss_display 变量在此处未使用，可移除或保留用于调试
            loss_status = '<span class="badge b-red">严重</span>'
            # jitter_display 变量在此处未使用，可移除或保留用于调试
            overall_verdict = '<span style="color:#ef4444; font-weight:bold; font-size:14px;">❌ 链路中断</span>'
            lat_class = "text-red" # 确保延迟文字也是红色
            score_color = "#ef4444"
        else:
            if lat < 150:
                lat_status = '<span class="badge b-green">优秀</span>'
                lat_class = "text-green"
            elif lat < 300:
                lat_status = '<span class="badge b-yellow">合格</span>'
                lat_class = "text-yellow"
            else:
                lat_status = '<span class="badge b-red">超标</span>'
                lat_class = "text-red"

            # 2. 丢包判定 (<1% 优秀, <3% 合格, >3% 严重)
            if loss < 1:
                loss_status = '<span class="badge b-green">正常</span>'
            elif loss < 3:
                loss_status = '<span class="badge b-yellow">轻微</span>'
            else:
                loss_status = '<span class="badge b-red">严重</span>'

            # 3. 综合 SLA 结论
            if score >= 80:
                overall_verdict = '<span style="color:#10b981; font-weight:bold;">✅ 达标</span>'
                score_color = "#10b981"
            elif score >= 60:
                overall_verdict = '<span style="color:#f59e0b; font-weight:bold;">⚠️ 临界</span>'
                score_color = "#f59e0b"
            else:
                overall_verdict = '<span style="color:#ef4444; font-weight:bold;">❌ 不达标</span>'
                score_color = "#ef4444"
                
        rows_html += f'''
        <tr>
            <td><strong>{target}</strong></td>
            <td class="{lat_class}">{lat:.1f} ms</td>
            <td>{lat_status}</td>
            <td>{loss:.2f} %</td>
            <td>{loss_status}</td>
            <td>{jitter:.1f} ms</td>
            <td>{overall_verdict}</td>
        </tr>
        '''

    return f'''
    <div class="section-title">📋 各业务链路 SLA 达标详情</div>
    <div style="margin-bottom: 10px; font-size: 13px; color: #666;">
        说明：以下针对每条独立链路进行 SLA 合规性检查，而非整体平均。
    </div>
    <table class="benchmark-table">
        <thead>
            <tr>
                <th style="width: 20%">业务目标</th>
                <th style="width: 12%">平均延迟</th>
                <th style="width: 12%">延迟评级</th>
                <th style="width: 12%">丢包率</th>
                <th style="width: 12%">丢包评级</th>
                <th style="width: 12%">网络抖动</th>
                <th style="width: 20%">SLA 结论</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    '''

# 保留原函数名以便兼容，但内部调用新逻辑，或者直接删除原函数并在模板中改用新函数
def _generate_benchmark_table(avg_lat, avg_loss, overall_score) -> str:
    """
    兼容旧接口，但建议直接在 generate_cross_border_html_report 中调用 _generate_link_sla_table
    此处返回空或提示，避免混淆
    """
    return "<!-- 已迁移至独立链路 SLA 表 -->"

def _generate_cross_border_recommendations_html(link_results: list, overall_score: float) -> str:
    """生成跨境优化建议"""
    recs = []
    
    if not link_results:
        return '<div class="rec-item"><span class="rec-icon">ℹ️</span> 无足够数据进行建议</div>'
        
    avg_lat = sum(getattr(l, 'avg_latency', 0) for l in link_results) / len(link_results)
    avg_loss = sum(getattr(l, 'packet_loss', 0) for l in link_results) / len(link_results)
    
    if avg_lat > 300:
        recs.append("🚀 <strong>延迟过高</strong>：建议启用 SD-WAN 智能选路，优先选择延迟较低的 POP 点接入。")
    elif avg_lat > 200:
        recs.append("⚡ <strong>延迟中等</strong>：建议开启 TCP 加速或协议优化功能，提升应用层响应速度。")
        
    if avg_loss > 0.5:
        recs.append("📉 <strong>轻微丢包</strong>：建议监控链路波动，考虑配置多链路负载分担以降低单链路压力。")
        
    if overall_score >= 85:
        recs.append("✅ <strong>链路质量优秀</strong>：当前配置符合核心业务要求，建议保持定期监控。")
    elif overall_score < 60:
        recs.append("⚠️ <strong>质量较差</strong>：建议检查物理线路质量，或联系运营商排查跨境拥塞情况。")
        
    recs.append("📊 <strong>基线建立</strong>：建议每周执行一次跨境测试，建立性能基线以便及时发现劣化。")
    
    html = ''
    for rec in recs:
        html += f'<div class="rec-item"><span class="rec-icon">➤</span> {rec}</div>'
    return html


def export_cross_border_html_report(report: FinalReport, cross_border_result, path: str = None):
    """导出跨境链路专项测试HTML格式报告"""
    
    if path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"瑞斯康达跨境FAQ--跨境链路SLA测试报告_{timestamp}.html"
        path = os.path.join(REPORT_DIR, filename)
    
    html_content = generate_cross_border_html_report(report, cross_border_result)
    
    try:
        # 确保目录存在
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"跨境链路HTML报告已保存至: {path}")
        return True
    except Exception as e:
        print(f"跨境链路HTML报告保存失败: {e}")
        return False