# CDK deployment (Lambda API + optional frontend)

This CDK app provisions:

- **Backend API**: API Gateway + Lambda (FastAPI in Lambda).
- **Data tables**: DynamoDB tables for report jobs, proposals/versions/documents, and contracts.
- **Cognito**: User pool + app client for auth.
- **Frontend (optional)**: S3 + CloudFront distribution for HTTPS hosting.

Legacy App Runner resources are disabled by default. If you still need them
temporarily, deploy with:

```
npx cdk deploy EstimationBackendStack -c legacyBackendEnabled=true
```

## Prereqs

- AWS CLI configured (`aws configure`)
- CDK bootstrap for your account/region:  
  `npx cdk bootstrap`

## Install

```
cd infra
npm install
```

## Deploy backend (API Gateway + Lambda)

```
npx cdk deploy EstimationBackendLambdaStack -c backendLambda='{"timeoutSeconds":60,"apiTimeoutSeconds":29,"env":{"AUTH_REQUIRED":"true"}}'
```

- `timeoutSeconds`: Lambda timeout in seconds (default `60`).
- `apiTimeoutSeconds`: API Gateway integration timeout in seconds (default `29`).
  API Gateway defaults to a 29-second max unless your AWS account has an
  approved quota increase for regional/private REST APIs.

Outputs include:

- `BackendLambdaApiUrl`
- `BackendLambdaApiDomain`
- `ReportJobsTableName` (DynamoDB table for async report/subtask jobs)
- `ProposalsTableName`
- `ProposalVersionsTableName`
- `ProposalDocumentsTableName`
- `ContractsTableName`
- `ContractSyncTableName`

If you want those table names persisted as GitHub Environment variables for the
deploy workflow, run from repo root:

```
python scripts/sync_backend_table_vars.py --repo noahspahn/excel-estimation-tool --env dev --region us-east-1
```

## Cognito outputs

The backend stack outputs:

- `CognitoUserPoolId`
- `CognitoUserPoolClientId`
- `CognitoRegion`

Use these values to set:

- Backend env (pass via `backendLambda.env`): `COGNITO_REGION`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`
- Frontend env at build time: `VITE_COGNITO_REGION`, `VITE_COGNITO_CLIENT_ID`

## Deploy frontend (S3 + CloudFront)

Deploy the frontend stack with the backend Lambda API URL so CloudFront proxies
`/api/*` to API Gateway.

```
npx cdk deploy EstimationFrontendStack -c frontend='{"apiUrl":"https://<api-id>.execute-api.<region>.amazonaws.com/prod/"}'
```

Build the frontend and sync:

```
cd ../frontend
$env:VITE_API_URL = "/"
$env:VITE_DISABLE_AUTH = "false"
$env:VITE_APP_ENV = "prod"
npm ci
npm run build
aws s3 sync .\dist "s3://<FrontendBucketName>/" --delete
```

## Context configuration

You can override backend defaults using CDK context:

```
npx cdk deploy EstimationBackendLambdaStack -c backendLambda='{"timeoutSeconds":60,"apiTimeoutSeconds":29,"env":{"ALLOWED_ORIGINS":"https://<cloudfront-domain>","AUTH_REQUIRED":"true"}}'
```

Optional frontend asset deployment via CDK:

```
npx cdk deploy EstimationFrontendStack -c frontend='{"deployAssets":true,"assetPath":"../frontend/dist"}'
```

To enable the `/api/*` proxy and asset deploy together:

```
npx cdk deploy EstimationFrontendStack -c frontend='{"apiUrl":"https://<api-id>.execute-api.<region>.amazonaws.com/prod/","deployAssets":true,"assetPath":"../frontend/dist"}'
```

You can also pass a full URL instead of a domain:

```
npx cdk deploy EstimationFrontendStack -c frontend='{"apiUrl":"https://<api-id>.execute-api.<region>.amazonaws.com/prod/"}'
```

Disable frontend stack entirely:

```
npx cdk synth -c frontendEnabled=false
```
