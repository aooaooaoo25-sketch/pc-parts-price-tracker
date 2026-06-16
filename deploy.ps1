# Deploy the static site to Cloudflare Pages.
#   Regenerate report.json -> bundle dist/ (index.html + report.json + robots + sitemap) -> wrangler upload.
# Comments kept ASCII on purpose: Windows PowerShell 5.1 misreads UTF-8-without-BOM .ps1 files.
# Full walkthrough (Chinese) is in DEPLOY.md.
#
# Usage:
#   .\deploy.ps1 -BuildOnly                                  # only build dist/ (drag to Dashboard)
#   .\deploy.ps1 -ProjectName pc-price-tracker               # build + deploy via wrangler
#   .\deploy.ps1 -ProjectName pc-price-tracker -Domain pc-price-tracker.pages.dev
param(
    [string]$ProjectName = "pc-price-tracker",
    [string]$Domain = $env:SITE_DOMAIN,   # default from SITE_DOMAIN env (so daily deploys keep the domain)
    [switch]$BuildOnly
)
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
Set-Location -LiteralPath $PSScriptRoot

Write-Host "==> 1/3 generate report.json"
python tools/export_report.py

Write-Host "==> 2/3 bundle dist/"
$dist = Join-Path $PSScriptRoot "dist"
if (Test-Path $dist) { Remove-Item $dist -Recurse -Force }
New-Item -ItemType Directory -Path $dist | Out-Null
Copy-Item -LiteralPath index.html, report.json, robots.txt, sitemap.xml, og.png -Destination $dist

if ($Domain) {
    foreach ($f in @("robots.txt", "sitemap.xml")) {
        $p = Join-Path $dist $f
        (Get-Content -LiteralPath $p -Raw) -replace "REPLACE-WITH-YOUR-DOMAIN", $Domain |
            Set-Content -LiteralPath $p -Encoding utf8
    }
    Write-Host "    replaced domain placeholder with $Domain"
}

if ($BuildOnly) {
    Write-Host "==> done (BuildOnly). Drag the dist\ folder into Cloudflare Pages Direct Upload."
    return
}

Write-Host "==> 3/3 wrangler deploy to Cloudflare Pages (project: $ProjectName)"
# Requires Node + wrangler, and either 'wrangler login' or CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID.
npx wrangler pages deploy $dist --project-name=$ProjectName
