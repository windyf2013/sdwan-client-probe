# d:/AI/testing/proj5/sdwan_analyzer/src/sdwan_analyzer/modules/report.py

import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict

# 1. 更新导入，引入新的统一模型
from sdwan_analyzer.models.diagnose import (
    FinalReport, 
    Issue, 
    SystemEnvironmentResult, 
    LocalConfigCheckResult,  
    SystemDiagnoseResult     
)

# 导入配置以获取 REPORT_DIR
from sdwan_analyzer.config import REPORT_DIR

@dataclass
class DiagnosisIssue:
    """报告模块内部使用的问题结构"""
    level: str
    category: str
    message: str
    detail: str = ""
    suggestion: str = ""

def collect_all_issues(
    env_result: Optional[SystemEnvironmentResult], 
    business_results: List[Dict]
) -> List[Issue]:
    """汇总所有诊断问题到 FinalReport.Issue 格式"""
    issues = []
    
    # 1. 系统环境与配置问题 (来自统一的 env_result)
    if env_result:
        issues.extend(env_result.issues)

    # 2. 业务测试结果
    if business_results:
        for res in business_results:
            if not res.get("ping_reachable"):
                issues.append(Issue(
                    level="error",
                    category="Business Connectivity",
                    message=f"目标 {res.get('target')} Ping 不可达"
                ))
            
            app_res = res.get("app_res")
            if app_res and isinstance(app_res, dict):
                if not app_res.get("tcp_open"):
                    issues.append(Issue(
                        level="error",
                        category="Business Port",
                        message=f"目标 {res.get('target')} TCP 443 关闭"
                    ))

    return issues

def generate_report(
    env_result: Optional[SystemEnvironmentResult], 
    network_context: Optional[Any],
    cross_border_results: Optional[Dict],
    business_results: List[Dict],
    target: str = ""
) -> FinalReport:
    """生成完整诊断报告"""
    
    report = FinalReport(
        report_id=str(uuid.uuid4())[:8],
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        target=target
    )
    
    # 1. 赋值原始数据
    report.system = env_result 
    report.local_config = None 
    report.network_context = network_context
    report.cross_border_results = cross_border_results or {}
    
    # 转换业务结果为 AppProbeResult 列表 (如果需要)
    report.app_probes = [] 
    for res in business_results:
        if res.get("app_res"):
            pass

    # 2. 收集并添加 Issues
    detected_issues = collect_all_issues(env_result, business_results)
    report.issues = detected_issues
    
    # 3. 计算评分
    env_score = 100.0
    if env_result:
        env_score = env_result.config_score
    
    conn_score = 100.0
    if cross_border_results and isinstance(cross_border_results, dict):
        conn_score = cross_border_results.get("overall_score", 100.0)
    
    report.environment_score = max(0, min(100, env_score))
    report.connectivity_score = max(0, min(100, conn_score))
    
    # 整体评分加权
    report.overall_score = (report.environment_score * 0.4 + report.connectivity_score * 0.6)
    
    # 4. 生成结论
    error_count = sum(1 for i in report.issues if i.level == "error")
    warning_count = sum(1 for i in report.issues if i.level == "warning")
    
    if error_count > 0:
        report.conclusion = f"❌ 发现 {error_count} 个严重问题，建议立即排查"
        report.all_ok = False
    elif warning_count > 0:
        report.conclusion = f"⚠️ 基本正常，但存在 {warning_count} 个警告项"
    else:
        report.conclusion = "✅ 所有检测项正常"
        report.all_ok = True

    return report

def export_report_to_file(report: FinalReport, path: Optional[str] = None):
    """导出报告到 JSON"""
    if path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 【修改点】使用 config 中的 REPORT_DIR (默认为当前目录)
        # 确保目录存在
        if not os.path.exists(REPORT_DIR):
            os.makedirs(REPORT_DIR)
        
        filename = f"SDWAN_Report_{timestamp}.json"
        path = os.path.join(REPORT_DIR, filename)
    
    # 简单序列化，处理 dataclass
    def serialize(obj):
        if hasattr(obj, '__dataclass_fields__'):
            return asdict(obj)
        raise TypeError(f"Type {type(obj)} not serializable")

    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=serialize)
        print(f"\n✅ 报告已保存至: {path}")
    except Exception as e:
        print(f"\n❌ 报告保存失败: {e}")