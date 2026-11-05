# 检查环境并打开后端、前端两个窗口。不创建数据库，不初始化账号，不删除数据。
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
$Database = Join-Path $Backend "data\studymate.db"
$EnvFile = Join-Path $Backend ".env"
$NodeModules = Join-Path $Root "frontend\node_modules"

function Get-LanIPv4 {
    $configs = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" }
    foreach ($item in $configs) {
        foreach ($addr in @($item.IPv4Address)) {
            $ip = $addr.IPAddress
            if ($ip -and $ip -notlike "127.*" -and $ip -notlike "169.254.*") {
                return $ip
            }
        }
    }
    return $null
}

if (-not (Test-Path $Python)) {
    Write-Host "没有找到 Python 虚拟环境：$Python"
    exit 1
}
if (-not (Test-Path $EnvFile)) {
    Write-Host "没有找到 backend\.env。"
    exit 1
}
if (-not (Test-Path $Database)) {
    Write-Host "没有找到正式数据库：$Database"
    exit 1
}
if (-not (Test-Path $NodeModules)) {
    Write-Host "没有找到 frontend\node_modules。"
    exit 1
}

try {
    $backendBusy = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction Stop
} catch {
    $backendBusy = $null
}
try {
    $frontendBusy = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction Stop
} catch {
    $frontendBusy = $null
}
if ($backendBusy -or $frontendBusy) {
    Write-Host "8000 或 5173 端口已被占用。请先关闭正在运行的 StudyMate，再重新启动。"
    exit 1
}

$ruleName = "StudyMate LAN 5173"
$rule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($rule) {
    Write-Host "防火墙已允许专用网络访问 TCP 5173，来源限于本机所在子网。"
} else {
    try {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5173 -Profile Private -RemoteAddress LocalSubnet -ErrorAction Stop | Out-Null
        Write-Host "已添加防火墙规则：专用网络、TCP 5173、来源为本机所在子网。"
    } catch {
        Write-Host "未能添加防火墙规则。请用管理员身份运行本脚本后再让其他设备访问。"
        Write-Host $_.Exception.Message
    }
}

$lan = Get-LanIPv4
Write-Host "后端将监听 0.0.0.0:8000，防火墙不开放这个端口。"
Write-Host "本机访问：http://127.0.0.1:5173/"
if ($lan) {
    Write-Host "局域网访问：http://${lan}:5173/"
} else {
    Write-Host "没有检测到可用于局域网的 IPv4 地址。"
}

Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "start_backend.ps1"))
Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "start_frontend.ps1"))