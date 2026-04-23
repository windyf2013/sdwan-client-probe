# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# 1. 定义需要包含的数据文件 (configs, templates, etc.)
a = Analysis(
    ['src/sdwan_analyzer/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('configs/default.yaml', 'configs'),
        # 如果有其他静态资源，如报告模板，在此添加
        # ('src/sdwan_analyzer/templates/*.html', 'templates'),
    ],
    hiddenimports=[
        # PyInstaller 可能无法自动检测到的动态导入
        'dns.resolver',
        'dns.rdtypes',
        'dns.rdtypes.IN',
        'dns.rdtypes.ANY',
        'ping3',
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        # 如果使用了 pydantic v2，可能需要以下隐藏导入
        'pydantic',
        'pydantic_core',
        'pydantic.fields',
        'pydantic.json_schema',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # --- 重点优化：排除未使用或体积巨大的库 ---
        
        # 1. 数据分析库 (除非明确用于实时诊断，否则排除)
        'pandas',
        'numpy',
        'pyarrow',
        
        # 2. 地理位置库 (若不使用本地 GeoIP 数据库查询，排除)
        'geoip2',
        'maxminddb',
        
        # 3. 浏览器自动化 (若不使用 Playwright 进行 DOM 捕获，排除)
        'playwright',
        'greenlet',
        
        # 4. 开发与测试工具 (绝对排除)
        'pytest',
        '_pytest',
        'unittest',
        'nose',
        'ruff',
        'mypy',
        'pre_commit',
        'flake8',
        'coverage',
        
        # 5. 其他常见但可能未使用的重型库
        'matplotlib',
        'scipy',
        'sklearn',
        'tensorflow',
        'torch',
        
        # 6. GUI 框架 (如果是 CLI 工具，排除所有 GUI 后端)
        'tkinter',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'wx',
        
        # 7. 文档生成
        'sphinx',
        'docutils',
        'docs', 
        'spec', 
        'tests'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 2. 打包为单文件 (onefile) 或 单目录 (onedir)
# onedir 启动速度快，体积小(共享系统dll)，适合分发
# onefile 只有一个exe，但启动慢(解压)，体积大
# 这里推荐 onedir 以获得最佳性能和较小磁盘占用，若必须单文件则改为 'onefile'
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='瑞斯康达跨境FAQ小助手',
    debug=False,
    bootloader_ignore_signals=False,
    upx=True,    # 使用 UPX 压缩 (需安装 upx)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True, # 保留控制台窗口以便查看日志
    disable_windowed_traceback=False,
    icon='icon.ico',
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# 如果使用 onedir 模式，可以使用 Collate 或直接构建 COLLECT
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    upx=True,
    upx_exclude=[],
    name='瑞斯康达跨境FAQ助手',
    icon='icon.ico',
)