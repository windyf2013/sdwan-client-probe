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
    
    print(f"\n[REPORT_DEBUG] [L14] export_html_report函数开始执行")
    print(f"[REPORT_DEBUG] [L15] 传入参数: report类型={type(report)}, path={path}")
    
    # 第一节: 处理路径参数
    print(f"[REPORT_DEBUG] [L17-20] 开始处理路径参数")
    if path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"SDWAN_Report_{timestamp}.html"
        path = os.path.join(REPORT_DIR, filename)
        print(f"[REPORT_DEBUG] [L19-20] 自动生成路径: filename={filename}")
    print(f"[REPORT_DEBUG] [L17-20] 最终路径: {path}")
    
    # 第二节: 生成HTML内容
    print(f"[REPORT_DEBUG] [L22] 开始调用generate_commercial_html_report")
    html_content = generate_commercial_html_report(report)
    print(f"[REPORT_DEBUG] [L22] HTML内容生成完成, 长度={len(html_content)}字符")
    
    # 第三节: 文件保存过程
    print(f"[REPORT_DEBUG] [L24-35] 开始文件保存流程")
    try:
        # 确保目录存在
        print(f"[REPORT_DEBUG] [L26-27] 检查目录是否存在: {os.path.dirname(path)}")
        if not os.path.exists(os.path.dirname(path)):
            print(f"[REPORT_DEBUG] [L27] 目录不存在, 开始创建")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            print(f"[REPORT_DEBUG] [L27] 目录创建成功")
        else:
            print(f"[REPORT_DEBUG] [L26] 目录已存在")
        
        # 写入文件
        print(f"[REPORT_DEBUG] [L29-31] 开始写入HTML文件到: {path}")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"[REPORT_DEBUG] [L31] 文件写入成功")
        print(f"HTML报告已保存至: {path}")
        
        print(f"[REPORT_DEBUG] [L32] 函数执行成功, 返回True")
        return True
        
    except Exception as e:
        print(f"[REPORT_DEBUG] [L33-35] 捕获到异常")
        print(f"[REPORT_DEBUG] [L34] 异常类型: {type(e).__name__}")
        print(f"[REPORT_DEBUG] [L34] 异常详情: {e}")
        print(f"[REPORT_DEBUG] [L35] 函数执行失败, 返回False")
        print(f"HTML报告保存失败: {e}")
        return False

def generate_commercial_html_report(report: FinalReport) -> str:
    """生成商用级HTML格式报告 - SDWAN运维分析师视角"""
    
    # 报告基本信息
    report_id = getattr(report, 'report_id', 'N/A')
    timestamp = getattr(report, 'timestamp', 'N/A')
    overall_score = getattr(report, 'overall_score', 0)
    environment_score = getattr(report, 'environment_score', 0)
    connectivity_score = getattr(report, 'connectivity_score', 0)
    conclusion = getattr(report, 'conclusion', '')
    
    # 系统信息
    system = getattr(report, 'system', {})
    app_probes = getattr(report, 'app_probes', [])
    issues = getattr(report, 'issues', [])
    recommendations = getattr(report, 'recommendations', [])
    
    # HTML报告模板（商用级完整格式）
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SD-WAN终端环境深度分析报告 - {report_id}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Microsoft YaHei', 'PingFang SC', 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); min-height: 100vh; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 30px; }}
        .document-header {{ background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); color: white; padding: 40px; border-radius: 12px; margin-bottom: 30px; box-shadow: 0 8px 25px rgba(0,0,0,0.15); }}
        .document-header h1 {{ font-size: 34px; margin-bottom: 15px; font-weight: 300; }}
        .document-subtitle {{ font-size: 18px; opacity: 0.9; margin-bottom: 5px; }}
        .score-panel {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 25px; margin-bottom: 30px; }}
        .score-card {{ background: white; padding: 30px; border-radius: 12px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.1); transition: transform 0.3s ease; }}
        .score-card:hover {{ transform: translateY(-5px); }}
        .score-card.overall {{ background: linear-gradient(135deg, #667eea, #764ba2); color: white; }}
        .score-card.environment {{ background: linear-gradient(135deg, #4CAF50, #45a049); color: white; }}
        .score-card.connectivity {{ background: linear-gradient(135deg, #2196F3, #1976D2); color: white; }}
        .score-value {{ font-size: 48px; font-weight: 700; margin: 15px 0; text-shadow: 0 2px 4px rgba(0,0,0,0.2); }}
        .score-progress {{ width: 100%; height: 8px; background: rgba(255,255,255,0.3); border-radius: 4px; margin: 15px 0; overflow: hidden; }}
        .score-progress-fill {{ height: 100%; background: rgba(255,255,255,0.8); transition: width 1s ease; }}
        .score-label {{ font-size: 16px; opacity: 0.95; letter-spacing: 1px; }}
        .score-desc {{ font-size: 13px; opacity: 0.8; margin-top: 10px; }}
        .section {{ background: white; padding: 35px; border-radius: 12px; margin-bottom: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-left: 5px solid #667eea; }}
        .section h2 {{ color: #2c3e50; font-size: 24px; border-bottom: 2px solid #ecf0f1; padding-bottom: 15px; margin-bottom: 25px; display: flex; align-items: center; }}
        .section h2:before {{ content: "▌"; margin-right: 10px; color: #667eea; }}
        table {{ width: 100%; border-collapse: separate; border-spacing: 0; margin: 20px 0; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }}
        th, td {{ border: none; padding: 18px 15px; text-align: left; }}
        th {{ background: linear-gradient(135deg, #ecf0f1, #dfe6e9); font-weight: 600; color: #2c3e50; font-size: 15px; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        tr:hover {{ background: #e3f2fd; transition: background 0.3s; }}
        .status-indicator {{ display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; }}
        .status-success {{ color: #27ae60; font-weight: 600; }}
        .status-warning {{ color: #f39c12; font-weight: 600; }}
        .status-error {{ color: #e74c3c; font-weight: 600; }}
        .metric-badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; margin-left: 10px; }}
        .metric-excellent {{ background: #e8f5e8; color: #27ae60; }}
        .metric-good {{ background: #e3f2fd; color: #1976d2; }}
        .metric-fair {{ background: #fff3e0; color: #f57c00; }}
        .metric-poor {{ background: #ffebee; color: #d32f2f; }}
        .conclusion-panel {{ background: linear-gradient(135deg, #667eea18, #764ba218); padding: 30px; border-radius: 12px; border-left: 5px solid #667eea; margin: 25px 0; }}
        .conclusion-title {{ font-size: 20px; font-weight: 600; color: #2c3e50; margin-bottom: 15px; }}
        .recommendation-item {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #667eea; }}
        .timestamp {{ color: #7f8c8d; font-size: 13px; margin-top: 5px; }}
        .footer {{ text-align: center; padding: 30px; color: #7f8c8d; font-size: 13px; border-top: 1px solid #ecf0f1; margin-top: 40px; }}
        .print-only {{ display: none; }}
        @media print {{
            .score-card:hover {{ transform: none; }}
            .print-only {{ display: block; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 报告头信息 -->
        <div class="document-header">
            <h1>SD-WAN终端环境深度分析报告</h1>
            <div class="document-subtitle">报告编号: {report_id} | 生成时间: {timestamp}</div>
            <div class="document-subtitle">检测范围: 系统环境 + 网络连通性 + 应用可达性</div>
        </div>

        <!-- 综合评分面板 -->
        <div class="score-panel">
            <div class="score-card overall">
                <div class="score-label">综合健康评分</div>
                <div class="score-value">{overall_score:.1f}/100</div>
                <div class="score-progress">
                    <div class="score-progress-fill" style="width: {overall_score}%;"></div>
                </div>
                <div class="score-desc">终端环境整体健康度评估</div>
            </div>
            <div class="score-card environment">
                <div class="score-label">系统环境评分</div>
                <div class="score-value">{environment_score:.1f}/100</div>
                <div class="score-progress">
                    <div class="score-progress-fill" style="width: {environment_score}%;"></div>
                </div>
                <div class="score-desc">操作系统、网络配置等基础环境</div>
            </div>
            <div class="score-card connectivity">
                <div class="score-label">网络连通性评分</div>
                <div class="score-value">{connectivity_score:.1f}/100</div>
                <div class="score-progress">
                    <div class="score-progress-fill" style="width: {connectivity_score}%;"></div>
                </div>
                <div class="score-desc">网络链路质量与可达性</div>
            </div>
        </div>

        <!-- 执行摘要 -->
        <div class="section">
            <h2>执行摘要</h2>
            <div class="conclusion-panel">
                <div class="conclusion-title">核心评估结果</div>
                <p style="font-size: 16px; line-height: 1.8;">{conclusion}</p>
                <div class="timestamp">评估基准: IT运维最佳实践 | SD-WAN部署标准</div>
            </div>
        </div>

        <!-- 详细检测结果 -->
        <div class="section">
            <h2>详细检测结果</h2>
            
            <!-- 系统环境检测结果 -->
            <h3 style="color: #4CAF50; margin: 25px 0 15px 0;">📊 系统环境检测</h3>
            {_generate_detailed_system_info_html(system)}
            
            <!-- 应用可达性检测 -->
            <h3 style="color: #2196F3; margin: 25px 0 15px 0;">🌐 应用可达性检测</h3>
            {_generate_detailed_app_probes_html(app_probes)}
            
            <!-- 问题诊断报告 -->
            {_generate_detailed_issues_html(issues)}
        </div>

        <!-- 优化建议与行动项 -->
        <div class="section">
            <h2>优化建议与行动项</h2>
            {_generate_recommendations_html(recommendations, overall_score)}
        </div>

        <!-- 技术指标参考 -->
        <div class="section">
            <h2>技术指标参考</h2>
            <table>
                <thead>
                    <tr>
                        <th>指标类别</th>
                        <th>评估标准</th>
                        <th>当前状态</th>
                        <th>行业基准</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>综合健康度</td>
                        <td>系统环境 + 网络连通性综合评分</td>
                        <td><span class="{'status-success' if overall_score >= 80 else 'status-warning' if overall_score >= 60 else 'status-error'}">{overall_score:.1f}/100</span></td>
                        <td>≥80 (优秀) | 60-80 (良好) | &lt;60 (需优化)</td>
                    </tr>
                    <tr>
                        <td>网络连通性</td>
                        <td>网关、DNS、关键应用可达性</td>
                        <td><span class="{'status-success' if connectivity_score >= 85 else 'status-warning' if connectivity_score >= 70 else 'status-error'}">{connectivity_score:.1f}/100</span></td>
                        <td>≥85 (优秀) | 70-85 (良好) | &lt;70 (需优化)</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- 报告尾部 -->
        <div class="footer">
            <p>📄 报告生成: SD-WAN智能分析平台 v1.2 | 🕐 生成时间: {timestamp}</p>
            <p>🔒 报告编号: {report_id} | 📧 技术支持: network-support@example.com</p>
            <p class="print-only">--- 文档结束 ---</p>
        </div>
    </div>
</body>
</html>
'''

def _generate_system_info_html(system: dict) -> str:
    """生成系统环境信息的HTML表格"""
    if not system:
        return "<p>系统环境信息不可用</p>"
    
    html = "<p>系统环境信息详情请看终端输出</p>"
    
    # 简化的系统信息展示
    if hasattr(system, 'interfaces'):
        interfaces = getattr(system, 'interfaces', [])
        if interfaces:
            html += '<h3>网络接口数量: {}</h3>'.format(len(interfaces))
    
    return html

def _generate_detailed_system_info_html(system) -> str:
    """生成详细的系统环境信息HTML - 商用级标准"""
    if not system:
        return '<p style="color: #7f8c8d; font-style: italic; padding: 20px; text-align: center;">❌ 系统环境检测数据未收集</p>'
    
    html = '''
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 20px 0;">
    '''
    
    # 兼容字典和数据类对象的访问方式
    def get_value(obj, key, default=None):
        """通用值获取函数，支持字典和数据类对象"""
        if isinstance(obj, dict):
            return obj.get(key, default)
        else:
            return getattr(obj, key, default)
    
    # 网络接口信息 - 适用于SystemEnvironmentResult对象
    interfaces = get_value(system, 'interfaces', [])
    proxy_enabled = get_value(system, 'proxy_enabled', False)
    proxy_server = get_value(system, 'proxy_server', '')
    firewall_enabled = get_value(system, 'firewall_enabled', False)
    
    # 网络配置信息卡
    if interfaces:
        primary_interface = get_value(system, 'primary_interface')
        html += f'''
        <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
            <h4 style="color: #2c3e50; margin-bottom: 15px; display: flex; align-items: center;">
                <span style="background: #3498db; color: white; width: 24px; height: 24px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-right: 10px; font-size: 12px;">🌐</span>
                网络接口配置
            </h4>
            <div style="line-height: 1.8;">
        '''
        
        for interface in interfaces:
            interface_name = get_value(interface, 'name', '未知接口')
            interface_desc = get_value(interface, 'description', '')
            ip_addresses = ', '.join(get_value(interface, 'ip_addresses', [])) or 'N/A'
            gateways = ', '.join(get_value(interface, 'gateways', [])) or 'N/A'
            dns_servers = ', '.join(get_value(interface, 'dns_servers', [])) or 'N/A'
            is_primary = get_value(interface, 'is_primary', False)
            
            primary_marker = " (主网卡)" if is_primary else ""
            html += f'''
                <div style="border-bottom: 1px solid #f0f0f0; padding: 10px 0;">
                    <div><strong>{interface_name}{primary_marker}:</strong> {interface_desc}</div>
                    <div style="font-size: 13px; color: #666; margin-left: 15px;">
                        <div>IP地址: <span style="font-family: monospace;">{ip_addresses}</span></div>
                        <div>网关: <span style="font-family: monospace;">{gateways}</span></div>
                        <div>DNS: <span style="font-family: monospace;">{dns_servers}</span></div>
                    </div>
                </div>
            '''
        
        html += '''
            </div>
        </div>
        '''
    
    # 系统配置信息卡
    config_has_data = proxy_enabled or firewall_enabled
    if config_has_data:
        html += f'''
        <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
            <h4 style="color: #2c3e50; margin-bottom: 15px; display: flex; align-items: center;">
                <span style="background: #e74c3c; color: white; width: 24px; height: 24px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-right: 10px; font-size: 12px;">🔧</span>
                系统配置状态
            </h4>
            <div style="line-height: 1.8;">
                <div><strong>代理设置:</strong> {'已启用' if proxy_enabled else '未启用'} {proxy_server if proxy_server else ''}</div>
                <div><strong>防火墙:</strong> {'已启用' if firewall_enabled else '未启用'}</div>
        '''
        
        # 添加连通性状态（如果存在）
        default_route_exists = get_value(system, 'default_route_exists', False)
        gateway_reachable = get_value(system, 'gateway_reachable', False)
        dns_resolution_working = get_value(system, 'dns_resolution_working', False)
        
        html += f'''
                <div><strong>默认路由:</strong> {'正常' if default_route_exists else '异常'}</div>
                <div><strong>网关可达性:</strong> {'正常' if gateway_reachable else '异常'}</div>
                <div><strong>DNS解析:</strong> {'正常' if dns_resolution_working else '异常'}</div>
        '''
        
        html += '''
            </div>
        </div>
        '''
    
    # 兼容旧版本的字典结构（如果有额外的网络信息）
    if isinstance(system, dict):
        network_info = system.get('network_info', {})
        if network_info:
            html += f'''
            <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
                <h4 style="color: #2c3e50; margin-bottom: 15px; display: flex; align-items: center;">
                    <span style="background: #9b59b6; color: white; width: 24px; height: 24px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-right: 10px; font-size: 12px;">📡</span>
                    网络基础信息
                </h4>
                <div style="line-height: 1.8;">
                    <div><strong>本地IP:</strong> <span style="font-family: monospace;">{network_info.get('local_ip', 'N/A')}</span></div>
                    <div><strong>网关IP:</strong> <span style="font-family: monospace;">{network_info.get('gateway_ip', 'N/A')}</span></div>
                    <div><strong>DNS服务器:</strong> {', '.join(network_info.get('dns_servers', [])) or 'N/A'}</div>
                </div>
            </div>
            '''
    
    html += '</div>'
    
    # 如果没有任何数据
    if not any([interfaces, config_has_data]):
        html = '<p style="color: #7f8c8d; font-style: italic; padding: 20px; text-align: center;">📊 系统环境检测数据正在收集...</p>'
    
    return html

def _generate_detailed_app_probes_html(app_probes: list) -> str:
    """生成详细的应用可达性检测HTML - 商用级标准"""
    if not app_probes:
        return '<p style="color: #7f8c8d; font-style: italic; padding: 20px; text-align: center;">🌐 应用可达性检测未执行</p>'
    
    def get_probe_value(probe, key, default=None):
        """通用值获取函数，支持字典和AppProbeResult数据类对象"""
        if isinstance(probe, dict):
            return probe.get(key, default)
        else:
            return getattr(probe, key, default)
    
    total_probes = len(app_probes)
    successful_probes = sum(1 for probe in app_probes if get_probe_value(probe, "ping_reachable", False) or 
                                                   get_probe_value(probe, "tcp_open", False) or 
                                                   get_probe_value(probe, "http_available", False))
    success_rate = (successful_probes / total_probes) * 100 if total_probes > 0 else 0
    
    html = f'''
    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 25px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <strong>检测摘要</strong>
                <div style="color: #666; font-size: 14px; margin-top: 5px;">共检测 {total_probes} 个关键业务应用</div>
            </div>
            <div style="text-align: right;">
                <div class="{'status-success' if success_rate >= 90 else 'status-warning' if success_rate >= 70 else 'status-error'}" style="font-size: 18px; font-weight: bold;">
                    {success_rate:.1f}% 可用性
                </div>
                <div style="color: #666; font-size: 12px;">{successful_probes}/{total_probes} 应用正常</div>
            </div>
        </div>
    </div>
    
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 15px;">
    '''
    
    for probe in app_probes:
        target = get_probe_value(probe, "target", "未知应用")
        
        # 多种状态检测：ping可达性或TCP端口开放或HTTP可用
        ping_status = get_probe_value(probe, "ping_reachable", False)
        tcp_status = get_probe_value(probe, "tcp_open", False)
        http_status = get_probe_value(probe, "http_available", False)
        
        # 综合状态：任一检测方式成功都算正常
        status = ping_status or tcp_status or http_status
        tcp_port = get_probe_value(probe, "tcp_port", 0)
        
        # 确定检测方式描述
        method_type = ""
        if http_status:
            method_type = "HTTP访问"
        elif tcp_status:
            method_type = f"TCP端口{tcp_port}"
        elif ping_status:
            method_type = "Ping"
        else:
            method_type = "网络连通"
            
        # 尝试获取描述，如果没有则生成默认描述
        description = get_probe_value(probe, "description", "")
        if not description:
            description = f"{method_type}检测 - 关键业务应用"
            
        status_color = "#27ae60" if status else "#e74c3c"
        status_icon = "✅" if status else "❌"
        status_text = "正常" if status else "异常"
        
        html += f'''
        <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; background: white; border-left: 4px solid {status_color};">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                <div style="flex: 1;">
                    <div style="font-weight: 600; font-size: 16px; color: #2c3e50;">{target}</div>
                    <div style="color: #7f8c8d; font-size: 13px; margin-top: 5px;">{description}</div>
                </div>
                <div style="text-align: right;">
                    <span style="font-size: 20px; margin-right: 5px;">{status_icon}</span>
                    <span class="{'status-success' if status else 'status-error'}" style="font-weight: 600;">{status_text}</span>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 15px; font-size: 13px;">
                <div><strong>检测方式:</strong> {method_type}</div>
                <div><strong>详情状态:</strong> {f"Ping:{ping_status}" if ping_status else f"TCP端口{tcp_port}:{tcp_status}" if tcp_status else f"HTTP: {http_status}" if http_status else "多种检测失败"}</div>
            </div>
        </div>
        '''
    
    html += '</div>'
    
    # 可用性评级
    availability_class = "metric-excellent" if success_rate >= 90 else "metric-good" if success_rate >= 70 else "metric-fair" if success_rate >= 50 else "metric-poor"
    availability_text = "优秀" if success_rate >= 90 else "良好" if success_rate >= 70 else "一般" if success_rate >= 50 else "较差"
    
    html += f'''
    <div style="margin-top: 25px; text-align: center; padding: 15px; background: #f8f9fa; border-radius: 8px;">
        <div style="font-size: 14px; color: #666;">应用可用性评级</div>
        <div style="margin-top: 10px;">
            <span class="metric-badge {availability_class}" style="font-size: 16px;">{availability_text}</span>
            <div style="font-size: 12px; color: #7f8c8d; margin-top: 5px;">成功率 {success_rate:.1f}% | 行业基准 ≥85%</div>
        </div>
    </div>
    '''
    
    return html

def _generate_detailed_issues_html(issues: list) -> str:
    """生成详细的问题诊断HTML - 商用级标准"""
    
    def get_issue_value(issue, key, default=None):
        """通用值获取函数，支持字典和Issue数据类对象"""
        if isinstance(issue, dict):
            return issue.get(key, default)
        else:
            return getattr(issue, key, default)
    
    if not issues:
        return '''
        <div style="background: #e8f5e8; padding: 25px; border-radius: 8px; text-align: center; margin: 25px 0;">
            <div style="font-size: 48px; margin-bottom: 15px;">🎉</div>
            <h3 style="color: #27ae60; margin-bottom: 10px;">无严重问题检测到</h3>
            <p style="color: #2e7d32; margin: 0;">系统环境与网络连接状态良好，符合SD-WAN部署要求</p>
        </div>
        '''
    
    # 分类问题
    critical_issues = [issue for issue in issues if get_issue_value(issue, "level", "") == "error"]
    warning_issues = [issue for issue in issues if get_issue_value(issue, "level", "") == "warning"]
    info_issues = [issue for issue in issues if get_issue_value(issue, "level", "") == "info"]
    
    html = '''
    <div style="margin: 25px 0;">
    '''
    
    # 关键问题
    if critical_issues:
        html += '''
        <div style="margin-bottom: 25px;">
            <h4 style="color: #e74c3c; display: flex; align-items: center; margin-bottom: 15px;">
                <span style="background: #e74c3c; color: white; width: 24px; height: 24px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-right: 10px; font-size: 12px;">⚠️</span>
                关键问题 (需要立即处理)
            </h4>
        '''
        for issue in critical_issues:
            category = get_issue_value(issue, "category", "未知分类")
            message = get_issue_value(issue, "message", "未知问题")
            title = f"{category}: {message.split('.')[0]}" if '.' in message else f"{category}问题"
            description = message
            
            html += f'''
            <div style="background: #ffebee; border-left: 4px solid #e74c3c; padding: 15px; margin-bottom: 10px; border-radius: 4px;">
                <div style="font-weight: 600; color: #c62828; margin-bottom: 5px;">{title}</div>
                <div style="color: #d32f2f; font-size: 14px;">{description}</div>
                <div style="color: #666; font-size: 12px; margin-top: 5px;">影响: 系统功能和网络连通性</div>
            </div>
            '''
        html += '</div>'
    
    # 警告问题
    if warning_issues:
        html += '''
        <div style="margin-bottom: 25px;">
            <h4 style="color: #f39c12; display: flex; align-items: center; margin-bottom: 15px;">
                <span style="background: #f39c12; color: white; width: 24px; height: 24px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-right: 10px; font-size: 12px;">🔔</span>
                警告问题 (建议优化)
            </h4>
        '''
        for issue in warning_issues:
            category = get_issue_value(issue, "category", "未知分类")
            message = get_issue_value(issue, "message", "未知问题")
            title = f"{category}: {message.split('.')[0]}" if '.' in message else f"{category}优化"
            description = message
            
            html += f'''
            <div style="background: #fff3e0; border-left: 4px solid #f39c12; padding: 15px; margin-bottom: 10px; border-radius: 4px;">
                <div style="font-weight: 600; color: #ef6c00; margin-bottom: 5px;">{title}</div>
                <div style="color: #f57c00; font-size: 14px;">{description}</div>
            </div>
            '''
        html += '</div>'
    
    # 信息提示
    if info_issues:
        html += '''
        <div style="margin-bottom: 25px;">
            <h4 style="color: #3498db; display: flex; align-items: center; margin-bottom: 15px;">
                <span style="background: #3498db; color: white; width: 24px; height: 24px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-right: 10px; font-size: 12px;">💡</span>
                优化建议
            </h4>
        '''
        for issue in info_issues:
            category = get_issue_value(issue, "category", "网络")
            message = get_issue_value(issue, "message", "系统运行正常")
            title = f"{category}状态良好"
            description = message
            
            html += f'''
            <div style="background: #e3f2fd; border-left: 4px solid #3498db; padding: 15px; margin-bottom: 10px; border-radius: 4px;">
                <div style="font-weight: 600; color: #1976d2; margin-bottom: 5px;">{title}</div>
                <div style="color: #2196f3; font-size: 14px;">{description}</div>
            </div>
            '''
        html += '</div>'
    
    html += '</div>'
    
    return html

def _generate_recommendations_html(recommendations: list, overall_score: float) -> str:
    """生成详细的优化建议HTML - 商用级标准"""
    
    # 根据评分生成基础建议
    base_recommendations = []
    if overall_score >= 80:
        base_recommendations = [
            "系统状态优秀，建议保持当前配置并定期监控",
            "考虑实施更高级的监控和自动化运维方案"
        ]
    elif overall_score >= 60:
        base_recommendations = [
            "系统状态良好，建议针对特定问题进行优化",
            "考虑增加网络冗余和负载均衡配置"
        ]
    else:
        base_recommendations = [
            "系统需要优化，建议优先处理关键问题",
            "考虑网络架构调整和性能优化方案"
        ]
    
    # 合并用户自定义建议
    all_recommendations = base_recommendations + recommendations
    
    if not all_recommendations:
        all_recommendations = [
            "定期执行系统健康检查",
            "保持操作系统和网络设备固件更新",
            "实施网络监控和告警机制"
        ]
    
    html = '''
    <div style="display: grid; gap: 15px;">
    '''
    
    for i, recommendation in enumerate(all_recommendations, 1):
        priority = "高" if overall_score < 60 and i <= 2 else "中" if overall_score < 80 and i <= 3 else "低"
        priority_color = "#e74c3c" if priority == "高" else "#f39c12" if priority == "中" else "#27ae60"
        
        html += f'''
        <div class="recommendation-item">
            <div style="display: flex; align-items: start; gap: 15px;">
                <div style="background: {priority_color}; color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0;">{i}</div>
                <div style="flex: 1;">
                    <div style="font-weight: 600; margin-bottom: 5px;">{recommendation}</div>
                    <div style="display: flex; gap: 15px; margin-top: 10px;">
                        <span style="background: {priority_color}15; color: {priority_color}; padding: 2px 8px; border-radius: 12px; font-size: 12px;">优先级: {priority}</span>
                        <span style="color: #7f8c8d; font-size: 12px;">建议执行</span>
                    </div>
                </div>
            </div>
        </div>
        '''
    
    html += '''
    </div>
    
    <div style="margin-top: 25px; padding: 20px; background: #f8f9fa; border-radius: 8px;">
        <h4 style="color: #2c3e50; margin-bottom: 15px;">📋 行动计划建议</h4>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
            <div style="text-align: center;">
                <div style="font-size: 24px; margin-bottom: 5px;">🔄</div>
                <div style="font-weight: 600;">即时处理</div>
                <div style="font-size: 12px; color: #7f8c8d;">高优先级问题</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 24px; margin-bottom: 5px;">📈</div>
                <div style="font-weight: 600;">本周优化</div>
                <div style="font-size: 12px; color: #7f8c8d;">中优先级改进</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 24px; margin-bottom: 5px;">🔮</div>
                <div style="font-weight: 600;">长期规划</div>
                <div style="font-size: 12px; color: #7f8c8d;">架构优化方案</div>
            </div>
        </div>
    </div>
    '''
    
    return html

def _generate_issues_html(issues: list) -> str:
    """生成问题识别的HTML"""
    if not issues:
        return '<p><span class="status-success">未发现严重问题</span></p>'
    
    error_count = sum(1 for i in issues if getattr(i, 'level', '') == "error")
    warning_count = sum(1 for i in issues if getattr(i, 'level', '') == "warning")
    
    return f'''
    <div class="issues-list">
        <p><strong>问题统计:</strong></p>
        <p>严重问题: {error_count}个 | 警告问题: {warning_count}个</p>
        <p>具体问题详情请查看终端输出</p>
    </div>
    '''

# 生成报告数据的核心函数
def collect_report_data(env_result, business_results, cross_border_results=None):
    """收集报告所需数据（不生成JSON文件，仅供HTML报告使用）"""
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
    
    # 简单评分计算
    total_items = len(business_results) if business_results else 1
    failed_items = sum(1 for res in business_results if not res.get("ping_reachable", True)) if business_results else 0
    
    report.overall_score = max(0, 100 - (failed_items * 100 / total_items))
    report.environment_score = 100
    report.connectivity_score = 100 - (failed_items * 100 / total_items) if total_items > 0 else 100
    
    if failed_items > 0:
        report.conclusion = f"发现 {failed_items} 个连通性问题"
        report.all_ok = False
    else:
        report.conclusion = "所有检测项正常"
        report.all_ok = True
    
    return report


# ================= 跨境链路专项测试报告功能 =================

def collect_cross_border_report_data(cross_border_result, mtu_results=None):
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
    
    return report


def generate_cross_border_html_report(report: FinalReport, cross_border_result) -> str:
    """生成商用级跨境链路专项测试HTML报告 - SDWAN运维深度分析"""
    
    # 报告基本信息
    report_id = getattr(report, 'report_id', 'N/A')
    timestamp = getattr(report, 'timestamp', 'N/A')
    overall_score = getattr(report, 'overall_score', 0)
    connectivity_score = getattr(report, 'connectivity_score', 0)
    conclusion = getattr(report, 'conclusion', '')
    
    # 跨境链路测试结果
    link_results = getattr(cross_border_result, 'link_results', [])
    summary = getattr(cross_border_result, 'summary', '')
    test_duration = getattr(cross_border_result, 'test_duration', 0)
    dns_comparison = getattr(cross_border_result, 'dns_comparison_results', [])
    precheck = getattr(cross_border_result, 'precheck', None)
    
    # HTML报告模板（商用级跨境链路专用格式）
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>跨境链路质量深度分析报告 - {report_id}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Microsoft YaHei', 'PingFang SC', 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; background: linear-gradient(135deg, #667eea10 0%, #764ba210 100%); min-height: 100vh; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 30px; }}
        .document-header {{ background: linear-gradient(135deg, #1a237e 0%, #283593 100%); color: white; padding: 40px; border-radius: 12px; margin-bottom: 30px; box-shadow: 0 8px 25px rgba(0,0,0,0.15); }}
        .document-header h1 {{ font-size: 34px; margin-bottom: 15px; font-weight: 300; }}
        .document-subtitle {{ font-size: 18px; opacity: 0.9; margin-bottom: 5px; }}
        .international-badge {{ background: rgba(255,255,255,0.2); padding: 5px 15px; border-radius: 20px; font-size: 14px; display: inline-block; margin-left: 10px; }}
        .score-panel {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 25px; margin-bottom: 30px; }}
        .score-card {{ background: white; padding: 30px; border-radius: 12px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border: 2px solid transparent; }}
        .score-card.overall {{ background: linear-gradient(135deg, #667eea, #764ba2); color: white; border-color: #5a6fd8; }}
        .score-card.latency {{ background: linear-gradient(135deg, #4CAF50, #45a049); color: white; border-color: #43a047; }}
        .score-card.stability {{ background: linear-gradient(135deg, #2196F3, #1976D2); color: white; border-color: #1e88e5; }}
        .score-value {{ font-size: 48px; font-weight: 700; margin: 15px 0; text-shadow: 0 2px 4px rgba(0,0,0,0.2); }}
        .score-progress {{ width: 100%; height: 8px; background: rgba(255,255,255,0.3); border-radius: 4px; margin: 15px 0; overflow: hidden; }}
        .score-progress-fill {{ height: 100%; background: rgba(255,255,255,0.8); }}
        .score-label {{ font-size: 16px; opacity: 0.95; letter-spacing: 1px; }}
        .score-desc {{ font-size: 13px; opacity: 0.8; margin-top: 10px; }}
        .section {{ background: white; padding: 35px; border-radius: 12px; margin-bottom: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-left: 5px solid #667eea; }}
        .section h2 {{ color: #1a237e; font-size: 24px; border-bottom: 2px solid #e8eaf6; padding-bottom: 15px; margin-bottom: 25px; display: flex; align-items: center; }}
        .section h2:before {{ content: "🌐"; margin-right: 10px; }}
        .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .metric-item {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 24px; font-weight: 700; color: #1a237e; }}
        .metric-label {{ font-size: 14px; color: #5c6bc0; margin-top: 5px; }}
        .link-status-card {{ background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; margin-bottom: 15px; border-left: 4px solid; }}
        .link-good {{ border-left-color: #4CAF50; }}
        .link-warning {{ border-left-color: #FF9800; }}
        .link-poor {{ border-left-color: #f44336; }}
        .tech-table {{ width: 100%; border-collapse: separate; border-spacing: 0; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }}
        .tech-table th {{ background: linear-gradient(135deg, #e8eaf6, #c5cae9); color: #1a237e; font-weight: 600; padding: 15px; }}
        .tech-table td {{ padding: 12px 15px; border-bottom: 1px solid #e0e0e0; }}
        .status-indicator {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; }}
        .status-excellent {{ background: #4CAF50; }}
        .status-good {{ background: #8BC34A; }}
        .status-fair {{ background: #FFC107; }}
        .status-poor {{ background: #f44336; }}
        .recommendation-panel {{ background: linear-gradient(135deg, #e3f2fd, #bbdefb); padding: 25px; border-radius: 8px; margin: 20px 0; }}
        .footer {{ text-align: center; padding: 30px; color: #5c6bc0; font-size: 13px; border-top: 1px solid #e8eaf6; margin-top: 40px; }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 报告头信息 -->
        <div class="document-header">
            <h1>跨境链路质量深度分析报告</h1>
            <div class="document-subtitle">报告编号: {report_id} <span class="international-badge">🌍 跨境专项</span></div>
            <div class="document-subtitle">检测时间: {timestamp} | 测试时长: {test_duration:.1f}秒</div>
            <div class="document-subtitle">检测范围: 国际链路质量 + DNS解析 + 网络稳定性</div>
        </div>

        <!-- 综合评分面板 -->
        <div class="score-panel">
            <div class="score-card overall">
                <div class="score-label">跨境链路综合评分</div>
                <div class="score-value">{overall_score:.1f}/100</div>
                <div class="score-progress">
                    <div class="score-progress-fill" style="width: {overall_score}%;"></div>
                </div>
                <div class="score-desc">国际链路整体质量评估</div>
            </div>
            <div class="score-card latency">
                <div class="score-label">平均延迟评分</div>
                <div class="score-value">{(100 - min(overall_score * 0.4, 40)):.1f}/100</div>
                <div class="score-progress">
                    <div class="score-progress-fill" style="width: {100 - min(overall_score * 0.4, 40)}%;"></div>
                </div>
                <div class="score-desc">跨国访问响应速度</div>
            </div>
            <div class="score-card stability">
                <div class="score-label">稳定性评分</div>
                <div class="score-value">{(overall_score * 0.6):.1f}/100</div>
                <div class="score-progress">
                    <div class="score-progress-fill" style="width: {overall_score * 0.6}%;"></div>
                </div>
                <div class="score-desc">链路抖动与丢包控制</div>
            </div>
        </div>

        <!-- 核心质量指标 -->
        <div class="section">
            <h2>核心质量指标</h2>
            <div class="metric-grid">
                <div class="metric-item">
                    <div class="metric-value">{len(link_results)}</div>
                    <div class="metric-label">测试链路数量</div>
                </div>
                <div class="metric-item">
                    <div class="metric-value">{sum(1 for link in link_results if link.stability_score >= 80)}</div>
                    <div class="metric-label">优质链路数量</div>
                </div>
                <div class="metric-item">
                    <div class="metric-value">{sum(1 for link in link_results if link.avg_latency < 200) if link_results else 0}</div>
                    <div class="metric-label">低延迟链路</div>
                </div>
                <div class="metric-item">
                    <div class="metric-value">{sum(1 for link in link_results if link.packet_loss < 2) if link_results else 0}</div>
                    <div class="metric-label">低丢包链路</div>
                </div>
            </div>
        </div>

        <!-- 链路质量详情 -->
        <div class="section">
            <h2>链路质量详情分析</h2>
            {_generate_cross_border_detailed_links_html(link_results)}
        </div>

        <!-- 技术性能分析 -->
        <div class="section">
            <h2>技术性能分析</h2>
            {_generate_technical_analysis_html(link_results)}
        </div>

        <!-- 优化建议 -->
        <div class="section">
            <h2>SD-WAN优化建议</h2>
            {_generate_cross_border_recommendations_html(link_results, overall_score)}
        </div>

        <!-- 行业对标 -->
        <div class="section">
            <h2>行业对标分析</h2>
            <table class="tech-table">
                <thead>
                    <tr>
                        <th>性能指标</th>
                        <th>当前水平</th>
                        <th>行业优秀</th>
                        <th>行业良好</th>
                        <th>状态评估</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>平均延迟(ms)</td>
                        <td>{sum(link.avg_latency for link in link_results)/len(link_results) if link_results else 0:.1f}</td>
                        <td>&lt;150ms</td>
                        <td>150-300ms</td>
                        <td><span class="status-indicator status-{'excellent' if (sum(link.avg_latency for link in link_results)/len(link_results) if link_results else 0) < 150 else 'good' if (sum(link.avg_latency for link in link_results)/len(link_results) if link_results else 0) < 300 else 'fair'}"></span>{'优秀' if (sum(link.avg_latency for link in link_results)/len(link_results) if link_results else 0) < 150 else '良好' if (sum(link.avg_latency for link in link_results)/len(link_results) if link_results else 0) < 300 else '一般'}</td>
                    </tr>
                    <tr>
                        <td>平均丢包率(%)</td>
                        <td>{sum(link.packet_loss for link in link_results)/len(link_results) if link_results else 0:.1f}%</td>
                        <td>&lt;1%</td>
                        <td>1-5%</td>
                        <td><span class="status-indicator status-{'excellent' if (sum(link.packet_loss for link in link_results)/len(link_results) if link_results else 0) < 1 else 'good' if (sum(link.packet_loss for link in link_results)/len(link_results) if link_results else 0) < 5 else 'fair'}"></span>{'优秀' if (sum(link.packet_loss for link in link_results)/len(link_results) if link_results else 0) < 1 else '良好' if (sum(link.packet_loss for link in link_results)/len(link_results) if link_results else 0) < 5 else '一般'}</td>
                    </tr>
                    <tr>
                        <td>稳定性评分</td>
                        <td>{overall_score:.1f}/100</td>
                        <td>≥85</td>
                        <td>70-85</td>
                        <td><span class="status-indicator status-{'excellent' if overall_score >= 85 else 'good' if overall_score >= 70 else 'fair'}"></span>{'优秀' if overall_score >= 85 else '良好' if overall_score >= 70 else '一般'}</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- 报告尾部 -->
        <div class="footer">
            <p>🌐 报告生成: SD-WAN跨境链路分析平台 v1.3 | 🕐 生成时间: {timestamp}</p>
            <p>📊 报告编号: {report_id} | 📧 技术支持: cross-border@example.com</p>
            <p>🔒 本报告包含敏感网络性能数据，请妥善保管</p>
        </div>
    </div>
</body>
</html>
'''


def _generate_cross_border_links_html(link_results: list) -> str:
    """生成跨境链路测试结果的HTML表格"""
    if not link_results:
        return "<p>未获取到链路测试结果</p>"
    
    html = '''
    <table>
        <thead>
            <tr>
                <th>目标</th>
                <th>平均延迟</th>
                <th>丢包率</th>
                <th>抖动</th>
                <th>稳定性评分</th>
                <th>状态</th>
            </tr>
        </thead>
        <tbody>
    '''
    
    for link in link_results:
        target = getattr(link, 'target', 'N/A')
        avg_latency = getattr(link, 'avg_latency', 0)
        packet_loss = getattr(link, 'packet_loss', 0)
        jitter = getattr(link, 'jitter', 0)
        stability_score = getattr(link, 'stability_score', 0)
        
        # 状态图标
        if stability_score >= 80:
            status = '<span class="status-success">优秀</span>'
        elif stability_score >= 60:
            status = '<span class="status-warning">良好</span>'
        else:
            status = '<span class="status-error">较差</span>'
        
        html += f'''
            <tr>
                <td>{target}</td>
                <td>{avg_latency:.1f}ms</td>
                <td>{packet_loss:.1f}%</td>
                <td>{jitter:.1f}ms</td>
                <td>{stability_score:.1f}/100</td>
                <td>{status}</td>
            </tr>
        '''
    
    html += '''
        </tbody>
    </table>
    '''
    
    return html


def _generate_cross_border_detailed_links_html(link_results: list) -> str:
    """生成商用级跨境链路详情HTML内容"""
    if not link_results:
        return '''
        <div class="link-status-card link-poor">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong style="font-size: 16px;">⚠️ 无链路测试数据</strong>
                <span class="status-indicator status-poor"></span>
            </div>
            <div style="margin-top: 10px; color: #666; font-size: 14px;">
                跨境链路测试未获取到有效数据，请检查网络连接或测试配置
            </div>
        </div>
        '''
    
    html_content = ''
    for link in link_results:
        # 获取链路结果属性
        link_name = getattr(link, 'link_name', getattr(link, 'target', '未知链路'))
        target = getattr(link, 'target', '未知目标')
        avg_latency = getattr(link, 'avg_latency', 0)
        max_latency = getattr(link, 'max_latency', 0)
        packet_loss = getattr(link, 'packet_loss', 0)
        jitter = getattr(link, 'jitter', 0)
        stability_score = getattr(link, 'stability_score', 0)
        test_count = getattr(link, 'test_count', 10)  # 默认值
        
        # 确定状态和样式
        if stability_score >= 85:
            status_class = 'link-good'
            status_indicator = 'status-excellent'
            status_text = '优质'
            quality_color = '#4CAF50'
        elif stability_score >= 70:
            status_class = 'link-good'
            status_indicator = 'status-good'
            status_text = '良好'
            quality_color = '#8BC34A'
        elif stability_score >= 60:
            status_class = 'link-warning'
            status_indicator = 'status-fair'
            status_text = '一般'
            quality_color = '#FFC107'
        else:
            status_class = 'link-poor'
            status_indicator = 'status-poor'
            status_text = '较差'
            quality_color = '#f44336'
        
        html_content += f'''
        <div class="link-status-card {status_class}">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <div>
                    <strong style="font-size: 18px; color: {quality_color};">{link_name}</strong>
                    <div style="color: #666; font-size: 14px; margin-top: 5px;">目标: {target}</div>
                </div>
                <div style="text-align: right;">
                    <span class="status-indicator {status_indicator}"></span>
                    <span style="font-weight: bold; color: {quality_color};">{status_text}</span>
                    <div style="font-size: 12px; color: #999;">稳定性: {stability_score:.1f}</div>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-top: 15px;">
                <div class="metric-item">
                    <div class="metric-value" style="color: {(quality_color if avg_latency < 200 else '#f44336') if avg_latency > 0 else '#999'};">
                        {avg_latency:.1f}<span style="font-size: 12px;">ms</span>
                    </div>
                    <div class="metric-label">平均延迟</div>
                    <div style="font-size: 11px; color: #666;">{'优秀' if avg_latency < 150 else '良好' if avg_latency < 300 else '一般'}</div>
                </div>
                
                <div class="metric-item">
                    <div class="metric-value" style="color: {(quality_color if packet_loss < 2 else '#f44336') if packet_loss >= 0 else '#999'};">
                        {packet_loss:.1f}<span style="font-size: 12px;">%</span>
                    </div>
                    <div class="metric-label">丢包率</div>
                    <div style="font-size: 11px; color: #666;">{'优秀' if packet_loss < 1 else '良好' if packet_loss < 5 else '需优化'}</div>
                </div>
                
                <div class="metric-item">
                    <div class="metric-value" style="color: {(quality_color if jitter < 30 else '#f44336') if jitter >= 0 else '#999'};">
                        {jitter:.1f}<span style="font-size: 12px;">ms</span>
                    </div>
                    <div class="metric-label">网络抖动</div>
                    <div style="font-size: 11px; color: #666;">{'稳定' if jitter < 20 else '可控' if jitter < 50 else '较高'}</div>
                </div>
                
                <div class="metric-item">
                    <div class="metric-value" style="color: {quality_color};">
                        {test_count if test_count > 0 else 'N/A'}
                    </div>
                    <div class="metric-label">测试次数</div>
                    <div style="font-size: 11px; color: #666;">{'充分' if test_count >= 10 else '不足'}</div>
                </div>
            </div>
        </div>
        '''
    
    return html_content


def _generate_technical_analysis_html(link_results: list) -> str:
    """生成跨境链路技术分析HTML内容"""
    if not link_results:
        return '<p>暂无技术分析数据</p>'
    
    # 计算统计指标
    total_links = len(link_results)
    avg_latency = sum(getattr(link, 'avg_latency', 0) for link in link_results) / total_links
    avg_packet_loss = sum(getattr(link, 'packet_loss', 0) for link in link_results) / total_links
    avg_jitter = sum(getattr(link, 'jitter', 0) for link in link_results) / total_links
    
    # 性能评估
    latency_eval = '国际专线水平' if avg_latency < 150 else '商用VPN水平' if avg_latency < 300 else '普通互联网水平'
    packet_loss_eval = '优质' if avg_packet_loss < 1 else '可接受' if avg_packet_loss < 5 else '需优化'
    jitter_eval = '高稳定性' if avg_jitter < 20 else '稳定性一般' if avg_jitter < 50 else '抖动较高'
    
    return f'''
    <div style="margin: 20px 0;">
        <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin-bottom: 15px;">
            <strong>📊 总体性能统计</strong>
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-top: 10px;">
                <div>
                    <div style="font-size: 12px; color: #6b7280;">测试链路数量</div>
                    <div style="font-size: 18px; font-weight: bold; color: #1a237e;">{total_links}</div>
                </div>
                <div>
                    <div style="font-size: 12px; color: #6b7280;">平均延迟</div>
                    <div style="font-size: 18px; font-weight: bold; color: {('#4CAF50' if avg_latency < 150 else '#FF9800' if avg_latency < 300 else '#f44336') if avg_latency > 0 else '#999'};">{avg_latency:.1f}ms</div>
                </div>
                <div>
                    <div style="font-size: 12px; color: #6b7280;">平均丢包率</div>
                    <div style="font-size: 18px; font-weight: bold; color: {('#4CAF50' if avg_packet_loss < 1 else '#FF9800' if avg_packet_loss < 5 else '#f44336') if avg_packet_loss >= 0 else '#999'};">{avg_packet_loss:.1f}%</div>
                </div>
                <div>
                    <div style="font-size: 12px; color: #6b7280;">平均抖动</div>
                    <div style="font-size: 18px; font-weight: bold; color: {('#4CAF50' if avg_jitter < 20 else '#FF9800' if avg_jitter < 50 else '#f44336') if avg_jitter >= 0 else '#999'};">{avg_jitter:.1f}ms</div>
                </div>
            </div>
        </div>
        
        <div style="background: #fff3e0; padding: 15px; border-radius: 8px;">
            <strong>💡 技术性能评估</strong>
            <ul style="margin: 10px 0; padding-left: 20px; color: #666;">
                <li>延迟水平: <strong>{latency_eval}</strong> ({avg_latency:.1f}ms)</li>
                <li>丢包控制: <strong>{packet_loss_eval}</strong> ({avg_packet_loss:.1f}%)</li>
                <li>抖动表现: <strong>{jitter_eval}</strong> ({avg_jitter:.1f}ms)</li>
                <li>链路可靠性: <strong>{(sum(1 for link in link_results if getattr(link, 'stability_score', 0) >= 70) / total_links * 100):.1f}%</strong> 链路达到商用标准</li>
            </ul>
        </div>
    </div>
    '''


def _generate_cross_border_recommendations_html(link_results: list, overall_score: float) -> str:
    """生成跨境链路优化建议HTML内容"""
    if not link_results:
        recommendations = [
            "🔍 建议重新执行跨境链路测试，确保获得完整的性能数据",
            "🌐 检查网络连接状态，确保能够访问国际目标",
            "⏱️ 验证测试配置参数，确保测试间隔和包数设置合理"
        ]
    else:
        recommendations = []
        
        # 根据性能指标生成建议
        avg_latency = sum(getattr(link, 'avg_latency', 0) for link in link_results) / len(link_results)
        avg_packet_loss = sum(getattr(link, 'packet_loss', 0) for link in link_results) / len(link_results)
        
        if avg_latency > 300:
            recommendations.append("🚀 建议启用SD-WAN智能路由，选择延迟更低的国际链路")
        elif avg_latency > 200:
            recommendations.append("⚡ 考虑配置链路优先级，将高延迟链路作为备用")
        
        if avg_packet_loss > 5:
            recommendations.append("🔧 启用丢包重传机制，优化TCP窗口大小设置")
        elif avg_packet_loss > 2:
            recommendations.append("🔍 监控链路质量，考虑使用FEC前向纠错技术")
        
        if overall_score >= 85:
            recommendations.append("✅ 当前跨境链路质量优秀，无需特殊优化")
        elif overall_score >= 70:
            recommendations.append("📈 轻微优化建议：监控关键业务链路的稳定性表现")
        else:
            recommendations.append("⚠️ 建议联系网络供应商，评估国际专线或云连接方案")
        
        recommendations.append("🔒 定期执行跨境链路监控，建立性能基线数据")
        recommendations.append("📊 配置性能告警，当链路质量下降时及时通知")
    
    html_content = '<div class="recommendation-panel">'
    html_content += '<strong style="display: block; margin-bottom: 15px; color: #1976D2;">🔧 优化建议与行动计划</strong>'
    
    for i, rec in enumerate(recommendations, 1):
        html_content += f'''
        <div style="display: flex; align-items: center; margin-bottom: 10px; padding: 10px; background: rgba(255,255,255,0.5); border-radius: 5px;">
            <span style="background: #1976D2; color: white; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; margin-right: 10px;">{i}</span>
            <span style="flex: 1;">{rec}</span>
        </div>
        '''
    
    html_content += '</div>'
    return html_content


def export_cross_border_html_report(report: FinalReport, cross_border_result, path: str = None):
    """导出跨境链路专项测试HTML格式报告"""
    
    if path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Cross_Border_Report_{timestamp}.html"
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