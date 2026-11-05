# 启动 StudyMate 后端。不创建数据库，不初始化账号，不删除数据。
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
$Database = Join-Path $Backend "data\studymate.db"
$EnvFile = Join-Path $Backend ".env"

if (-not (Test-Path $Python)) {
    Write-Host "没有找到 Python 虚拟环境：$Python"
    exit 1
}
if (-not (Test-Path $EnvFile)) {
    Write-Host "没有找到 backend\.env。请按 backend\.env.example 准备配置。"
    Write-Host "不要删除或重建现有数据库。"
    exit 1
}
if (-not (Test-Path $Database)) {
    Write-Host "没有找到正式数据库：$Database"
    Write-Host "启动脚本不会创建或清空数据库。"
    exit 1
}

try {
    $listen = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction Stop
} catch {
    $listen = $null
}
if ($listen) {
    Write-Host "端口 8000 已被占用，后端没有启动。"
    exit 1
}

Remove-Item Env:DATABASE_PATH -ErrorAction SilentlyContinue
Set-Location $Backend
Write-Host "后端监听 0.0.0.0:8000"
Write-Host "数据库：$Database"
Write-Host "局域网成员通过前端访问，不直接连接 8000 端口。"
& $Python -m uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000