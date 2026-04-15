# sdwan_analyzer/modules/proxy_check.py (建议新建或添加到现有系统诊断模块)
import winreg
import socket

def check_windows_proxy() -> dict:
    """
    检测 Windows 系统代理设置
    :return: {
        "enabled": bool, 
        "server": str, 
        "bypass_list": str,
        "message": str
    }
    """
    result = {
        "enabled": False,
        "server": "",
        "bypass_list": "",
        "message": "未启用系统代理"
    }
    
    try:
        # 打开注册表键
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        )
        
        # 获取 ProxyEnable 值 (1 为启用, 0 为禁用)
        proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        
        if proxy_enable:
            result["enabled"] = True
            try:
                proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
                result["server"] = proxy_server
            except FileNotFoundError:
                result["server"] = "未知"
            
            try:
                bypass_list, _ = winreg.QueryValueEx(key, "ProxyOverride")
                result["bypass_list"] = bypass_list
            except FileNotFoundError:
                result["bypass_list"] = ""
                
            result["message"] = f"系统代理已启用: {result['server']}"
        
        winreg.CloseKey(key)
        
    except Exception as e:
        result["message"] = f"检测代理设置失败: {str(e)}"
        
    return result