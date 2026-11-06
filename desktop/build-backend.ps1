$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Create .venv, then install desktop\requirements-build.txt before building the Windows app."
}

$backendOutput = Join-Path $PSScriptRoot "backend"
$workOutput = Join-Path $repoRoot ".build\pyinstaller"
New-Item -ItemType Directory -Force -Path $backendOutput | Out-Null
& $pythonExe -m PyInstaller --noconfirm --clean --onefile --name invoice-engine-backend --distpath $backendOutput --workpath $workOutput --specpath $workOutput --add-data "$repoRoot\frontend;frontend" (Join-Path $PSScriptRoot "runner.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE." }
