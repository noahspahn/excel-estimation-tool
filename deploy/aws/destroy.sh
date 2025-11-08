#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 --region REGION --app-name NAME --s3-bucket BUCKET

Deletes CloudFormation stacks (frontend/backend), empties S3 bucket, and removes ECR repo.

Options:
  --region REGION
  --app-name NAME       (prefix used by deploy script)
  --s3-bucket BUCKET
EOF
}

REGION=""
APP_NAME=""
S3_BUCKET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region) REGION="$2"; shift 2;;
    --app-name) APP_NAME="$2"; shift 2;;
    --s3-bucket) S3_BUCKET="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

if [[ -z "$REGION" || -z "$APP_NAME" || -z "$S3_BUCKET" ]]; then
  usage; exit 1
fi

STACK_BE="${APP_NAME}-be"
STACK_FE="${APP_NAME}-fe"
ECR_REPO="${APP_NAME}-backend"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO"

echo "Emptying S3 bucket s3://$S3_BUCKET ..."
aws s3 rm "s3://$S3_BUCKET" --recursive --region "$REGION" || true

echo "Deleting frontend stack $STACK_FE ..."
aws cloudformation delete-stack --stack-name "$STACK_FE" --region "$REGION"
aws cloudformation wait stack-delete-complete --stack-name "$STACK_FE" --region "$REGION" || true

echo "Deleting backend stack $STACK_BE ..."
aws cloudformation delete-stack --stack-name "$STACK_BE" --region "$REGION"
aws cloudformation wait stack-delete-complete --stack-name "$STACK_BE" --region "$REGION" || true

echo "Removing ECR images and repository $ECR_REPO ..."
aws ecr batch-delete-image --repository-name "$ECR_REPO" --image-ids $(aws ecr list-images --repository-name "$ECR_REPO" --query 'imageIds[*]' --output json --region "$REGION") --region "$REGION" >/dev/null 2>&1 || true
aws ecr delete-repository --repository-name "$ECR_REPO" --force --region "$REGION" >/dev/null 2>&1 || true

echo "Done."

