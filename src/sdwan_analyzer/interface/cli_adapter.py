"""CLI适配器层 - 实现命令接口层，不包含任何业务逻辑"""

import argparse
import sys
from typing import Optional, List
from dataclasses import dataclass
from sdwan_analyzer.core.contracts import AgentInput, Context
from sdwan_analyzer.infrastructure.config import ConfigManager


@dataclass
class CLIArgs:
    """CLI参数数据契约"""
    command: str
    target: Optional[str] = None
    port: Optional[int] = None
    targets: Optional[List[str]] = None
    profile: str = "default"
    output_format: str = "text"
    verbose: bool = False
    timeout: int = 30


class CLIAdapter:
    """CLI适配器，处理命令行参数到Agent输入结构的转换"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """创建命令行参数解析器"""
        parser = argparse.ArgumentParser(
            prog="sdwan-analyzer",
            description="SD-WAN网络分析器 - 符合AAPS-001标准的AI Agent架构"
        )
        
        # 主命令
        subparsers = parser.add_subparsers(dest="command", help="可用命令")
        
        # 一键检测命令
        oneclick_parser = subparsers.add_parser("oneclick", help="执行一键网络诊断")
        oneclick_parser.add_argument(
            "--profile", 
            default="default", 
            help="配置文件名称"
        )
        oneclick_parser.add_argument(
            "--format", 
            choices=["text", "json", "html"], 
            default="text", 
            help="输出格式"
        )
        
        # 网络测试命令
        test_parser = subparsers.add_parser("test", help="执行特定网络测试")
        test_subparsers = test_parser.add_subparsers(dest="test_type", help="测试类型")
        
        # Ping测试
        ping_parser = test_subparsers.add_parser("ping", help="执行Ping测试")
        ping_parser.add_argument("target", help="目标地址或域名")
        ping_parser.add_argument("--count", type=int, default=4, help="Ping次数")
        ping_parser.add_argument("--timeout", type=int, default=5, help="超时时间(秒)")
        
        # 端口测试
        port_parser = test_subparsers.add_parser("port", help="执行端口测试")
        port_parser.add_argument("target", help="目标地址或域名")
        port_parser.add_argument("port", type=int, help="端口号")
        port_parser.add_argument("--timeout", type=int, default=10, help="超时时间(秒)")
        
        # DNS测试
        dns_parser = test_subparsers.add_parser("dns", help="执行DNS解析测试")
        dns_parser.add_argument("--server", help="指定DNS服务器")
        dns_parser.add_argument("--domain", default="google.com", help="测试域名")
        
        # 路由跟踪
        trace_parser = test_subparsers.add_parser("trace", help="执行路由跟踪")
        trace_parser.add_argument("target", help="目标地址或域名")
        trace_parser.add_argument("--max-hops", type=int, default=30, help="最大跳数")
        
        # 跨境测试
        cross_parser = subparsers.add_parser("crossborder", help="执行跨境链路测试")
        cross_parser.add_argument(
            "--targets", 
            nargs="+", 
            help="测试目标列表"
        )
        cross_parser.add_argument(
            "--format", 
            choices=["text", "json", "html"], 
            default="html", 
            help="输出格式"
        )
        
        # 监控命令
        monitor_parser = subparsers.add_parser("monitor", help="网络监控模式")
        monitor_parser.add_argument(
            "targets", 
            nargs="+", 
            help="监控目标列表"
        )
        monitor_parser.add_argument(
            "--interval", 
            type=int, 
            default=60, 
            help="监控间隔(秒)"
        )
        
        # 通用参数
        for subparser in [parser, oneclick_parser, test_parser, cross_parser, monitor_parser]:
            subparser.add_argument(
                "-v", "--verbose", 
                action="store_true", 
                help="详细输出模式"
            )
        
        return parser
    
    def parse_args(self, args: Optional[List[str]] = None) -> CLIArgs:
        """解析命令行参数"""
        if args is None:
            args = sys.argv[1:]
        
        parsed = self.parser.parse_args(args)
        
        # 如果没有指定命令，显示帮助
        if not parsed.command:
            self.parser.print_help()
            sys.exit(0)
        
        # 转换为标准结构
        return CLIArgs(
            command=parsed.command,
            target=getattr(parsed, 'target', None),
            port=getattr(parsed, 'port', None),
            targets=getattr(parsed, 'targets', None),
            profile=getattr(parsed, 'profile', 'default'),
            output_format=getattr(parsed, 'format', 'text'),
            verbose=getattr(parsed, 'verbose', False),
            timeout=getattr(parsed, 'timeout', 30)
        )
    
    def build_agent_input(self, cli_args: CLIArgs) -> AgentInput:
        """构建Agent输入数据"""
        
        # 加载配置
        config = self.config_manager.load_config(cli_args.profile)
        
        # 构建输入数据
        return AgentInput(
            target=cli_args.target or "",
            session_id=f"session_{CLIAdapter._generate_session_id()}",
            context=Context(
                session_id=f"session_{CLIAdapter._generate_session_id()}",
                user_id="cli_user",
                platform="cli",
                environment=config.dict() if hasattr(config, 'dict') else config
            )
        )
    
    @staticmethod
    def _generate_session_id() -> str:
        """生成会话ID"""
        import time
        import random
        return f"{int(time.time())}_{random.randint(1000, 9999)}"
    
    def format_output(self, agent_output, cli_args: CLIArgs) -> str:
        """格式化输出结果"""
        
        if cli_args.output_format == "json":
            import json
            return json.dumps(agent_output.dict(), indent=2, ensure_ascii=False)
        
        elif cli_args.output_format == "html":
            # HTML格式化的逻辑
            return self._format_html_output(agent_output)
        
        else:  # text格式
            return self._format_text_output(agent_output)
    
    def _format_text_output(self, agent_output) -> str:
        """格式化文本输出"""
        output_lines = []
        
        output_lines.append("=" * 60)
        output_lines.append(f"SD-WAN分析器 - 诊断报告")
        output_lines.append("=" * 60)
        
        if agent_output.success:
            output_lines.append(f"✓ 诊断完成 - {agent_output.timestamp}")
            
            if agent_output.results:
                for result in agent_output.results:
                    output_lines.append(f"\n[{result.category.upper()}]")
                    
                    if result.metrics:
                        for metric, value in result.metrics.items():
                            output_lines.append(f"  {metric}: {value}")
                    
                    if result.recommendations:
                        output_lines.append("  \n建议:")
                        for rec in result.recommendations:
                            output_lines.append(f"    • {rec}")
        else:
            output_lines.append(f"✗ 诊断失败: {agent_output.error_message}")
        
        output_lines.append("=" * 60)
        return "\n".join(output_lines)
    
    def _format_html_output(self, agent_output) -> str:
        """格式化HTML输出"""
        # 简化的HTML输出，完整实现需要模板引擎
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>SD-WAN诊断报告</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .result {{ margin: 10px 0; padding: 10px; border-left: 3px solid #007acc; }}
                .success {{ color: green; }}
                .error {{ color: red; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>SD-WAN网络诊断报告</h1>
                <p>生成时间: {agent_output.timestamp}</p>
            </div>
            
            <div class="{'success' if agent_output.success else 'error'}">
                <h2>{'✓ 诊断成功' if agent_output.success else '✗ 诊断失败'}</h2>
                {f'<p><strong>错误:</strong> {agent_output.error_message}</p>' if not agent_output.success else ''}
            </div>
            
            {"".join([
                f'''
                <div class="result">
                    <h3>{result.category}</h3>
                    {"".join([f"<p><strong>{metric}:</strong> {value}</p>" for metric, value in result.metrics.items()])}
                </div>
                ''' for result in agent_output.results or []
            ])}
        </body>
        </html>
        """
        return html
    
    def run_interactive(self) -> int:
        """运行交互式模式"""
        try:
            while True:
                self._print_interactive_menu()
                choice = input("请选择功能 (0-5): ").strip()
                
                if choice == "0":
                    print("再见!")
                    return 0
                elif choice == "1":
                    return self._run_oneclick_interactive()
                elif choice == "2":
                    return self._run_test_interactive()
                elif choice == "3":
                    return self._run_crossborder_interactive()
                elif choice == "4":
                    return self._run_monitor_interactive()
                else:
                    print("无效选择，请重新输入")
        except KeyboardInterrupt:
            print("\n用户中断程序")
            return 0
    
    def _print_interactive_menu(self):
        """打印交互式菜单"""
        print("\n" + "=" * 50)
        print("    SD-WAN网络分析器 - 交互模式")
        print("=" * 50)
        print("1. 一键网络诊断")
        print("2. 网络测试工具")
        print("3. 跨境链路测试")
        print("4. 网络监控模式")
        print("0. 退出")
        print("=" * 50)
    
    def _run_oneclick_interactive(self) -> int:
        """交互式一键检测"""
        print("\n执行一键网络诊断...")
        # 这里会调用编排层引擎
        # 简化实现，返回成功代码
        return 0
    
    def _run_test_interactive(self) -> int:
        """交互式网络测试"""
        print("\n网络测试工具:")
        print("1. Ping测试")
        print("2. 端口测试")
        print("3. DNS测试")
        print("4. 路由跟踪")
        
        choice = input("请选择测试类型 (1-4): ").strip()
        
        if choice == "1":
            target = input("请输入目标地址: ").strip()
            if target:
                print(f"执行Ping测试: {target}")
        elif choice == "2":
            target = input("请输入目标地址: ").strip()
            port = input("请输入端口号: ").strip()
            if target and port:
                print(f"执行端口测试: {target}:{port}")
        # 其他测试类型...
        
        return 0
    
    def _run_crossborder_interactive(self) -> int:
        """交互式跨境测试"""
        print("\n执行跨境链路测试...")
        return 0
    
    def _run_monitor_interactive(self) -> int:
        """交互式监控"""
        print("\n网络监控模式 (开发中)...")
        return 0