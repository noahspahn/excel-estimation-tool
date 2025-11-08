#!/usr/bin/env bash
set -euo pipefail

# Simple deployer for: Backend on App Runner + Frontend on S3/CloudFront.
# Requirements: awscli v2, docker, node (npm)

usage() {
  cat <<EOF
Usage: $0 [options]

Options:
  --region REGION              AWS region (default: us-east-1)
  --app-name NAME              App name/prefix (default: estimation)
  --ecr-repo NAME              ECR repo name (default: <app-name>-backend)
  --image-tag TAG              Image tag (default: timestamp)
  --s3-bucket NAME             S3 bucket for frontend (must be globally unique)
  --openai-secret-arn ARN      Optional Secrets Manager ARN for OPENAI_API_KEY
  --allowed-origins ORIGINS    CORS for backend (default: *)
  --skip-frontend              Skip frontend build/upload
  --skip-backend               Skip backend build/deploy

Example:
  $0 --region us-east-1 --app-name estimation \\
     --s3-bucket estimation-frontend-$(date +%s)
EOF
}

REGION="us-east-1"
APP_NAME="estimation"
ECR_REPO=""
IMAGE_TAG=""
S3_BUCKET=""
OPENAI_SECRET_ARN=""
ALLOWED_ORIGINS="*"
SKIP_FE=0
SKIP_BE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region) REGION="$2"; shift 2;;
    --app-name) APP_NAME="$2"; shift 2;;
    --ecr-repo) ECR_REPO="$2"; shift 2;;
    --image-tag) IMAGE_TAG="$2"; shift 2;;
    --s3-bucket) S3_BUCKET="$2"; shift 2;;
    --openai-secret-arn) OPENAI_SECRET_ARN="$2"; shift 2;;
    --allowed-origins) ALLOWED_ORIGINS="$2"; shift 2;;
    --skip-frontend) SKIP_FE=1; shift;;
    --skip-backend) SKIP_BE=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

ECR_REPO=${ECR_REPO:-"${APP_NAME}-backend"}
IMAGE_TAG=${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}
STACK_BE="${APP_NAME}-be"
STACK_FE="${APP_NAME}-fe"

echo "Region:           $REGION"
echo "App name:         $APP_NAME"
echo "ECR repo:         $ECR_REPO"
echo "Image tag:        $IMAGE_TAG"
echo "S3 bucket:        ${S3_BUCKET:-<auto>}"
echo "OpenAI secret:    ${OPENAI_SECRET_ARN:-<none>}"
echo "Allowed origins:  $ALLOWED_ORIGINS"

account_id=$(aws sts get-caller-identity --query Account --output text)
ecr_uri="$account_id.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO"

if [[ "$SKIP_BE" -eq 0 ]]; then
  echo "\n[Backend] Ensuring ECR repo exists..."
  if ! aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$REGION" >/dev/null 2>&1; then
    aws ecr create-repository --repository-name "$ECR_REPO" --region "$REGION" >/dev/null
  fi

  echo "[Backend] Login to ECR..."
  aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$account_id.dkr.ecr.$REGION.amazonaws.com"

  echo "[Backend] Build and push image..."
  docker build -t "$ECR_REPO:$IMAGE_TAG" backend
  docker tag "$ECR_REPO:$IMAGE_TAG" "$ecr_uri:$IMAGE_TAG"
  docker push "$ecr_uri:$IMAGE_TAG"

  echo "[Backend] Deploy App Runner via CloudFormation..."
  aws cloudformation deploy \
    --template-file deploy/aws/apprunner-backend.yaml \
    --stack-name "$STACK_BE" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides \
      ServiceName="${APP_NAME}-backend" \
      EcrImageUri="$ecr_uri:$IMAGE_TAG" \
      AllowedOrigins="$ALLOWED_ORIGINS" \
      OpenAISecretArn="${OPENAI_SECRET_ARN}" \
    --region "$REGION"

  BACKEND_URL=$(aws cloudformation describe-stacks --stack-name "$STACK_BE" --region "$REGION" --query "Stacks[0].Outputs[?OutputKey=='ServiceUrl'].OutputValue" --output text)
  echo "[Backend] Service URL: $BACKEND_URL"
else
  BACKEND_URL="${VITE_API_URL:-}"
fi

if [[ "$SKIP_FE" -eq 0 ]]; then
  if [[ -z "${S3_BUCKET}" ]]; then
    S3_BUCKET="${APP_NAME}-frontend-$(date +%s)"
  fi

  echo "\n[Frontend] Build with VITE_API_URL=${BACKEND_URL}";
  pushd frontend >/dev/null
  export VITE_API_URL="$BACKEND_URL"
  npm ci
  npm run build
  popd >/dev/null

  echo "[Frontend] Provision S3 + CloudFront via CloudFormation..."
  aws cloudformation deploy \
    --template-file deploy/aws/cf-s3-static-site.yaml \
    --stack-name "$STACK_FE" \
    --parameter-overrides BucketName="$S3_BUCKET" \
    --region "$REGION"

  CF_DOMAIN=$(aws cloudformation describe-stacks --stack-name "$STACK_FE" --region "$REGION" --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDomainName'].OutputValue" --output text)
  DIST_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_FE" --region "$REGION" --query "Stacks[0].Outputs[?OutputKey=='DistributionId'].OutputValue" --output text)

  echo "[Frontend] Uploading assets to s3://$S3_BUCKET ..."
  aws s3 sync frontend/dist "s3://$S3_BUCKET" --delete --region "$REGION"

  echo "[Frontend] Creating CloudFront invalidation..."
  aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" >/dev/null

  echo "\nDeployment complete"
  echo "Frontend URL:  https://$CF_DOMAIN"
  if [[ -n "$BACKEND_URL" ]]; then
    echo "Backend URL:   $BACKEND_URL"
  fi
else
  echo "\nFrontend step skipped."
fi

