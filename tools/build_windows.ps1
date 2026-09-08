param([Parameter(Mandatory=$true)][string]$WorkRoot)

$ErrorActionPreference='Stop'

$WorkRoot=(Resolve-Path -LiteralPath $WorkRoot).Path

$python=Join-Path $WorkRoot 'firmware-venv\Scripts\python.exe'

$upstream=Join-Path $WorkRoot 'firmware-2.7.15'

if(!(Test-Path -LiteralPath $python)){throw 'Use the prepared PlatformIO work root containing firmware-venv and firmware-2.7.15.'}

& $python (Join-Path $PSScriptRoot 'apply_firmware.py') $upstream

if($LASTEXITCODE -ne 0){throw 'Source integration failed'}

$mapping=(subst | Where-Object {$_ -match '^M:'})

if($mapping -and !$mapping.EndsWith($WorkRoot,[System.StringComparison]::OrdinalIgnoreCase)){throw 'M: is already mapped to a different directory'}

if(!$mapping){subst M: $WorkRoot}

if(!(Test-Path 'M:\s')){New-Item -ItemType Junction -Path 'M:\s' -Target 'M:\firmware-2.7.15' | Out-Null}

if(!(Test-Path 'M:\c')){New-Item -ItemType Junction -Path 'M:\c' -Target 'M:\pio-stable' | Out-Null}

New-Item -ItemType Directory -Force 'M:\tmp' | Out-Null

$env:PLATFORMIO_CORE_DIR='M:\c';$env:TEMP='M:\tmp';$env:TMP='M:\tmp'

# Stable build metadata across the two sandbox users; source provenance is in the manifest.

$env:TDECK_BUILD_REPO='unknown'

$env:SOURCE_DATE_EPOCH='1788719400'

Push-Location 'M:\s'

try { & 'M:\firmware-venv\Scripts\python.exe' -m platformio run -e t-deck-tft -j 1; if($LASTEXITCODE -ne 0){throw 'Firmware build failed'} }

finally {Pop-Location}
