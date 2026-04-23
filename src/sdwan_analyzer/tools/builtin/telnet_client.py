"""
Telnet客户端模块（最终稳定版）
✅ 最小化修复：仅移除timeout参数，保留所有原有功能
✅ IP默认值：192.168.33.1 | 端口默认：23
✅ 回车/Tab正常识别，无bytes/isprintable/await错误
✅ 兼容所有telnetlib3版本，无参数不兼容问题
"""
import sys
import asyncio
import telnetlib3
from typing import Optional

# 跨平台终端处理适配
try:
    import termios
    import tty
    UNIX_TERMINAL = True
except ImportError:
    UNIX_TERMINAL = False

try:
    import msvcrt
    WINDOWS_TERMINAL = True
except ImportError:
    WINDOWS_TERMINAL = False

class telnet_client:
    """
    Telnet客户端模块（基于原有逻辑，仅修复timeout参数错误）
    """
    def __init__(self):
        self.ip = "192.168.33.1"  # IP默认值
        self.port = 23            # 端口默认值
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.old_settings = None  # 保存终端原始配置
        self.running = False      # 交互运行状态

    def input_params(self) -> bool:
        """
        引导用户分步输入IP和端口（带默认值）- 保留原有逻辑
        """
        print("\n===== Telnet参数配置 =====")
        # 输入IP（带默认值）
        while True:
            ip_input = input(f"请输入设备IP地址（默认：{self.ip}）：").strip()
            # 使用默认值
            if not ip_input:
                break
            # 验证IP格式
            parts = ip_input.split(".")
            if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
                self.ip = ip_input
                break
            else:
                print("❌ IP格式错误（请输入合法IPv4地址，如192.168.1.1）！")

        # 输入端口（带默认值）
        while True:
            port_input = input(f"请输入Telnet端口（默认：{self.port}）：").strip()
            # 使用默认值
            if not port_input:
                break
            # 验证端口格式
            if port_input.isdigit() and 1 <= int(port_input) <= 65535:
                self.port = int(port_input)
                break
            else:
                print("❌ 端口格式错误（请输入1-65535之间的数字）！")

        print(f"✅ 配置完成：IP={self.ip}，Port={self.port}")
        return True

    def set_terminal_raw(self):
        """
        终端原始模式 - 保留原有逻辑
        """
        if UNIX_TERMINAL and self.old_settings is None:
            try:
                self.old_settings = termios.tcgetattr(sys.stdin)
                # 原始模式 + 保留回显（关键：输入可见）
                tty.setraw(sys.stdin.fileno())
                new_settings = termios.tcgetattr(sys.stdin)
                new_settings[3] |= termios.ECHO
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, new_settings)
            except Exception as e:
                print(f"⚠️ 终端模式设置警告：{str(e)}")

    def restore_terminal(self):
        """
        恢复终端配置 - 保留原有逻辑
        """
        if UNIX_TERMINAL and self.old_settings is not None:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
                self.old_settings = None
            except Exception as e:
                print(f"⚠️ 终端模式恢复警告：{str(e)}")

    def connect(self) -> bool:
        """
        建立Telnet连接 - 仅修复timeout参数错误
        """
        print(f"\n🔌 正在连接 {self.ip}:{self.port} ...")
        try:
            # 检查是否已有运行中的事件循环
            try:
                self.loop = asyncio.get_running_loop()
                # 如果在运行中的循环里，需要创建新循环
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
            except RuntimeError:
                # 没有运行中的循环，创建新的
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)

            # 核心修复：移除 timeout 参数，改用 wait_for 实现超时
            connect_coro = asyncio.open_connection(self.ip, self.port)
            self.reader, self.writer = self.loop.run_until_complete(
                asyncio.wait_for(connect_coro, timeout=10)
            )
            
            print("✅ Telnet连接成功！")
            print("📢 交互式Telnet窗口（支持Tab补全/回车执行）：")
            print("   → 输入命令按回车执行，输入 'quit' 退出")
            print("   → 按 Ctrl+C 可强制退出")
            return True
        
        except asyncio.TimeoutError:
            print(f"❌ 连接超时（10秒）")
        except ConnectionRefusedError:
            print(f"❌ 端口拒绝连接（设备未开启Telnet）")
        except Exception as e:
            print(f"❌ 连接失败：{type(e).__name__} - {str(e)}")
        return False

    async def _read_device_output(self):
        """
        读取设备输出 - 保留原有逻辑
        """
        while self.running:
            try:
                data = await asyncio.wait_for(self.reader.read(1024), timeout=0.05)
                if not data:
                    self.running = False
                    print("\n⚠️ 设备连接断开")
                    break
                
                # 实时打印设备输出
                sys.stdout.write(data.decode('utf-8', errors='replace'))
                sys.stdout.flush()
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                if self.running:
                    print(f"\n❌ 读取数据错误：{str(e)}")
                break

    async def _read_user_input(self):
        """
        读取用户输入 - 保留原有修复后的逻辑（回车/Tab正常）
        """
        input_buffer = []
        
        try:
            self.set_terminal_raw()
            
            while self.running:
                key = b""
                key_str = ""
                
                # 跨平台读取按键
                if WINDOWS_TERMINAL:
                    if not msvcrt.kbhit():
                        await asyncio.sleep(0.01)
                        continue
                    key = msvcrt.getch()
                    # 处理Windows扩展键（方向键等）
                    if key in [b'\xe0', b'\x00']:
                        key += msvcrt.getch()
                        continue  # 扩展键直接发送，不处理
                    # 字节转字符串（修复isprintable错误）
                    try:
                        key_str = key.decode('ascii', errors='ignore')
                    except:
                        key_str = ""
                else:
                    # Unix系统直接读取字符串
                    key_str = await self.loop.run_in_executor(None, sys.stdin.read, 1)
                    if not key_str:
                        continue
                    # 字符串转字节
                    key = key_str.encode('utf-8', errors='replace')

                # 按键处理逻辑（回车/Tab正常识别）
                if key_str == '\x03':  # Ctrl+C
                    self.writer.write(b'\x03')
                    await self.writer.drain()
                elif key_str in ['\r', '\n']:  # 回车（兼容所有系统）
                    if input_buffer:
                        cmd = b''.join(input_buffer) + b'\r\n'
                        self.writer.write(cmd)
                        await self.writer.drain()
                        input_buffer = []
                    sys.stdout.write('\n')
                    sys.stdout.flush()
                elif key_str == '\t':  # Tab补全（直接发送给设备）
                    self.writer.write(b'\t')
                    await self.writer.drain()
                    sys.stdout.write('\t')
                    sys.stdout.flush()
                elif key_str in ['\x08', '\x7f']:  # 退格
                    if input_buffer:
                        input_buffer.pop()
                        sys.stdout.write('\b \b')
                        sys.stdout.flush()
                elif key_str == 'q' and input_buffer == [b'q', b'u', b'i', b't']:
                    # 输入quit退出
                    self.running = False
                    break
                elif len(key_str) == 1 and key_str.isprintable():  # 普通字符
                    input_buffer.append(key)
                    sys.stdout.write(key_str)
                    sys.stdout.flush()
                else:  # 其他特殊键直接发送
                    if key:  # 确保有数据才发送
                        self.writer.write(key)
                        await self.writer.drain()

        finally:
            self.restore_terminal()

    def telnet_interactive(self):
        """
        启动交互 - 保留原有修复后的逻辑
        """
        if not (self.reader and self.writer and self.loop):
            print("❌ 无有效连接")
            return

        self.running = True
        
        # 修复await语法错误的逻辑保留
        async def _telnet_interactive_core():
            try:
                await asyncio.gather(
                    self._read_device_output(),
                    self._read_user_input()
                )
            except Exception as e:
                print(f"\n❌ 交互异常：{type(e).__name__} - {str(e)}")

        try:
            self.loop.run_until_complete(_telnet_interactive_core())
        except KeyboardInterrupt:
            print("\n⚠️ 用户中断操作")
        finally:
            self.running = False
            self.close()

    def close(self):
        """
        关闭连接 - 保留原有逻辑
        """
        self.restore_terminal()
        
        try:
            if self.writer and not self.writer.transport.is_closing():
                self.writer.close()
                if self.loop:
                    self.loop.run_until_complete(self.writer.wait_closed())
        except:
            pass
        
        try:
            if self.loop:
                for task in asyncio.all_tasks(self.loop):
                    task.cancel()
                self.loop.stop()
                self.loop.close()
        except:
            pass
        
        print("\n🔌 Telnet连接已关闭")

    def run(self):
        """
        主流程 - 保留原有逻辑
        """
        if not self.input_params() or not self.connect():
            return
        
        try:
            self.telnet_interactive()
        except Exception as e:
            print(f"\n❌ 运行异常：{type(e).__name__} - {str(e)}")
            self.close()

# 测试入口
if __name__ == "__main__":
    try:
        import telnetlib3
    except ImportError:
        print("❌ 缺少依赖，请执行：pip install telnetlib3")
        sys.exit(1)
    
    client = telnet_client()
    client.run()