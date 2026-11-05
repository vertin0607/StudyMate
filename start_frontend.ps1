# 启动 StudyMate 前端。浏览器通过本页面的 /api 访问后端。
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Frontend = Join-Path $Root "frontend"
$NodeModules = Join-Path $Frontend "node_modules"

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

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "没有找到 npm。请先安装 Node.js。"
    exit 1
}
if (-not (Test-Path $NodeModules)) {
    Write-Host "没有找到 frontend\node_modules。请先在 frontend 目录执行 npm install。"
    exit 1
}

try {
    $listen = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction Stop
} catch {
    $listen = $null
}
if ($listen) {
    Write-Host "端口 5173 已被占用，前端没有启动。"
    exit 1
}

$lan = Get-LanIPv4
Set-Location $Frontend
Write-Host "本机访问：http://127.0.0.1:5173/"
if ($lan) {
    Write-Host "局域网访问：http://${lan}:5173/"
} else {
    Write-Host "没有检测到可用于局域网的 IPv4 地址。"
}
npm run dev