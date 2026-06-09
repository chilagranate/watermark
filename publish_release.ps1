$token = $env:GITHUB_TOKEN
if (-not $token) {
    Write-Host "ERROR: GITHUB_TOKEN no está configurado. Ejecutá: `$env:GITHUB_TOKEN = 'tu_token'" -ForegroundColor Red
    exit 1
}

$headers = @{
    Authorization = "Bearer $token"
    Accept = "application/vnd.github+json"
}

$repo = "chilagranate/watermark"
$baseUrl = "https://api.github.com/repos/$repo"
$artifactUrl = "$baseUrl/actions/runs/27168009108/artifacts"

Write-Host "Bajando artifacts..." -ForegroundColor Cyan
$artifacts = Invoke-RestMethod -Uri $artifactUrl -Headers $headers
$outDir = "release_files"
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

foreach ($a in $artifacts.artifacts) {
    $name = $a.name
    Write-Host "  Descargando $name..."
    $dlUrl = $a.archive_download_url
    $zipPath = "$outDir\$name.zip"
    Invoke-WebRequest -Uri $dlUrl -Headers $headers -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath "$outDir\$name" -Force
    Remove-Item $zipPath
}

Write-Host "Creando release v1.0.0..." -ForegroundColor Cyan
$releaseBody = @{
    tag_name = "v1.0.0"
    name = "Watermark v1.0.0"
    body = @"
## Watermark App v1.0.0

Marcado digital invisible con VideoSeal para imágenes y video.

### Funcionalidades
- Fingerprint de 256 bits resistente a screenshots y JPEG
- Identificación multi-comprador (misma foto, fingerprints distintos)
- GUI oscura con drag & drop, barra de progreso con ETA
- Lectura de marcas con búsqueda local + servidor monitor
- Soporte PWA para iPhone vía QR
- Sync offline con cola de envío

### Instalación
- **Mac**: descargar `.dmg`, arrastrar a Aplicaciones, abrir con clic derecho
- **Windows**: descargar `.exe`, ejecutar

### Requisitos
- macOS 14+ (Apple Silicon) o Windows 10+ x64
- 4 GB RAM recomendado
"@
    draft = $false
    prerelease = $false
}

$release = Invoke-RestMethod -Uri "$baseUrl/releases" -Method POST -Headers $headers -Body ($releaseBody | ConvertTo-Json)

Write-Host "Release creado: $($release.html_url)" -ForegroundColor Green

Write-Host "Subiendo archivos..." -ForegroundColor Cyan
foreach ($a in $artifacts.artifacts) {
    $name = $a.name
    $artifactDir = "$outDir\$name"
    $files = Get-ChildItem -Path $artifactDir -File
    foreach ($file in $files) {
        $uploadUrl = $release.upload_url -replace '\{[\w,]+\}', ''
        $uploadUrl = "$uploadUrl`?name=$($file.Name)"
        Write-Host "  Subiendo $($file.Name) ($([math]::Round($file.Length/1MB,1)) MB)..."
        Invoke-RestMethod -Uri $uploadUrl -Method POST -Headers @{
            Authorization = "Bearer $token"
            Accept = "application/vnd.github+json"
            "Content-Type" = "application/octet-stream"
        } -InFile $file.FullName
    }
}

Write-Host "`nListo. Release: $($release.html_url)" -ForegroundColor Green
Write-Host "Archivos locales: $outDir\" -ForegroundColor Yellow
