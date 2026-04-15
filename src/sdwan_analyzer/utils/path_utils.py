import os
import sys

def get_resource_path(relative_path):
    """
    获取资源的绝对路径，兼容开发环境和 PyInstaller 打包后的环境
    :param relative_path: 相对于项目根目录或 _MEIPASS 的路径
    :return: 绝对路径
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 创建临时文件夹，并将路径存储在 _MEIPASS 变量中
        base_path = sys._MEIPASS
    else:
        # 正常运行时的路径 (开发环境)
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)