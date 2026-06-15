# 每日 PTT 自動爬取（供 Windows 工作排程器呼叫）
# 手動測試： powershell -ExecutionPolicy Bypass -File .\crawl_daily.ps1
# 爬五大分類；可改 $cats（空白分隔）縮小範圍。RAM 為規格帶＋雜訊過濾，HDD/SSD 為品牌+容量。
$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
Set-Location -LiteralPath $PSScriptRoot

$cats = "gpu cpu ram ssd hdd"
$logDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$log = Join-Path $logDir ("crawl_{0}.log" -f (Get-Date -Format "yyyyMMdd"))

"==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 開始 PTT 爬取 ($cats) ====" |
    Out-File -FilePath $log -Append -Encoding utf8
python pc_scraper_backend.py $cats.Split(" ") *>> $log

# Auto-deploy the static site after crawl: only when CLOUDFLARE_API_TOKEN is set (non-interactive);
# otherwise skip (crawl unaffected). One-time setup in DEPLOY.md section D.
if ($env:CLOUDFLARE_API_TOKEN) {
    "==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') deploy Cloudflare Pages ====" |
        Out-File -FilePath $log -Append -Encoding utf8
    try { & "$PSScriptRoot\deploy.ps1" -ProjectName pc-price-tracker *>> $log }
    catch { "deploy failed: $_" | Out-File -FilePath $log -Append -Encoding utf8 }
} else {
    "(CLOUDFLARE_API_TOKEN not set, skip auto-deploy)" |
        Out-File -FilePath $log -Append -Encoding utf8
}

"==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 完成 ====`n" |
    Out-File -FilePath $log -Append -Encoding utf8
