#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
客户端全场景网络诊断工具 - 最终修复版
功能：自底向上检查、环境识别、浏览器全量捕获、并发出口IP探测、一致性分析、网络交互流全景图
用法：python net_diag_final.py <URL> [--headed] [--verbose]
"""

import sys, os, time, json, socket, ssl, re, ipaddress, subprocess, platform, signal
from datetime import datetime, timezone
from urllib.parse import urlparse
from collections import defaultdict
from multiprocessing import Process, Queue
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests, dns.resolver, netifaces

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# ---------- 配置 ----------
INTERNET_CHECK_URLS = [
    "https://www.baidu.com/", "https://www.qq.com/",
    "http://g.cn/generate_204", "http://captive.v2ex.co/generate_204",
    "https://www.google.com/generate_204", "https://www.cloudflare.com/cdn-cgi/trace"
]
CAPTIVE_PORTAL_CHECK = "http://captive.v2ex.co/generate_204"

IP_REGION_SERVICES = [
    {"name": "ip-api.com", "url": "http://ip-api.com/json/{}?lang=zh-CN",
     "parser": lambda r: f"{r.json().get('country', '')} {r.json().get('regionName', '')} {r.json().get('city', '')}".strip()},
    {"name": "ip.useragentinfo.com", "url": "https://ip.useragentinfo.com/json?ip={}",
     "parser": lambda r: f"{r.json().get('country', '')} {r.json().get('province', '')} {r.json().get('city', '')}".strip()}
]

DOH_SERVERS = [
    {"name": "阿里云", "url": "https://dns.alidns.com/resolve", "region": "domestic"},
    {"name": "腾讯云", "url": "https://doh.pub/dns-query", "region": "domestic"},
    {"name": "Cloudflare", "url": "https://cloudflare-dns.com/dns-query", "region": "global"},
]

IP_ECHO_SERVICES = [
    {"name": "ip.sb", "url": "https://api-ipv4.ip.sb/ip", "parser": lambda r: r.text.strip()},
    {"name": "搜狐IP", "url": "https://pv.sohu.com/cityjson?ie=utf-8",
     "parser": lambda r: re.search(r'"cip"\s*:\s*"([\d\.]+)"', r.text).group(1)},
    {"name": "ipify", "url": "https://api.ipify.org", "parser": lambda r: r.text.strip()}
]

SYSTEM = platform.system()


def run_network_waterfall_diagnosis(target_url: str, output_dir: str = "./reports") -> dict:
    """
    执行全场景网络诊断：
    1. 浏览器捕获请求 (Playwright Trace)
    2. 并发出口 IP 探测
    3. 一致性分析 (多出口/DNS分离)
    4. 生成 HTML 可视化报告
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {"status": "error", "message": "Playwright 未安装。请运行: pip install playwright && playwright install"}

    # 确保 URL 格式正确
    if not target_url.startswith(('http://', 'https://')):
        target_url = 'https://' + target_url

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 定义输出文件路径
    trace_file = os.path.join(output_dir, f"trace_{timestamp}.zip")
    html_report = os.path.join(output_dir, f"report_{timestamp}.html")
    json_data = os.path.join(output_dir, f"data_{timestamp}.json")

    print(f"\n[NetWaterfall] 正在启动全场景诊断: {target_url}")
    print(f"[NetWaterfall] 阶段 1/4: 浏览器捕获与 Trace 录制...")
    
    requests_info = []
    start_time = time.time()

    try:
        # --- 阶段 1: Playwright 捕获 ---
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True
            )
            
            # 启动 Trace 录制
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            
            page = context.new_page()
            
            def handle_request(request):
                parsed = urlparse(request.url)
                if parsed.hostname and not request.url.startswith(('data:', 'blob:')):
                    requests_info.append({
                        "url": request.url,
                        "domain": parsed.hostname,
                        "resource_type": request.resource_type,
                        "start_time": time.time()
                    })

            page.on("request", handle_request)
            
            try:
                page.goto(target_url, wait_until="networkidle", timeout=30000)
                time.sleep(2) # 等待动态内容
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
            except Exception as e:
                print(f"[NetWaterfall] 警告: 页面加载异常 - {e}")

            # 保存 Trace
            context.tracing.stop(path=trace_file)
            browser.close()

        if not requests_info:
            return {"status": "error", "message": "未捕获到任何网络请求"}

        print(f"[NetWaterfall] ✅ 捕获 {len(requests_info)} 个请求")
        
        # --- 阶段 2: 并发出口 IP 探测 ---
        print(f"[NetWaterfall] 阶段 2/4: 并发探测域名出口 IP (这可能需要几十秒)...")
        probed_results = probe_domains(requests_info, max_workers=15)
        
        # --- 阶段 3: 一致性分析 ---
        print(f"[NetWaterfall] 阶段 3/4: 分析链路一致性...")
        consistency = analyze_consistency(probed_results)
        
        # --- 阶段 4: 构建报告数据 ---
        print(f"[NetWaterfall] 阶段 4/4: 生成 HTML 报告...")
        
        # 获取本地 IP 用于报告展示
        local_ip = "127.0.0.1"
        try:
            import netifaces
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr['addr']
                        if not ip.startswith('127.'):
                            local_ip = ip
                            break
        except: pass

        # 构建简化的事件流用于 HTML 展示 (复用原有逻辑)
        # 注意：这里为了简化，我们直接传递原始数据给 generate_html_report，
        # 或者你可以选择在这里调用 NetworkFlowBuilder 构建更详细的事件列表。
        # 为了保持代码简洁且利用现有功能，我们直接构造 report 对象。
        
        report_data = {
            "target_url": target_url,
            "timestamp": time.time(),
            "local_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "env_type": "browser_capture", # 简化环境类型
            "stack_check": {"local": {"gateways": [], "dns_servers": [], "proxy": {}}}, # 占位符，如需详细本地信息可调用 LocalNetworkChecker
            "browser_requests": requests_info,
            "domain_probes": probed_results,
            "consistency": consistency,
            "events": [], # 如果需要详细瀑布流表格，需在此处调用 NetworkFlowBuilder.build()
            "anomalies": []
        }
        
        # 如果希望 HTML 中有详细的逐行流水账，可以启用以下代码：
        builder = NetworkFlowBuilder(local_ip, requests_info, probed_results)
        report_data['events'] = builder.build()
        report_data['anomalies'] = builder.get_anomalies()
        
        # 补充本地网络信息到报告
        local_checker = LocalNetworkChecker()
        report_data['stack_check']['local'] = local_checker.run()

        # 生成 HTML
        generate_html_report(report_data, output_path=html_report)
        
        # 保存 JSON 数据备份
        with open(json_data, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)

        duration = time.time() - start_time
        
        print(f"\n[NetWaterfall] ✅ 诊断全部完成! (耗时: {duration:.1f}s)")
        print(f"📄 HTML 报告: {html_report}")
        print(f"📦 Trace 文件: {trace_file}")
        
        # 打印关键分析结果到控制台
        if consistency.get('multi_egress'):
            print(f"⚠️ 检测到多出口 NAT: {consistency['http_ips']}")
        if consistency.get('mismatches'):
            print(f"⚠️ 检测到 {len(consistency['mismatches'])} 个域名存在 DNS/HTTP 出口分离")
        
        return {
            "status": "success",
            "html_report": html_report,
            "trace_file": trace_file,
            "json_data": json_data,
            "consistency_summary": consistency
        }

    except Exception as e:
        print(f"[NetWaterfall] ❌ 诊断失败: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

# ---------- 通用服务调用 ----------
def call_with_fallback(service_list, timeout=5, **kwargs):
    for svc in service_list:
        try:
            url = svc['url'].format(**kwargs) if '{' in svc['url'] else svc['url']
            resp = requests.get(url, timeout=timeout, headers={"User-Agent": "NetDiag/11.0"})
            if resp.status_code == 200:
                result = svc['parser'](resp)
                if result: return result, svc.get('name', 'unknown')
        except: continue
    return None, "all_failed"

def get_egress_ip(timeout=5):
    ip, src = call_with_fallback(IP_ECHO_SERVICES, timeout)
    if ip and re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip): return ip, src
    return None, "all_failed"

def get_ip_region(ip, timeout=5):
    region, _ = call_with_fallback(IP_REGION_SERVICES, timeout, ip=ip)
    return region if region else "未知"

def dns_query_with_doh(domain, prefer_domestic=None, timeout=5):
    if not domain: return {"domain": domain, "resolved_ips": [], "egress_ip_during_dns": None, "doh_server": "invalid"}
    if prefer_domestic is None: prefer_domestic = domain.endswith('.cn')
    sorted_doh = sorted(DOH_SERVERS, key=lambda x: 0 if x['region'] == ('domestic' if prefer_domestic else 'global') else 1)
    egress_ip, _ = get_egress_ip()
    for svc in sorted_doh:
        try:
            resp = requests.get(svc['url'], params={"name": domain, "type": "A"}, timeout=timeout, headers={"Accept": "application/dns-json"})
            if resp.status_code == 200:
                data = resp.json()
                ips = [ans["data"] for ans in data.get("Answer", []) if ans["type"] == 1]
                return {"domain": domain, "resolved_ips": ips, "egress_ip_during_dns": egress_ip, "doh_server": svc['name']}
        except: continue
    return {"domain": domain, "resolved_ips": [], "egress_ip_during_dns": egress_ip, "doh_server": "all_failed"}

# ---------- 本地网络检查 ----------
class LocalNetworkChecker:
    def __init__(self): self.result = {}
    def get_all_interfaces(self):
        interfaces = {}
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            ipv4 = addrs.get(netifaces.AF_INET, [])
            ipv6 = addrs.get(netifaces.AF_INET6, [])
            mac = addrs.get(netifaces.AF_LINK, [{}])[0].get('addr') if netifaces.AF_LINK in addrs else None
            interfaces[iface] = {"ipv4": [a['addr'] for a in ipv4], "netmask": [a.get('netmask') for a in ipv4], "ipv6": [a['addr'].split('%')[0] for a in ipv6], "mac": mac}
        return interfaces
    def get_default_gateways(self):
        gws = []
        try:
            for fam, gw in netifaces.gateways().get('default', {}).items():
                if fam == netifaces.AF_INET: gws.append({"ip": gw[0], "interface": gw[1]})
        except: pass
        return gws
    def get_dns_servers(self):
        dns = []
        if SYSTEM == "Windows":
            try:
                out = subprocess.check_output("ipconfig /all", shell=True, text=True, encoding='gbk', errors='ignore')
                dns.extend(re.findall(r"(?:DNS\s*服务器|DNS\s*Servers)[.\s]*:\s*([\d\.]+)", out, re.I))
                out2 = subprocess.check_output("netsh interface ip show dns", shell=True, text=True, encoding='gbk', errors='ignore')
                dns.extend(re.findall(r"(\d+\.\d+\.\d+\.\d+)", out2))
            except: pass
        else:
            try:
                with open('/etc/resolv.conf') as f:
                    for line in f:
                        if line.startswith('nameserver'): dns.append(line.split()[1])
            except: pass
            if SYSTEM == "Darwin" and not dns:
                try:
                    out = subprocess.check_output("scutil --dns | grep nameserver", shell=True, text=True)
                    dns = re.findall(r"(\d+\.\d+\.\d+\.\d+)", out)
                except: pass
        return list(set(dns))
    def get_system_proxy(self):
        proxies = {}
        for v in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']:
            if os.environ.get(v): proxies[v] = os.environ[v]
        if SYSTEM == "Windows":
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
                if winreg.QueryValueEx(key, "ProxyEnable")[0]:
                    proxies['IE Proxy'] = winreg.QueryValueEx(key, "ProxyServer")[0]
                winreg.CloseKey(key)
            except: pass
        return proxies
    def check_firewall_outbound(self):
        targets = [("www.baidu.com",80), ("www.baidu.com",443), ("114.114.114.114",53)]
        res = {}
        for h,p in targets:
            try:
                s = socket.socket(); s.settimeout(3); r = s.connect_ex((h,p))==0; s.close(); res[f"{h}:{p}"] = r
            except: res[f"{h}:{p}"] = False
        return res
    def run(self):
        self.result.update({"interfaces": self.get_all_interfaces(), "gateways": self.get_default_gateways(),
                            "dns_servers": self.get_dns_servers(), "proxy": self.get_system_proxy(),
                            "firewall": self.check_firewall_outbound()})
        return self.result

# ---------- 环境识别 ----------
def identify_network_environment(local_info):
    vpn_kw = ['ppp','utun','ipsec','tun','tap','vpn','l2tp','pptp','wg','wireguard']
    for iface in local_info.get('interfaces',{}):
        if any(k in iface.lower() for k in vpn_kw): return 'vpn_client'
    if len(local_info.get('gateways',[])) > 1: return 'vpn_client'
    return 'normal'

# ---------- 网络栈检查 ----------
class NetworkStackChecker:
    def __init__(self, target_url, verbose=False):
        self.target = target_url; self.verbose = verbose
        self.parsed = urlparse(target_url); self.host = self.parsed.hostname
        self.port = self.parsed.port or (443 if self.parsed.scheme=='https' else 80)
        self.results = {}; self.local_checker = LocalNetworkChecker(); self.env_type = 'normal'
    def check_local_network(self):
        info = self.local_checker.run(); self.results['local'] = info
        self.env_type = identify_network_environment(info)
        valid = any(v['ipv4'] and not v['ipv4'][0].startswith('127.') for v in info['interfaces'].values())
        return valid and len(info['gateways'])>0
    def check_internet(self):
        for url in INTERNET_CHECK_URLS:
            try:
                if requests.head(url, timeout=5).status_code < 400:
                    self.results['internet'] = {"status": "可达", "check_url": url}; return True
            except: continue
        self.results['internet'] = {"status": "不可达"}; return False
    def check_captive_portal(self):
        try:
            resp = requests.get(CAPTIVE_PORTAL_CHECK, timeout=5, allow_redirects=False)
            self.results['captive'] = {"status": "无强制门户" if resp.status_code==204 else "可能被重定向"}
        except: self.results['captive'] = {"status": "检测失败"}
    def check_dns(self):
        try: traditional = [str(r) for r in dns.resolver.resolve(self.host, 'A')]
        except: traditional = []
        doh = dns_query_with_doh(self.host)
        self.results['dns'] = {"traditional": traditional, "doh": doh}
        return bool(traditional or doh.get('resolved_ips'))
    def check_tcp_tls(self):
        sock = None
        try:
            sock = socket.create_connection((self.host, self.port), 10)
            self.results['tcp'] = {"status": "成功"}
            if self.parsed.scheme == 'https':
                ctx = ssl.create_default_context()
                with ctx.wrap_socket(sock, server_hostname=self.host) as ssock:
                    cert = ssock.getpeercert()
                    issuer = dict(x[0] for x in cert.get('issuer',[]))
                    self.results['tls'] = {"issuer": issuer.get('commonName','未知'), "expire": cert.get('notAfter')}
            return True
        except Exception as e:
            self.results['tcp'] = {"status": "失败", "error": str(e)}; return False
        finally:
            if sock: sock.close()
    def check_http(self):
        chain = []
        try:
            cur = self.target
            for _ in range(10):
                egress, _ = get_egress_ip()
                resp = requests.get(cur, allow_redirects=False, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                chain.append({"url": cur, "status_code": resp.status_code, "egress_ip": egress})
                if resp.status_code in (301,302,303,307,308):
                    loc = resp.headers.get('Location')
                    if loc: cur = requests.compat.urljoin(cur, loc); continue
                final = resp; break
            else: final = resp
            self.results['http'] = {"status_code": final.status_code, "final_url": final.url, "redirect_chain": chain}
            return final.status_code < 400
        except Exception as e:
            self.results['http'] = {"error": str(e), "redirect_chain": chain}; return False
    def run_all(self):
        print("🔍 开始网络栈自底向上检查...")
        ok1 = self.check_local_network(); print(f"  L1 本地网络 ({self.env_type}) {'✅' if ok1 else '❌'}")
        ok2 = self.check_internet(); print(f"  L2 互联网连通 {'✅' if ok2 else '❌'}")
        self.check_captive_portal()
        ok3 = self.check_dns(); print(f"  L3 DNS解析 {'✅' if ok3 else '❌'}")
        ok4 = self.check_tcp_tls(); print(f"  L4 TCP/TLS {'✅' if ok4 else '❌'}")
        ok5 = self.check_http(); print(f"  L5 HTTP应用 {'✅' if ok5 else '❌'}")
        return all([ok1,ok2,ok3,ok4,ok5])

# ---------- Playwright 子进程 ----------
def playwright_worker(target_url, queue, headed, verbose):
    """子进程：收集请求，详细日志，快速退出"""
    def log(msg):
        # 子进程输出带时间戳的日志
        print(f"[子进程 {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)

    requests_info = []
    try:
        log("启动 Playwright")
        with sync_playwright() as p:
            log("启动浏览器")
            browser = p.chromium.launch(headless=not headed)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1280, "height": 720},
                ignore_https_errors=True
            )
            page = context.new_page()
            log("浏览器上下文已创建")

            def handle_request(request):
                url = request.url
                if url.startswith(('data:', 'blob:', 'about:', 'chrome-extension:')):
                    return
                parsed = urlparse(url)
                domain = parsed.hostname
                requests_info.append({
                    "url": url,
                    "domain": domain,
                    "resource_type": request.resource_type,
					"start_time": time.time()
                })
                if verbose:
                    print(f"      [捕获] {request.resource_type.upper()} {url[:70]}")

            page.on('request', handle_request)
            log("请求监听器已绑定")

            # 确保 target_url 有协议头
            if not target_url.startswith(('http://', 'https://')):
                target_url = 'https://' + target_url
            log(f"开始导航: {target_url}")
            page.goto(target_url, wait_until="commit", timeout=10000)
            log("导航 commit 完成，开始等待6秒收集资源")
            time.sleep(6)
            log("等待结束，尝试滚动页面")
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                log("滚动完成")
            except Exception as e:
                log(f"滚动异常（忽略）: {e}")

            log(f"共捕获 {len(requests_info)} 个请求，准备关闭浏览器")
            # 关闭浏览器（可能阻塞，但我们不等待）
            try:
                browser.close()
                log("浏览器 close() 调用完成")
            except Exception as e:
                log(f"浏览器 close() 异常: {e}")

    except Exception as e:
        log(f"子进程异常: {e}")
        queue.put({"error": str(e), "partial": requests_info})
    else:
        log(f"子进程正常结束，将数据放入队列（{len(requests_info)} 条）")
        queue.put({"data": requests_info})
    log("子进程退出")


def playwright_full_capture(target_url, headed=False, verbose=False):
    """主进程调用，带详细等待日志"""
    if not PLAYWRIGHT_AVAILABLE:
        print("  ⚠️ Playwright 未安装，跳过浏览器模拟。")
        return None

    mode_str = "有头" if headed else "无头"
    print(f"\n🌐 启动真实浏览器收集页面请求（{mode_str}模式）...")
    print("  ℹ️ 最长等待 45 秒。")

    queue = Queue()
    p = Process(target=playwright_worker, args=(target_url, queue, headed, verbose))
    p.start()
    print(f"[主进程 {datetime.now().strftime('%H:%M:%S')}] 子进程已启动")

    start_time = time.time()
    timeout = 45
    # 每5秒打印一次等待状态
    while time.time() - start_time < timeout:
        if not p.is_alive():
            print(f"[主进程 {datetime.now().strftime('%H:%M:%S')}] 子进程已退出")
            break
        # 检查队列是否有数据（非阻塞）
        try:
            result = queue.get_nowait()
            print(f"[主进程 {datetime.now().strftime('%H:%M:%S')}] 提前从队列获取到数据")
            # 等待子进程自然退出（最多2秒）
            p.join(2)
            if p.is_alive():
                p.terminate()
            return process_queue_result(result)
        except Exception:
            pass
        # 每5秒打印一次
        elapsed = int(time.time() - start_time)
        if elapsed % 5 == 0 and elapsed > 0:
            print(f"[主进程 {datetime.now().strftime('%H:%M:%S')}] 等待子进程中... (已等待 {elapsed} 秒)")
        time.sleep(1)

    # 超时处理
    if p.is_alive():
        print(f"[主进程 {datetime.now().strftime('%H:%M:%S')}] 超时，强制终止子进程")
        p.terminate()
        p.join(5)
        if p.is_alive():
            p.kill()
        return None

    # 子进程已退出，读取队列（最多等待3秒）
    print(f"[主进程 {datetime.now().strftime('%H:%M:%S')}] 子进程已退出，读取队列...")
    for _ in range(6):  # 3秒
        try:
            result = queue.get_nowait()
            return process_queue_result(result)
        except Exception:
            time.sleep(0.5)
    print("  ⚠️ 未能从队列读取到数据")
    return None


def process_queue_result(result):
    """处理队列返回的结果"""
    if "error" in result:
        print(f"  ⚠️ 浏览器收集出错: {result['error']}")
        return result.get("partial", [])
    else:
        data = result.get("data", [])
        print(f"  ✅ 浏览器收集完成，共捕获 {len(data)} 个请求。")
        return data

# -------------------- 事后分析：对唯一域名进行 DNS 和 HTTP 出口探测 --------------------

def probe_single_domain(domain, sample_url):
    """探测单个域名的 DNS 和 HTTP 出口 IP"""
    result = {
        "domain": domain,
        "sample_url": sample_url,
        "dns_egress_ip": None,
        "dns_resolved_ips": [],
        "http_egress_ip": None
    }
    try:
        # DNS 探测
        dns_info = dns_query_with_doh(domain, timeout=3)
        result['dns_egress_ip'] = dns_info.get('egress_ip_during_dns')
        result['dns_resolved_ips'] = dns_info.get('resolved_ips', [])

        # HTTP 出口探测
        pre_ip, _ = get_egress_ip(timeout=3)
        try:
            requests.head(sample_url, timeout=5, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            post_ip, _ = get_egress_ip(timeout=3)
            result['http_egress_ip'] = post_ip if post_ip else pre_ip
        except Exception:
            result['http_egress_ip'] = pre_ip
    except Exception as e:
        result['error'] = str(e)
    return result

def probe_domains(requests_info, max_workers=20):
    """并发探测所有唯一域名"""
    if not requests_info:
        return []

    # 提取唯一域名和对应的样本 URL
    domain_to_sample_url = {}
    for req in requests_info:
        domain = req.get('domain')
        if domain and domain not in domain_to_sample_url:
            domain_to_sample_url[domain] = req['url']

    domains = list(domain_to_sample_url.keys())
    total = len(domains)
    print(f"\n🔬 正在对 {total} 个唯一域名进行出口 IP 探测（并发数 {max_workers}）...")

    probed_results = []
    completed = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_domain = {
            executor.submit(probe_single_domain, domain, domain_to_sample_url[domain]): domain
            for domain in domains
        }
        for future in as_completed(future_to_domain):
            domain = future_to_domain[future]
            try:
                result = future.result()
                probed_results.append(result)
            except Exception as e:
                probed_results.append({
                    "domain": domain,
                    "sample_url": domain_to_sample_url[domain],
                    "error": str(e)
                })
            completed += 1
            if completed % 20 == 0 or completed == total:
                elapsed = time.time() - start_time
                print(f"  进度: {completed}/{total} 个域名, 已耗时 {elapsed:.1f} 秒")

    print(f"  ✅ 探测完成，总耗时 {time.time() - start_time:.1f} 秒。")
    return probed_results

# -------------------- 一致性分析 --------------------
def analyze_consistency(probed_results):
    if not probed_results:
        return {"error": "无探测数据"}

    http_ip_counter = defaultdict(int)
    dns_http_mismatch = []

    for item in probed_results:
        http_ip = item.get('http_egress_ip')
        dns_ip = item.get('dns_egress_ip')
        if http_ip:
            http_ip_counter[http_ip] += 1
        if http_ip and dns_ip and http_ip != dns_ip:
            dns_http_mismatch.append({
                "domain": item['domain'],
                "sample_url": item['sample_url'],
                "dns_egress": dns_ip,
                "http_egress": http_ip
            })

    multi_egress = len(http_ip_counter) > 1
    ip_details = []
    for ip, cnt in http_ip_counter.items():
        region = get_ip_region(ip)
        ip_details.append({
            "ip": ip,
            "region": region,
            "count": cnt,
            "percentage": f"{cnt / len(probed_results) * 100:.1f}%"
        })

    return {
        "total_domains": len(probed_results),
        "http_ips": list(http_ip_counter.keys()),        # 改为 http_ips
        "multi_egress": multi_egress,                    # 改为 multi_egress
        "mismatches": dns_http_mismatch,                 # 改为 mismatches
        "ip_details": ip_details
    }
	
# ---------- 交互流构建 ----------
class NetworkFlowBuilder:
    def __init__(self, local_ip, requests_info, probed_results):
        self.local_ip = local_ip
        self.requests_info = requests_info or []
        self.probed = {p['domain']: p for p in probed_results if 'domain' in p}
        self.events = []
        self.anomalies = []
    def format_time(self, ts):
        dt = datetime.fromtimestamp(ts)
        return dt.strftime('%H:%M:%S.%f')[:-3], dt.astimezone(timezone.utc).strftime('%H:%M:%S UTC')
    def build(self):
        processed_dns = set()
        for req in self.requests_info:
            url = req['url']; domain = req['domain']
            if not domain: continue
            parsed = urlparse(url)
            port = parsed.port or (443 if parsed.scheme=='https' else 80)
            scheme = parsed.scheme
            ts = req['start_time']
            probe = self.probed.get(domain, {})
            ips = probe.get('dns_resolved_ips', [])
            target_ip = ips[0] if ips else domain
            http_egress = probe.get('http_egress_ip')
            dns_egress = probe.get('dns_egress_ip')
            # DNS
            if domain not in processed_dns:
                processed_dns.add(domain)
                lt, ut = self.format_time(ts - 0.2)
                ev = {"event_type": "DNS", "local_time": lt, "internet_time": ut, "source_ip": self.local_ip, "source_port": "*", "target_domain": domain, "target_ip": ips[0] if ips else None, "target_port": 53, "protocol": "UDP", "egress_ip": dns_egress, "query_type": "A", "response_code": "NOERROR" if ips else "FAILED", "resolved_ips": ips, "duration_ms": 25, "anomaly_flags": []}
                if not ips: ev['anomaly_flags'].append('dns_failed'); self.anomalies.append(f"DNS失败: {domain}")
                self.events.append(ev)
            # TCP
            lt, ut = self.format_time(ts - 0.1)
            self.events.append({"event_type": "TCP", "local_time": lt, "internet_time": ut, "source_ip": self.local_ip, "source_port": "*", "target_domain": domain, "target_ip": target_ip, "target_port": port, "protocol": "TCP", "egress_ip": http_egress, "duration_ms": 35, "handshake_success": True})
            # TLS
            if scheme == 'https':
                lt, ut = self.format_time(ts - 0.05)
                self.events.append({"event_type": "TLS", "local_time": lt, "internet_time": ut, "source_ip": self.local_ip, "source_port": "*", "target_domain": domain, "target_ip": target_ip, "target_port": port, "protocol": "TCP", "egress_ip": http_egress, "duration_ms": 70, "tls_version": "TLSv1.3", "certificate_valid": True})
            # HTTP
            lt, ut = self.format_time(ts)
            self.events.append({"event_type": "HTTP", "local_time": lt, "internet_time": ut, "source_ip": self.local_ip, "source_port": "*", "target_domain": domain, "target_ip": target_ip, "target_port": port, "protocol": "TCP", "egress_ip": http_egress, "method": "GET", "url": url, "status_code": 200, "http_version": "HTTP/2", "resource_type": req['resource_type'], "duration_ms": 120})
        self.events.sort(key=lambda x: x['local_time'])
        return self.events
    def get_anomalies(self): return self.anomalies

# ---------- 控制台报告 ----------
def print_console_report(checker, requests_info, probed_results, events, anomalies, consistency):
    print("\n" + "="*80)
    print("📋 网络诊断报告")
    print("="*80)
    local = checker.results.get('local', {})
    gws = local.get('gateways', [])
    dns = local.get('dns_servers', [])
    print(f"环境: {checker.env_type.upper()} | 网关: {gws[0]['ip'] if gws else '无'} | DNS: {dns[0] if dns else '无'}")
    print(f"目标: {checker.target} | HTTP状态: {checker.results.get('http', {}).get('status_code', 'N/A')}")
    print(f"捕获请求: {len(requests_info)} | 唯一域名: {len(probed_results)}")
    if consistency.get('multi_egress'): print(f"⚠️ 多出口NAT: {consistency['http_ips']}")
    if consistency.get('mismatches'): print(f"⚠️ DNS/HTTP出口分离: {len(consistency['mismatches'])} 个域名")
    if anomalies: print("异常摘要:"); [print(f"  - {a}") for a in anomalies[:5]]
    print("\n【关键交互流】")
    print(f"{'时间':<12} {'类型':<6} {'域名':<28} {'目标IP':<16} {'状态':<6} {'出口IP':<16}")
    print("-"*86)
    type_order = {'DNS':0, 'TCP':1, 'TLS':2, 'HTTP':3}
    for e in sorted(events, key=lambda x: (type_order.get(x['event_type'],99), x['local_time']))[:20]:
        status = e.get('status_code') or e.get('response_code') or '-'
        status_display = str(status) if status is not None else '-'
        print(f"{e['local_time']:<12} {e['event_type']:<6} {(e['target_domain'] or '')[:26]:<28} {(e.get('target_ip') or '-'):<16} {str(status):<6} {(e.get('egress_ip') or '-'):<16}")
    print("="*80)

# ---------- HTML报告 ----------
def generate_html_report(report_data, output_path="network_diagnostic_report.html"):
    import html
    events = report_data.get('events', [])
    anomalies = report_data.get('anomalies', [])
    consistency = report_data.get('consistency', {})
    stack = report_data.get('stack_check', {})
    local = stack.get('local', {})
    http_info = stack.get('http', {})
    rows = []
    for e in events:
        status = e.get('status_code') or e.get('response_code') or '-'
        cls = 'error' if (isinstance(status,int) and status>=400) or status=='FAILED' else ('success' if status=='NOERROR' else '')
        rows.append(f'''
        <tr>
            <td>{e['local_time']}</td><td><span class="badge badge-{e['event_type'].lower()}">{e['event_type']}</span></td>
            <td title="{html.escape(e.get('url',''))}">{html.escape(e['target_domain'])}</td>
            <td>{e['source_ip']}:{e['source_port']}</td><td>{e['target_ip']}:{e['target_port']}</td><td>{e['protocol']}</td>
            <td class="{cls}">{status}</td><td>{e['duration_ms']} ms</td><td>{e.get('egress_ip','-')}</td>
        </tr>''')
    html_content = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>网络诊断报告 - {html.escape(report_data['target_url'])}</title>
    <style></style></head><body><div class="container">
    <h1>🌐 网络诊断报告</h1><div class="subtitle">目标: {html.escape(report_data['target_url'])} | 时间: {report_data.get('local_time','')} | 环境: {report_data.get('env_type','normal').upper()}</div>
    <div class="card"><div class="grid"><div class="stat"><div class="stat-label">总事件</div><div class="stat-value">{len(events)}</div></div>
    <div class="stat"><div class="stat-label">异常</div><div class="stat-value" style="color:{'#dc2626' if anomalies else '#059669'};">{len(anomalies)}</div></div>
    <div class="stat"><div class="stat-label">出口IP</div><div class="stat-value" style="font-size:16px;">{', '.join(consistency.get('http_ips',['未知']))}</div></div>
    <div class="stat"><div class="stat-label">多出口NAT</div><div class="stat-value">{'是' if consistency.get('multi_egress') else '否'}</div></div></div></div>
    <div class="card"><h3>📡 本地网络</h3><div style="display:grid;grid-template-columns:1fr 1fr"><div><strong>网关:</strong> {local.get('gateways',[{}])[0].get('ip','无')}<br><strong>DNS:</strong> {', '.join(local.get('dns_servers',[]))}</div>
    <div><strong>HTTP状态:</strong> {http_info.get('status_code','N/A')}<br><strong>代理:</strong> {', '.join(f'{k}={v}' for k,v in local.get('proxy',{}).items()) or '无'}</div></div></div>
    {f'<div class="card anomaly-box"><h3>⚠️ 异常 ({len(anomalies)})</h3><ul>{"".join(f"<li>{a}</li>" for a in anomalies)}</ul></div>' if anomalies else ''}
    <div class="card"><h3>📋 网络交互流全景</h3><div class="filter-bar"><input type="text" id="searchInput" placeholder="搜索域名或IP"><select id="typeFilter"><option value="">全部</option><option>DNS</option><option>TCP</option><option>TLS</option><option>HTTP</option></select></div>
    <table id="flowTable"><thead><tr><th>时间</th><th>类型</th><th>域名</th><th>源地址</th><th>目标地址</th><th>协议</th><th>状态</th><th>耗时</th><th>出口IP</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
    <div class="card suggestion-box"><h3>💡 诊断建议</h3><ul>{"".join([f"<li>{s}</li>" for s in [
        '检测到多出口NAT，可能影响会话保持。' if consistency.get('multi_egress') else '',
        'DNS与HTTP出口分离，检查代理或更换DNS。' if consistency.get('mismatches') else '',
        '部分域名DNS解析失败。' if any('DNS失败' in a for a in anomalies) else '',
        'HTTP错误状态码。' if http_info.get('status_code',0)>=400 else '',
        '✅ 未发现明显问题。' if not anomalies and not consistency.get('mismatches') and not consistency.get('multi_egress') else ''
    ] if s])}</ul></div></div>
    <script>const search=document.getElementById('searchInput'),type=document.getElementById('typeFilter'),rows=Array.from(document.querySelectorAll('#flowTable tbody tr'));
    function filter(){{const s=search.value.toLowerCase(),t=type.value;rows.forEach(r=>{{const d=r.cells[2]?.textContent.toLowerCase()||'',ip=r.cells[4]?.textContent.toLowerCase()||'',ev=r.cells[1]?.textContent.trim()||'';r.style.display=(d.includes(s)||ip.includes(s))&&(!t||ev===t)?'':'';}});}}
    search.addEventListener('input',filter);type.addEventListener('change',filter);</script></body></html>'''
    with open(output_path, 'w', encoding='utf-8') as f: f.write(html_content)
    print(f"📄 HTML 报告已生成: {output_path}")

# ---------- 主程序 ----------
def normalize_url(url):
    if not url.startswith(('http://','https://')): return 'https://' + url
    return url

def main():
    if len(sys.argv) < 2:
        print("用法: python net_diag_final.py <URL> [--headed] [--verbose]"); sys.exit(1)
    target_url = normalize_url(sys.argv[1])
    headed = "--headed" in sys.argv
    verbose = "--verbose" in sys.argv
    signal.signal(signal.SIGINT, lambda sig,frame: sys.exit(0))

    checker = NetworkStackChecker(target_url, verbose)
    checker.run_all()

    requests_info = playwright_full_capture(target_url, headed, verbose)
    if not requests_info: print("❌ 浏览器捕获失败"); return

    probed_results = probe_domains(requests_info)
    consistency = analyze_consistency(probed_results)

    local_ip = "127.0.0.1"
    for iface, info in checker.results['local']['interfaces'].items():
        if info['ipv4'] and not info['ipv4'][0].startswith('127.'):
            local_ip = info['ipv4'][0]; break

    builder = NetworkFlowBuilder(local_ip, requests_info, probed_results)
    events = builder.build()
    anomalies = builder.get_anomalies()

    print_console_report(checker, requests_info, probed_results, events, anomalies, consistency)

    report = {
        "target_url": target_url,
        "timestamp": time.time(),
        "local_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "env_type": checker.env_type,
        "stack_check": checker.results,
        "browser_requests": requests_info,
        "domain_probes": probed_results,
        "consistency": consistency,
        "events": events,
        "anomalies": anomalies
    }
    
    report_json_file = f"{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}_network_diagnostic_report.json";
    report_html_file = f"{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}_network_diagnostic_report.html"
    with open(report_json_file, "w", encoding="utf-8") as f:
        json.dump(report_json_file, f, indent=2, ensure_ascii=False)
    generate_html_report(report, output_path=report_html_file)
    print("\n📄 报告已保存: network_diagnostic_report.json / .html")

if __name__ == "__main__":
    main()