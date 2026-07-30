param(
  [switch]$Restart
)

$ErrorActionPreference = "Stop"
$projectPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiPath = Join-Path $projectPath "services\catalog-service"
$webPath = Join-Path $projectPath "apps\web-next"
$pythonPath = Join-Path $apiPath ".venv\Scripts\python.exe"
$npmPath = (Get-Command "npm.cmd" -ErrorAction Stop).Source

if (-not (Test-Path -LiteralPath $pythonPath)) {
  throw "Backend virtual environment is missing. Create .venv and install requirements first."
}

Write-Host "Applying database migrations..."
Push-Location -LiteralPath $apiPath
try {
  & $pythonPath -m alembic upgrade head
  if ($LASTEXITCODE -ne 0) {
    throw "Database migration failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}

function Get-PortProcesses {
  param([int]$Port)

  $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  foreach ($listener in @($listeners)) {
    Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
  }
}

function Stop-ProjectPort {
  param([int]$Port)

  foreach ($process in @(Get-PortProcesses -Port $Port)) {
    $commandLine = [string]$process.CommandLine
    if ($commandLine.IndexOf($projectPath, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
      throw "Port $Port is owned by an unrelated process (PID $($process.ProcessId)); it was not stopped."
    }
    Stop-Process -Id $process.ProcessId -Force
  }
}

function Wait-ForUrl {
  param(
    [string]$Url,
    [string]$Name
  )

  for ($attempt = 1; $attempt -le 30; $attempt++) {
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
        return
      }
    }
    catch {
      if ($attempt -eq 30) {
        throw "$Name did not become ready at $Url."
      }
    }
    Start-Sleep -Milliseconds 500
  }
}

if ($Restart) {
  Stop-ProjectPort -Port 8001
  Stop-ProjectPort -Port 3000
  Start-Sleep -Milliseconds 500
}

$apiListener = @(Get-PortProcesses -Port 8001)
if ($apiListener.Count -eq 0) {
  $apiProcess = Start-Process -FilePath $pythonPath `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001") `
    -WorkingDirectory $apiPath `
    -RedirectStandardOutput (Join-Path $apiPath "fastapi-dev.log") `
    -RedirectStandardError (Join-Path $apiPath "fastapi-dev-error.log") `
    -WindowStyle Hidden `
    -PassThru
  Write-Host "Started SourceAI backend (PID $($apiProcess.Id))."
}
else {
  Write-Host "SourceAI backend is already running (PID $($apiListener[0].ProcessId))."
}

$webListener = @(Get-PortProcesses -Port 3000)
if ($webListener.Count -eq 0) {
  $webProcess = Start-Process -FilePath $npmPath `
    -ArgumentList @("run", "dev") `
    -WorkingDirectory $webPath `
    -RedirectStandardOutput (Join-Path $webPath "next-dev.log") `
    -RedirectStandardError (Join-Path $webPath "next-dev-error.log") `
    -WindowStyle Hidden `
    -PassThru
  Write-Host "Started SourceAI frontend (PID $($webProcess.Id))."
}
else {
  Write-Host "SourceAI frontend is already running (PID $($webListener[0].ProcessId))."
}

Wait-ForUrl -Url "http://127.0.0.1:8001/api/ready" -Name "Backend"
Wait-ForUrl -Url "http://127.0.0.1:3000" -Name "Frontend"

Write-Host "SourceAI frontend: http://localhost:3000"
Write-Host "SourceAI backend:  http://localhost:8001"
