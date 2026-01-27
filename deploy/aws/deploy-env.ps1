Param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("dev", "stage", "prod")]
  [string]$Environment,
  [string]$Config = "deploy/aws/environments.json",
  [switch]$SkipBackend,
  [switch]$SkipFrontend
)

function Load-EnvConfig {
  param(
    [string]$Path,
    [string]$EnvironmentName
  )
  if (-not (Test-Path $Path)) {
    $examplePath = "deploy/aws/environments.example.json"
    throw "Config file not found: $Path. Copy $examplePath to $Path and edit values."
  }
  $raw = Get-Content -Path $Path -Raw
  $config = $raw | ConvertFrom-Json
  $entry = $config.$EnvironmentName
  if (-not $entry) {
    throw "Environment '$EnvironmentName' not found in $Path."
  }
  return $entry
}

$envConfig = Load-EnvConfig -Path $Config -EnvironmentName $Environment

$Region = if ($envConfig.region) { $envConfig.region } else { "us-east-1" }
$EcrRepo = if ($envConfig.ecrRepo) { $envConfig.ecrRepo } else { "estimation-backend-$Environment" }
$ServiceName = if ($envConfig.serviceName) { $envConfig.serviceName } else { "estimation-backend-$Environment-AR" }
$Bucket = if ($envConfig.bucket) { $envConfig.bucket } else { "meshai-estimation-frontend-$Environment" }

if ($envConfig.frontendEnv) {
  foreach ($kv in $envConfig.frontendEnv.PSObject.Properties) {
    if ($null -ne $kv.Value -and $kv.Value -ne "") {
      $env:$($kv.Name) = "$($kv.Value)"
    }
  }
}

Write-Host "=== Deploy environment: $Environment ==="
Write-Host "Region:         $Region"
Write-Host "ECR repo:       $EcrRepo"
Write-Host "S3 bucket:      $Bucket"
Write-Host "AppRunner name: $ServiceName"

& "$PSScriptRoot/deploy-simple.ps1" `
  -Region $Region `
  -EcrRepo $EcrRepo `
  -Bucket $Bucket `
  -ServiceName $ServiceName `
  -SkipBackend:$SkipBackend `
  -SkipFrontend:$SkipFrontend
