$ErrorActionPreference = "Stop"

Write-Host "=== Video Factory / ACE-Step 1.5 installer ===" -ForegroundColor Cyan
Write-Host "This installs the local free-first music engine. No paid service is configured."

$root = Join-Path $env:USERPROFILE "VideoFactoryTools"
$ace = Join-Path $root "ACE-Step-1.5"

New-Item -ItemType Directory -Force -Path $root | Out-Null
Set-Location $root

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git が見つかりません。Git for Windows を先にインストールしてください。"
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv をインストールします..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

if (-not (Test-Path $ace)) {
    git clone https://github.com/ACE-Step/ACE-Step-1.5.git $ace
} else {
    Write-Host "既存のACE-Stepを使用します: $ace"
}

Set-Location $ace
uv sync

Write-Host ""
Write-Host "インストール完了。" -ForegroundColor Green
Write-Host "APIを起動するには次を実行:"
Write-Host "  uv run acestep-api"
Write-Host ""
Write-Host "API: http://127.0.0.1:8001"
Write-Host "初回起動ではモデルのダウンロードが行われます。"
