import subprocess

def check_dns_working() -> bool:
    """DNS 能否正常解析公共域名"""
    domains = ["www.baidu.com", "www.google.com", "aliyun.com"]
    for d in domains:
        try:
            res = subprocess.run(
                ["nslookup", d], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            if res.returncode == 0:
                return True
        except:
            continue
    return False