import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict

from sdwan_analyzer.models.entities import UnifiedTargetResult, BusinessType, Priority, PingResult, AppProbeResult, LinkQualityResult
from sdwan_analyzer.core.ping import ping_check
from sdwan_analyzer.modules.app_probe import run_app_probe

logger = logging.getLogger(__name__)

class DiagnosticScheduler:
    """智能诊断调度器"""
    
    def __init__(self, max_workers_basic: int = 5, max_workers_deep: int = 3):
        self.max_workers_basic = max_workers_basic
        self.max_workers_deep = max_workers_deep

    def should_do_deep_check(self, result: UnifiedTargetResult, strategy: Dict) -> bool:
        """判断是否需要深度检测"""
        biz_type = result.business_type.value if isinstance(result.business_type, BusinessType) else result.business_type
        
        # 1. 基于策略配置
        if biz_type in strategy and strategy[biz_type].get("deep_checks"):
            return True
            
        # 2. 基于运行时状态 (例如：高丢包但连通，需要查路由)
        if result.ping_result and result.ping_result.loss > 5.0 and result.basic_reachable:
            logger.info(f"目标 {result.target} 检测到高丢包，触发深度检测")
            return True
            
        return False
    
    def _do_basic_check(self, config: Dict) -> UnifiedTargetResult:
        """执行基础连通性检查"""
        target = config['target']
        logger.info(f"[Basic] 开始检测: {target}")
        
        # 创建统一结果对象，适配不同的类型输入
        business_type = BusinessType.UNKNOWN
        priority = Priority.MEDIUM
        
        # 智能类型转换
        type_str = config.get('type', 'unknown')
        if type_str == 'domestic':
            business_type = BusinessType.DOMESTIC
        elif type_str == 'cross_border':
            business_type = BusinessType.CROSS_BORDER
            
        priority_str = config.get('priority', 'medium')
        if priority_str == 'high':
            priority = Priority.HIGH
        elif priority_str == 'low':
            priority = Priority.LOW
            
        result = UnifiedTargetResult(
            target=target,
            business_type=business_type,
            priority=priority
        )

        try:
            # 1. Ping检测
            ping_res_data = ping_check(target)
            # 适配旧的PingCheckResult到新的PingResult
            result.ping_result = PingResult(
                is_success=ping_res_data.is_success,
                avg_rtt=ping_res_data.avg_rtt,
                loss=ping_res_data.loss,
                sent=ping_res_data.sent,
                received=ping_res_data.received,
                min_rtt=getattr(ping_res_data, 'min_rtt', ping_res_data.avg_rtt),
                max_rtt=getattr(ping_res_data, 'max_rtt', ping_res_data.avg_rtt)
            )
            result.basic_reachable = ping_res_data.is_success
            
            # 2. App Probe (仅当Ping通或策略要求时执行)
            if result.basic_reachable or business_type == BusinessType.CROSS_BORDER:
                app_res_data = run_app_probe(target, 443)
                result.app_probe_result = AppProbeResult(
                    tcp_open=app_res_data.tcp_open,
                    http_available=app_res_data.http_available,
                    detected_mtu=app_res_data.detected_mtu,
                    mtu_normal=app_res_data.mtu_normal,
                    response_time=getattr(app_res_data, 'response_time', 0.0)
                )
                if not app_res_data.tcp_open:
                    result.add_issue("error", "Port", f"TCP 443 关闭", "检查防火墙或服务状态")

        except Exception as e:
            logger.error(f"基础检测异常: {str(e)}")
            result.add_issue("error", "System", f"基础检测异常: {str(e)}")
            
        return result

    def _do_deep_check(self, result: UnifiedTargetResult) -> UnifiedTargetResult:
        """执行深度链路检查 - 仅限路由和应用层检测"""
        target = result.target
        logger.info(f"[Deep] 开始深度分析: {target}")
        
        try:
            # 深度检测只包含路由分析和应用层检测
            # 不包含MTU探测等跨境专项测试内容
            
            # 1. 应用层深度探测
            if result.ping_result and result.ping_result.avg_rtt > 100:
                # 高延迟时执行应用层深度检测
                app_result = run_app_probe(target, 80)  # 修复参数：去掉protocol参数，使用标准端口
                if app_result and app_result.http_available:
                    # app_probe_result在基础检查已存在，避免重复赋值
                    if not result.app_probe_result:
                        result.app_probe_result = app_result
            
            # 2. 基于ping结果的路由质量智能分析
            if result.ping_result:
                # 简化的链路质量评估（计算抖动方差）
                if hasattr(result.ping_result, 'min_rtt') and hasattr(result.ping_result, 'max_rtt'):
                    jitter = result.ping_result.max_rtt - result.ping_result.min_rtt
                    if jitter > 20:
                        logger.info(f"检测到链路抖动: {jitter}ms")
                        result.add_issue("info", "Network", f"检测到网络抖动: {jitter}ms")
            
            result.deep_check_completed = True
            
            # 警告策略 - 基于ping结果，不再依赖跨境测试数据
            if result.ping_result and result.ping_result.loss > 5.0:
                result.add_issue("warning", "Link", f"丢包率偏高: {result.ping_result.loss}%")

        except Exception as e:
            result.add_issue("warning", "Link", f"深度分析失败: {str(e)}")
            logger.error(f"Deep check failed for {target}: {e}")
            
        return result

    def execute_smart_diagnosis(self, targets_config: List[Dict], strategy: Dict) -> List[UnifiedTargetResult]:
        """智能执行诊断流程"""
        results = []
        
        # --- 第一阶段：并行基础检测 ---
        logger.info("[SMART] 启动第一阶段：基础连通性并行检测")
        with ThreadPoolExecutor(max_workers=self.max_workers_basic) as executor:
            future_to_config = {
                executor.submit(self._do_basic_check, config): config 
                for config in targets_config
            }
            
            for future in as_completed(future_to_config):
                try:
                    basic_result = future.result()
                    results.append(basic_result)
                except Exception as e:
                    logger.error(f"基础检测任务执行异常: {e}")

        # --- 第二阶段：按需深度检测 ---
        deep_check_candidates = [
            r for r in results 
            if self.should_do_deep_check(r, strategy)
        ]
        
        if deep_check_candidates:
            logger.info(f"[DEEP] 启动第二阶段：对 {len(deep_check_candidates)} 个目标进行深度分析")
            with ThreadPoolExecutor(max_workers=self.max_workers_deep) as executor:
                future_to_result = {
                    executor.submit(self._do_deep_check, res): res 
                    for res in deep_check_candidates
                }
                
                for future in as_completed(future_to_result):
                    try:
                        future.result() # 结果直接更新在对象引用中
                    except Exception as e:
                        logger.error(f"深度检测任务执行异常: {e}")
        else:
            logger.info("[OK] 无需进行深度链路分析")

        return results

    def _execute_legacy_diagnosis(self, targets_legacy: List[tuple]) -> List[UnifiedTargetResult]:
        """传统模式诊断 - 作为回退方案"""
        logger.info("🔄 启动传统模式诊断")
        
        # 将传统格式转换为新格式
        new_configs = []
        for target, biz_type_desc in targets_legacy:
            config = {
                "target": target,
                "type": "cross_border" if "跨境" in biz_type_desc else "domestic",
                "priority": "high",
                "description": biz_type_desc
            }
            new_configs.append(config)
        
        # 使用智能调度器处理
        strategy = {
            "cross_border": {"deep_checks": ["link_quality"]},
            "domestic": {"deep_checks": []}
        }
        
        return self.execute_smart_diagnosis(new_configs, strategy)