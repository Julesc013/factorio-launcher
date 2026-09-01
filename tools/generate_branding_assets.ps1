# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

[CmdletBinding()]
param(
    [string]$Source,
    [string]$OutputRoot
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($Source)) {
    $Source = Join-Path $repositoryRoot "content\factorio\ui\branding\master\facman-provisional.png"
}
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $repositoryRoot "content\factorio\ui\branding"
}

$sourceItem = Get-Item -LiteralPath $Source -Force
if ($sourceItem.PSIsContainer -or $sourceItem.LinkType) {
    throw "Branding source must be a regular, non-link file: $Source"
}
$sourceDigest = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourceItem.FullName).Hash.ToLowerInvariant()
$expectedSourceDigest = "5001177903f03342630db1adced28a0ebc7dd03f16ffe791f1921cfdbeed6ed8"
if ($sourceDigest -ne $expectedSourceDigest) {
    throw "Branding source digest differs from reviewed custody: $sourceDigest"
}

$outputRootPath = [IO.Path]::GetFullPath($OutputRoot)
[IO.Directory]::CreateDirectory($outputRootPath) | Out-Null

function New-Directory([string]$Path) {
    [IO.Directory]::CreateDirectory($Path) | Out-Null
}

function Convert-ToPngBytes([System.Drawing.Image]$Image, [int]$Size) {
    $bitmap = New-Object System.Drawing.Bitmap($Size, $Size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $bitmap.SetResolution(96.0, 96.0)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.Clear([System.Drawing.Color]::Transparent)
        $graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
        $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
        $attributes = New-Object System.Drawing.Imaging.ImageAttributes
        try {
            $attributes.SetWrapMode([System.Drawing.Drawing2D.WrapMode]::TileFlipXY)
            $destination = New-Object System.Drawing.Rectangle(0, 0, $Size, $Size)
            $graphics.DrawImage(
                $Image,
                $destination,
                0,
                0,
                $Image.Width,
                $Image.Height,
                [System.Drawing.GraphicsUnit]::Pixel,
                $attributes)
        }
        finally {
            $attributes.Dispose()
        }
        $stream = New-Object IO.MemoryStream
        try {
            $bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
            return [byte[]]$stream.ToArray()
        }
        finally {
            $stream.Dispose()
        }
    }
    finally {
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

function Write-U16Little([IO.BinaryWriter]$Writer, [int]$Value) {
    $Writer.Write([uint16]$Value)
}

function Write-U32Little([IO.BinaryWriter]$Writer, [long]$Value) {
    $Writer.Write([uint32]$Value)
}

function Write-U32Big([IO.Stream]$Stream, [long]$Value) {
    $bytes = [BitConverter]::GetBytes([uint32]$Value)
    if ([BitConverter]::IsLittleEndian) { [Array]::Reverse($bytes) }
    $Stream.Write($bytes, 0, $bytes.Length)
}

function Write-Ico([System.Drawing.Image]$Image, [string]$Path) {
    $sizes = @(16, 24, 32, 48, 64, 72, 96, 128, 256)
    $frames = @()
    foreach ($size in $sizes) {
        $frames += ,(Convert-ToPngBytes $Image $size)
    }
    $stream = New-Object IO.MemoryStream
    $writer = New-Object IO.BinaryWriter($stream)
    try {
        Write-U16Little $writer 0
        Write-U16Little $writer 1
        Write-U16Little $writer $sizes.Count
        $offset = 6 + (16 * $sizes.Count)
        for ($index = 0; $index -lt $sizes.Count; $index++) {
            $size = $sizes[$index]
            $writer.Write([byte]($(if ($size -eq 256) { 0 } else { $size })))
            $writer.Write([byte]($(if ($size -eq 256) { 0 } else { $size })))
            $writer.Write([byte]0)
            $writer.Write([byte]0)
            Write-U16Little $writer 1
            Write-U16Little $writer 32
            Write-U32Little $writer $frames[$index].Length
            Write-U32Little $writer $offset
            $offset += $frames[$index].Length
        }
        foreach ($frame in $frames) {
            $writer.Write([byte[]]$frame)
        }
        $writer.Flush()
        New-Directory ([IO.Path]::GetDirectoryName($Path))
        [IO.File]::WriteAllBytes($Path, $stream.ToArray())
    }
    finally {
        $writer.Dispose()
        $stream.Dispose()
    }
}

function Write-Icns([System.Drawing.Image]$Image, [string]$Path) {
    $specifications = @(
        @{ Type = "icp4"; Size = 16 },
        @{ Type = "icp5"; Size = 32 },
        @{ Type = "icp6"; Size = 64 },
        @{ Type = "ic07"; Size = 128 },
        @{ Type = "ic08"; Size = 256 },
        @{ Type = "ic09"; Size = 512 },
        @{ Type = "ic10"; Size = 1024 }
    )
    $entries = @()
    $totalLength = 8
    foreach ($specification in $specifications) {
        $payload = Convert-ToPngBytes $Image $specification.Size
        $entries += ,@{ Type = $specification.Type; Payload = $payload }
        $totalLength += 8 + $payload.Length
    }
    $stream = New-Object IO.MemoryStream
    try {
        $magic = [Text.Encoding]::ASCII.GetBytes("icns")
        $stream.Write($magic, 0, $magic.Length)
        Write-U32Big $stream $totalLength
        foreach ($entry in $entries) {
            $type = [Text.Encoding]::ASCII.GetBytes($entry.Type)
            $stream.Write($type, 0, $type.Length)
            Write-U32Big $stream (8 + $entry.Payload.Length)
            $stream.Write($entry.Payload, 0, $entry.Payload.Length)
        }
        New-Directory ([IO.Path]::GetDirectoryName($Path))
        [IO.File]::WriteAllBytes($Path, $stream.ToArray())
    }
    finally {
        $stream.Dispose()
    }
}

function Write-ContactSheet([System.Drawing.Image]$Image, [string]$Path) {
    $sizes = @(16, 24, 32, 48, 64, 96, 128, 256)
    $sheet = New-Object System.Drawing.Bitmap(1280, 720, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $sheet.SetResolution(96.0, 96.0)
    $graphics = [System.Drawing.Graphics]::FromImage($sheet)
    $titleFont = New-Object System.Drawing.Font("Segoe UI", 20, [System.Drawing.FontStyle]::Bold)
    $labelFont = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Regular)
    try {
        $graphics.Clear([System.Drawing.Color]::FromArgb(255, 245, 245, 245))
        $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
        $graphics.DrawString("FacMan provisional branding contact sheet", $titleFont, [System.Drawing.Brushes]::Black, 28, 20)
        $graphics.DrawString("Operator-supplied source; final optical, trademark, and accessibility judgment remains human.", $labelFont, [System.Drawing.Brushes]::DimGray, 30, 58)
        for ($index = 0; $index -lt $sizes.Count; $index++) {
            $column = $index % 4
            $row = [Math]::Floor($index / 4)
            $cellX = 30 + (305 * $column)
            $cellY = 100 + (290 * $row)
            $graphics.FillRectangle([System.Drawing.Brushes]::White, $cellX, $cellY, 275, 250)
            $graphics.DrawRectangle([System.Drawing.Pens]::LightGray, $cellX, $cellY, 275, 250)
            for ($checkerY = 0; $checkerY -lt 210; $checkerY += 16) {
                for ($checkerX = 0; $checkerX -lt 250; $checkerX += 16) {
                    $brush = if ((($checkerX / 16) + ($checkerY / 16)) % 2 -eq 0) {
                        [System.Drawing.Brushes]::White
                    } else {
                        [System.Drawing.Brushes]::Gainsboro
                    }
                    $graphics.FillRectangle($brush, $cellX + 12 + $checkerX, $cellY + 12 + $checkerY, 16, 16)
                }
            }
            $previewSize = [Math]::Min($sizes[$index], 210)
            $previewX = $cellX + [Math]::Floor((275 - $previewSize) / 2)
            $previewY = $cellY + 12 + [Math]::Floor((210 - $previewSize) / 2)
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
            if ($sizes[$index] -gt 64) {
                $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            }
            $graphics.DrawImage($Image, $previewX, $previewY, $previewSize, $previewSize)
            $graphics.DrawString("$($sizes[$index]) x $($sizes[$index])", $labelFont, [System.Drawing.Brushes]::Black, $cellX + 12, $cellY + 224)
        }
        New-Directory ([IO.Path]::GetDirectoryName($Path))
        $sheet.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        $labelFont.Dispose()
        $titleFont.Dispose()
        $graphics.Dispose()
        $sheet.Dispose()
    }
}

$image = [System.Drawing.Image]::FromFile($sourceItem.FullName)
try {
    if ($image.Width -ne 1254 -or $image.Height -ne 1254) {
        throw "Reviewed source dimensions must remain 1254 x 1254"
    }
    $windowsIcon = Join-Path $repositoryRoot "apps\gui\windows\winforms\branding\FacMan.ico"
    $macIcon = Join-Path $repositoryRoot "apps\gui\macos\appkit\branding\FacMan.icns"
    Write-Ico $image $windowsIcon
    Write-Icns $image $macIcon

    $linuxSizes = @(16, 24, 32, 48, 64, 96, 128, 192, 256, 512)
    foreach ($size in $linuxSizes) {
        $directory = Join-Path $repositoryRoot "apps\gui\linux\gtk\icons\hicolor\${size}x${size}\apps"
        New-Directory $directory
        $destination = Join-Path $directory "io.github.julesc013.facman.png"
        [IO.File]::WriteAllBytes($destination, (Convert-ToPngBytes $image $size))
    }
    Write-ContactSheet $image (Join-Path $outputRootPath "review\contact-sheet.png")
}
finally {
    $image.Dispose()
}

$outputs = @(
    [ordered]@{
        path = "apps/gui/windows/winforms/branding/FacMan.ico"
        media_type = "image/vnd.microsoft.icon"
        pixel_sizes = @(16, 24, 32, 48, 64, 72, 96, 128, 256)
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $repositoryRoot "apps\gui\windows\winforms\branding\FacMan.ico")).Hash.ToLowerInvariant()
    },
    [ordered]@{
        path = "apps/gui/macos/appkit/branding/FacMan.icns"
        media_type = "image/icns"
        pixel_sizes = @(16, 32, 64, 128, 256, 512, 1024)
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $repositoryRoot "apps\gui\macos\appkit\branding\FacMan.icns")).Hash.ToLowerInvariant()
    }
)
foreach ($size in $linuxSizes) {
    $relative = "apps/gui/linux/gtk/icons/hicolor/${size}x${size}/apps/io.github.julesc013.facman.png"
    $outputs += ,[ordered]@{
        path = $relative
        media_type = "image/png"
        pixel_sizes = @($size)
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $repositoryRoot ($relative -replace "/", "\"))).Hash.ToLowerInvariant()
    }
}
$outputs += ,[ordered]@{
    path = "content/factorio/ui/branding/review/contact-sheet.png"
    media_type = "image/png"
    pixel_sizes = @(1280, 720)
    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $outputRootPath "review\contact-sheet.png")).Hash.ToLowerInvariant()
}

$manifest = [ordered]@{
    schema = "facman.branding_asset_manifest.v1"
    status = "provisional_human_review_required"
    product = "FacMan"
    source = [ordered]@{
        path = "content/factorio/ui/branding/master/facman-provisional.png"
        sha256 = $sourceDigest
        width = 1254
        height = 1254
        custody = "operator_supplied_local_inbox"
        official_brand_asset = $false
    }
    source_candidates = @(
        [ordered]@{
            name = "FacMan.png"
            sha256 = "5001177903f03342630db1adced28a0ebc7dd03f16ffe791f1921cfdbeed6ed8"
            disposition = "selected_provisional_master"
        },
        [ordered]@{
            name = "FacMan.ico"
            sha256 = "772e23951eef431bb7de936ae17ff6d2d7aafbd9bd5d3de05778d1186b35dfa1"
            disposition = "supplied_derivative_reference"
        },
        [ordered]@{
            name = "FacMan.favicons.zip"
            sha256 = "da3de5d5aebf079df744296d26dc6ec99838ffdfae69d0e335f9c6ed67a00ff8"
            disposition = "supplied_derivative_reference"
        }
    )
    generation = [ordered]@{
        tool = "tools/generate_branding_assets.ps1"
        algorithm = "system_drawing_high_quality_bicubic_v1"
        deterministic = $true
    }
    outputs = $outputs
    human_review_required = @(
        "small_size_optical_correction",
        "public_brand_and_trademark_judgment",
        "high_contrast_and_dpi_experience"
    )
    authority_exclusions = @(
        "official_factorio_or_wube_branding",
        "production_signing",
        "public_release_or_support_activation"
    )
}
$manifestPath = Join-Path $outputRootPath "provenance\branding-asset-manifest.v1.json"
New-Directory ([IO.Path]::GetDirectoryName($manifestPath))
$manifestText = $manifest | ConvertTo-Json -Depth 8
[IO.File]::WriteAllText($manifestPath, $manifestText + "`n", (New-Object Text.UTF8Encoding($false)))

Write-Output "branding-assets: generated deterministic platform assets from sha256:$sourceDigest"
