# CDK deployment (App Runner + optional frontend)

This CDK app provisions:

- **Backend**: ECR repo + App Runner service (HTTPS endpoint).
- **Backend Next (stage 1)**: API Gateway + Lambda for side-by-side backend migration.
- **Cognito**: User pool + app client for auth.
- **Database**: RDS Postgres + VPC + App Runner VPC connector + security groups.
- **Reports**: S3 bucket for PDF binaries + DynamoDB table for report metadata/payload snapshots.
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

## Deploy backend-next (API Gateway + Lambda)

This stack is intended for migration testing while the App Runner backend remains
the primary path.

```
npx cdk deploy EstimationBackendLambdaStack -c backendLambda='{"mode":"fastapi","env":{"AWS_REGION":"us-east-1"}}'
```

`mode` options:

- `fastapi` (default): run the full backend app in Lambda via Mangum.
- `router`: use the lightweight router Lambda and proxy unknown routes to
  `legacyBackendUrl`.

Outputs include:

- `BackendLambdaApiUrl`
- `BackendLambdaApiDomain`

## RDS + VPC outputs

When `createDatabase` is enabled (default), the stack outputs:

- `DatabaseEndpoint`
- `DatabaseName`
- `DatabaseSecretArn`
- `VpcConnectorArn`
- `VpcId`

The App Runner service is configured with a `DATABASE_URL` that points at
the RDS instance and uses `sslmode=require`.

## Report storage outputs

The backend stack also outputs:

- `ReportsBucketName`
- `ReportsTableName`

The App Runner service receives:

- `S3_REPORT_BUCKET`
- `REPORTS_TABLE_NAME`

## Cognito outputs

The backend stack outputs:

- `CognitoUserPoolId`
- `CognitoUserPoolClientId`
- `CognitoRegion`

Use these values to set:

- Backend env: `COGNITO_REGION`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`
- Frontend env at build time: `VITE_COGNITO_REGION`, `VITE_COGNITO_CLIENT_ID`

## Deploy frontend (S3 + CloudFront)

Deploy the frontend stack. If you want CloudFront to proxy `/api/*` to App Runner
(recommended to eliminate CORS), pass the App Runner domain via context:

```
npx cdk deploy EstimationFrontendStack -c frontend='{"apiDomain":"<your-apprunner-domain>"}'
```

To also enable the stage-1 backend route (`/api-next/*`), pass `nextApiUrl` from
the `EstimationBackendLambdaStack` output:

```
npx cdk deploy EstimationFrontendStack -c frontend='{"apiDomain":"<your-apprunner-domain>","nextApiUrl":"https://<api-id>.execute-api.<region>.amazonaws.com/prod/"}'
```

Build the frontend and sync:

```
cd ../frontend
$env:VITE_API_URL = "/"
$env:VITE_BACKEND_TARGET = "legacy"
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

Disable database provisioning:

```
npx cdk deploy EstimationBackendStack -c backend='{"createDatabase":false}'
```

Optional frontend asset deployment via CDK:

```
npx cdk deploy EstimationFrontendStack -c frontend='{"deployAssets":true,"assetPath":"../frontend/dist"}'
```

To enable the `/api/*` proxy and asset deploy together:

```
npx cdk deploy EstimationFrontendStack -c frontend='{"apiDomain":"<your-apprunner-domain>","deployAssets":true,"assetPath":"../frontend/dist"}'
```

You can also pass a full URL instead of a domain:

```
npx cdk deploy EstimationFrontendStack -c frontend='{"apiUrl":"https://<your-apprunner-domain>"}'
```

Disable frontend stack entirely:

```
npx cdk synth -c frontendEnabled=false
```
