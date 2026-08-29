$ErrorActionPreference = "Stop"

$credInput = "protocol=https`nhost=github.com`n"
$cred = $credInput | git credential fill 2>$null
$token = ($cred | Select-String '^password=').ToString().Substring(9)

$repo = "Alexpiltzz/Giveaways_Tools"
$version = "0.1.1"
$tag = "v$version"

$body = @{
    tag_name         = $tag
    name             = $tag
    target_commitish = "main"
    body             = @"
## DracmaSort v$version

Primeira release do **Giveaways Tools** - DracmaSort.

### Destaques
- Gerador de códigos únicos de sorteio a partir de planilhas de participantes
- Interface grafica (GUI)
- Envio de e-mails via Outlook/Office 365
- Validacao de e-mails e teste SMTP
- Fluxo interativo completo

### Executavel
- DracmaSort.exe - versao grafica compilada (Windows)

### Uso
Baixe o DracmaSort.exe e execute diretamente no Windows.
"@
    draft            = $false
    prerelease       = $false
} | ConvertTo-Json -Depth 5

Write-Output "Creating release $tag ..."
$release = Invoke-RestMethod -Method Post `
    -Uri "https://api.github.com/repos/$repo/releases" `
    -Headers @{ Authorization = "token $token"; Accept = "application/vnd.github+json" } `
    -ContentType "application/json" -Body $body

$releaseId = $release.id
$uploadUrl = "https://uploads.github.com/repos/$repo/releases/$releaseId/assets?name=DracmaSort.exe"
$exe = "D:\Repository\Python\Giveaways_Tools\dist\DracmaSort.exe"
Write-Output "Uploading DracmaSort.exe ($([math]::Round((Get-Item $exe).Length/1MB,1)) MB) ..."
$asset = Invoke-RestMethod -Method Post `
    -Uri $uploadUrl `
    -Headers @{ Authorization = "token $token"; Accept = "application/vnd.github+json" } `
    -ContentType "application/octet-stream" -InFile $exe

Write-Output "ASSET_URL=$($asset.browser_download_url)"
Write-Output "RELEASE_URL=$($release.html_url)"
