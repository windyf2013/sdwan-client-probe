# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/sdwan_analyzer/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 将必要的非代码资源包含进去
        # ('src/sdwan_analyzer/config/default_config.yaml', 'sdwan_analyzer/config'),
        # ('docs/my-rules.md', 'docs'), 
        # 注意：路径需根据实际资源位置调整，确保 get_resource_path 能找到
    ],
    hiddenimports=[
        # 添加可能漏掉的隐式导入
        'pkg_resources.py2_warn', # 常见警告修复
        'sdwan_analyzer.modules.app_probe',
        'sdwan_analyzer.modules.sdwan_check',
        'sdwan_analyzer.modules.system_diagnose',
        'sdwan_analyzer.modules.net_diagnostic',
        # 如果使用了 scapy 或其他复杂库，添加其子模块
        # 'scapy.layers.inet',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SDWAN_Analyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 如果是CLI工具设为True，如果是GUI设为False
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None, # 可以指定 .ico 文件路径
)