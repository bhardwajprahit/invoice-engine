$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Create .venv, then install desktop\requirements-build.txt before building the Windows app."
}

$backendOutput = Join-Path $PSScriptRoot "backend"
$workOutput = Join-Path $repoRoot ".build\pyinstaller"
New-Item -ItemType Directory -Force -Path $backendOutput | Out-Null

# Explicitly add the repository root and API/worker entry modules. The API is
# imported directly in runner.py as well; these flags make the bundle robust
# against PyInstaller's module discovery from the desktop entry-point folder.
& $pythonExe -m PyInstaller --noconfirm --clean --onefile `
    --name invoice-engine-backend `
    --distpath $backendOutput `
    --workpath $workOutput `
    --specpath $workOutput `
    --paths $repoRoot `
    --hidden-import api `
    --hidden-import worker `
    --add-data "$repoRoot\frontend;frontend" `
    (Join-Path $PSScriptRoot "runner.py")

if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE." }
