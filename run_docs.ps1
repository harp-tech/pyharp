# Resolve script directory (optional) and change to that directory if desired:
# Set-Location -Path (Split-Path -Path $MyInvocation.MyCommand.Definition -Parent)

# Launch mkdocs via uv (argument handling)
param(
    [string]$action = ""
)

# Find all subdirectories of .\harp.devices (follow symlinks)
$harpRoot = Join-Path -Path (Get-Location) -ChildPath "harp.devices"
$dirs = Get-ChildItem -LiteralPath $harpRoot -Directory -Force -ErrorAction SilentlyContinue |
        ForEach-Object { $_.FullName }

# Join them with ':' (Unix-style path separator)
$harpDevicesPaths = ($dirs -join ";")

# Prepend to PYTHONPATH (preserve existing)
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "{0};{1}" -f $harpDevicesPaths, $env:PYTHONPATH
} else {
    $env:PYTHONPATH = $harpDevicesPaths
}

# Optionally print for debugging
Write-Output "PYTHONPATH set to: $env:PYTHONPATH"

switch ($action) {
    "build"  { uv run mkdocs build }
    "deploy" { uv run mkdocs gh-deploy }
    default  { uv run mkdocs serve }
}
