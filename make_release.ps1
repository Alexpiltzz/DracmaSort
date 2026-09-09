param(
    [string]$Name = "DracmaSort"
)

$ErrorActionPreference = "Stop"

# --- Ler versão do pyproject.toml ---
$pyproject = Get-Content -Raw "pyproject.toml"
if ($pyproject -match 'version\s*=\s*"([^"]+)"') {
    $version = $Matches[1]
} else {
    Write-Error "Não foi possível extrair a versão de pyproject.toml"
    exit 1
}
$tag = "v$version"
Write-Output "Versão: $version (tag: $tag)"

# --- Resolver token (escrita — APENAS DEV) ---
$token = $env:GITHUB_RELEASE_TOKEN
if (-not $token) {
    Write-Output "GITHUB_RELEASE_TOKEN não definido. Tentando GITHUB_TOKEN (legado)..."
    $token = $env:GITHUB_TOKEN
}
if (-not $token) {
    Write-Output "Nenhum token no ambiente. Tentando git credential fill..."
    $credInput = "protocol=https`nhost=github.com`n"
    $cred = $credInput | git credential fill 2>$null
    $token = ($cred | Select-String '^password=').ToString().Substring(9)
}
if (-not $token) {
    Write-Error "Nenhum token disponível. Defina GITHUB_RELEASE_TOKEN (escrita) ou configure git credentials."
    exit 1
}

# --- Gerar changelog ---
$changelog = ""
try {
    $commits = git log --oneline "$tag..HEAD" 2>$null
    if ($LASTEXITCODE -eq 0 -and $commits) {
        $changelog = ($commits | ForEach-Object { "- $_" }) -join "`n"
        Write-Output "  $($commits.Count) commit(s) desde a última tag."
    }
} catch {
    Write-Output "  Não foi possível gerar changelog."
}

# --- Body da release ---
$body = @{
    tag_name         = $tag
    name             = $tag
    target_commitish = "main"
    body             = @"
## DracmaSort $tag

### Alterações

$changelog

### Executável

Baixe o **$Name.exe** e execute diretamente no Windows.
"@
    draft            = $false
    prerelease       = $false
} | ConvertTo-Json -Depth 5

# --- Criar release ---
$repo = "Alexpiltzz/Giveaways_Tools"
Write-Output "Criando release $tag ..."
$release = Invoke-RestMethod -Method Post `
    -Uri "https://api.github.com/repos/$repo/releases" `
    -Headers @{ Authorization = "token $token"; Accept = "application/vnd.github+json" } `
    -ContentType "application/json" -Body $body

# --- Upload do executável ---
$releaseId = $release.id
$uploadUrl = "https://uploads.github.com/repos/$repo/releases/$releaseId/assets?name=$Name.exe"
$exe = "dist\$Name.exe"
if (-not (Test-Path $exe)) {
    Write-Error "Executável não encontrado: $exe"
    exit 1
}
$sizeMB = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Output "Uploadando $Name.exe ($sizeMB MB)..."
$asset = Invoke-RestMethod -Method Post `
    -Uri $uploadUrl `
    -Headers @{ Authorization = "token $token"; Accept = "application/vnd.github+json" } `
    -ContentType "application/octet-stream" -InFile $exe

Write-Output ""
Write-Output "Release criada com sucesso!"
Write-Output "  RELEASE_URL=$($release.html_url)"
Write-Output "  ASSET_URL=$($asset.browser_download_url)"
