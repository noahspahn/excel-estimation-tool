AWS deployment (static frontend + container backend)

Overview

- Frontend: Static React site served from S3 behind CloudFront.
- Backend: FastAPI container on AWS App Runner pulling from ECR.
- Goals: Simple, low‑ops, cost‑aware. App Runner is easy to manage; for very low traffic, consider the Lambda alternative below.

Prerequisites

- AWS CLI v2 configured (`aws configure`), with permissions for CloudFormation, CloudFront, S3, ECR, IAM, App Runner, and Secrets Manager (optional).
- Docker installed and logged in locally.
- Node 18+ for building the frontend.

Quick start

1) Build and deploy backend + frontend

  ./deploy/aws/deploy-apprunner.sh \
    --region us-east-1 \
    --app-name estimation \
    --s3-bucket estimation-frontend-$(date +%s) \
    [--openai-secret-arn arn:aws:secretsmanager:...:secret:OPENAI_API_KEY-xxxxx]

What the script does

- Builds backend Docker image and pushes it to a private ECR repo.
- Creates/updates an App Runner service that pulls the image from ECR.
- Reads the service URL and builds the frontend with `VITE_API_URL` pointing at it.
- Provisions an S3 bucket + CloudFront distribution (via CloudFormation) and uploads the frontend build.
- Invalidates CloudFront so new assets are served immediately.

Outputs

- Backend URL (App Runner): https://xxxxxxxx.us-east-1.awsapprunner.com
- Frontend URL (CloudFront): https://xxxxxxxx.cloudfront.net

Common options

- You can pass `--allowed-origins` to restrict CORS on the backend. Default is `*`.
- For predictable S3 naming, pass a globally unique `--s3-bucket BUCKET_NAME`.

Clean up

  ./deploy/aws/destroy.sh --region us-east-1 --app-name estimation --s3-bucket <bucket>

This deletes the CloudFormation stacks, empties the S3 bucket, and removes the ECR repository.

Notes on cost

- App Runner: simplest container hosting with autoscaling. It does not scale to zero; it’s best for steady or moderate usage.
- ECS Fargate: more knobs; similar base costs for 1 task behind an ALB.
- Lightsail Containers: cheapest fixed monthly for a small container, fewer enterprise features.
- Lambda (serverless) alternative: For spiky/low traffic, converting the backend to Lambda (API Gateway + Lambda) is the most cost‑effective. This repo can support that with a small shim (Mangum). Ask if you want that path and we’ll wire it up.

