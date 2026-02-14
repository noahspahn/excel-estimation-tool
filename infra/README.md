# CDK deployment (App Runner + optional frontend)

This CDK app provisions:

- **Backend**: ECR repo + App Runner service (HTTPS endpoint).
- **Cognito**: User pool + app client for auth.
- **Frontend (optional)**: S3 + CloudFront distribution for HTTPS hosting.

## Prereqs

- AWS CLI configured (`aws configure`)
- CDK bootstrap for your account/region:  
  `npx cdk bootstrap`

## Install

```
cd infra
npm install
```

## Deploy backend (App Runner)

1) Deploy the stack to create the ECR repo + App Runner service:

```
npx cdk deploy EstimationBackendStack
```

If you need to reuse an existing App Runner service (quota limits), disable
service creation and only provision Cognito + ECR:

```
npx cdk deploy EstimationBackendStack -c backend='{"existingRepoName":"estimation-backend","createService":false}'
```

2) Build + push the backend image to the created repo (example):

```
# repo uri is output as BackendRepoUri
docker build -t estimation-backend:latest ../backend
docker tag estimation-backend:latest <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/estimation-backend:latest
aws ecr get-login-password --region <REGION> | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com
docker push <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/estimation-backend:latest
```

App Runner will auto-deploy when the image tag updates.

## Cognito outputs

The backend stack outputs:

- `CognitoUserPoolId`
- `CognitoUserPoolClientId`
- `CognitoRegion`

Use these values to set:

- Backend env: `COGNITO_REGION`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`
- Frontend env at build time: `VITE_COGNITO_REGION`, `VITE_COGNITO_CLIENT_ID`

## Deploy frontend (S3 + CloudFront)

Deploy the frontend stack:

```
npx cdk deploy EstimationFrontendStack
```

Build the frontend and sync:

```
cd ../frontend
$env:VITE_API_URL = "https://<your-apprunner-url>/"
$env:VITE_DISABLE_AUTH = "false"
$env:VITE_APP_ENV = "prod"
npm ci
npm run build
aws s3 sync .\dist "s3://<FrontendBucketName>/" --delete
```

## Context configuration

You can override defaults using CDK context:

```
npx cdk deploy EstimationBackendStack -c backend='{"serviceName":"estimation-backend","ecrRepoName":"estimation-backend","imageTag":"latest","env":{"ALLOWED_ORIGINS":"https://<cloudfront-domain>","AUTH_REQUIRED":"true"}}'
```

By default, the stack **reuses** an existing ECR repo. If you want CDK to
create the repo, pass `createRepo: true`.

Reuse an existing repo:

```
npx cdk deploy EstimationBackendStack -c backend='{"existingRepoName":"estimation-backend"}'
```

Create a new repo:

```
npx cdk deploy EstimationBackendStack -c backend='{"ecrRepoName":"estimation-backend","createRepo":true}'
```

Optional frontend asset deployment via CDK:

```
npx cdk deploy EstimationFrontendStack -c frontend='{"deployAssets":true,"assetPath":"../frontend/dist"}'
```

Disable frontend stack entirely:

```
npx cdk synth -c frontendEnabled=false
```
