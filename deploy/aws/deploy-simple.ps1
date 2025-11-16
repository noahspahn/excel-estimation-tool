Param(
  [string]$Region = "us-east-1",
  [string]$EcrRepo = "estimation-backend",
  [string]$Bucket = "meshai-estimation-frontend-1",
  [string]$ServiceName = "estimation-backend-AR",
  [switch]$SkipBackend,
  [switch]$SkipFrontend
)

Write-Host "=== Deploying Estimation Tool ==="
Write-Host "Region:         $Region"
Write-Host "ECR repo:       $EcrRepo"
Write-Host "S3 bucket:      $Bucket"
Write-Host "AppRunner name: $ServiceName"

# Resolve AWS account ID
$accountId = aws sts get-caller-identity --query Account --output text
if (-not $accountId) {
  throw "Failed to resolve AWS account ID. Is aws cli configured?"
}

$ecrRoot = "$accountId.dkr.ecr.$Region.amazonaws.com"
$ecrUri  = "$ecrRoot/$EcrRepo"

if (-not $SkipBackend) {
  Write-Host "`n[Backend] Ensuring ECR repo '$EcrRepo' exists..."
  $repoExists = $false
  try {
    aws ecr describe-repositories --repository-names $EcrRepo --region $Region | Out-Null
    $repoExists = $true
  } catch {
    $repoExists = $false
  }

  if (-not $repoExists) {
    aws ecr create-repository --repository-name $EcrRepo --region $Region | Out-Null
  }

  Write-Host "[Backend] Logging in to ECR..."
  aws ecr get-login-password --region $Region `
    | docker login --username AWS --password-stdin $ecrRoot

  Write-Host "[Backend] Building Docker image..."
  Push-Location backend
  $imageTag = "${EcrRepo}:latest"
  docker build -t $imageTag .
  Pop-Location

  Write-Host "[Backend] Tagging and pushing image to $ecrUri:latest ..."
  $remoteTag = "$ecrUri`:latest"
  docker tag $imageTag $remoteTag
  docker push $remoteTag
}

# Determine backend URL from App Runner
$backendUrl = $null
try {
  $serviceArn = aws apprunner list-services --region $Region `
    --query "ServiceSummaryList[?ServiceName=='$ServiceName'].ServiceArn" `
    --output text

  if (-not $serviceArn -or $serviceArn -eq "None") {
    throw "App Runner service '$ServiceName' not found in region $Region."
  }

  $backendUrl = aws apprunner describe-service --service-arn $serviceArn --region $Region `
    --query "Service.ServiceUrl" --output text
} catch {
  throw "Failed to resolve App Runner backend URL: $_"
}

if (-not $backendUrl) {
  throw "Backend URL could not be determined from App Runner."
}

Write-Host "`n[Backend] App Runner URL: $backendUrl"

if (-not $SkipFrontend) {
  Write-Host "`n[Frontend] Building React app with VITE_API_URL=$backendUrl ..."
  Push-Location frontend
  $env:VITE_API_URL = "$backendUrl/"
  $env:VITE_EXCEL_API_ENABLED = "true"

  if (Test-Path package-lock.json) {
    npm ci
  } else {
    npm install
  }
  npm run build
  Pop-Location

  Write-Host "[Frontend] Syncing dist/ to s3://$Bucket ..."
  aws s3 sync "frontend/dist" "s3://$Bucket/" --delete --region $Region
}

Write-Host "`n=== Deploy complete ==="
Write-Host "Backend:  $backendUrl"
Write-Host "Frontend: http://$Bucket.s3-website-$Region.amazonaws.com/"
