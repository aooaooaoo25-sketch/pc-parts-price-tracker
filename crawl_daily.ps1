# 每日 PTT 自動爬取（供 Windows 工作排程器呼叫）
# 手動測試： powershell -ExecutionPolicy Bypass -File .\crawl_daily.ps1
# 預設只爬 gpu cpu（PTT hardwaresale 量最多的分類）；要全部改成 ""（空字串）即可。
$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
Set-Location -LiteralPath $PSScriptRoot

$cats = "gpu cpu"
$logDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$log = Join-Path $logDir ("crawl_{0}.log" -f (Get-Date -Format "yyyyMMdd"))

"==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 開始 PTT 爬取 ($cats) ====" |
    Out-File -FilePath $log -Append -Encoding utf8
python pc_scraper_backend.py $cats.Split(" ") *>> $log
"==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 完成 ====`n" |
    Out-File -FilePath $log -Append -Encoding utf8
