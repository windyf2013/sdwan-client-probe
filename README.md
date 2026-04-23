# 1. 清理之前的构建缓存（重要，避免旧配置干扰）
rmdir /s /q build
rmdir /s /q dist

# 2. 重新打包
pyinstaller RC-sdwan-client-probe_v1.1.spec