# AWS deployment (CDK + App Runner primary)

## Primary path (CDK)

The recommended deployment path is now the CDK app in `infra/`:

- **Backend**: App Runner + ECR + Cognito + RDS (auth enabled, DB prewired)
- **Frontend**: S3 + CloudFront (HTTPS)

Start here:

```
cd infra
npm install
npx cdk bootstrap
npx cdk deploy EstimationBackendStack
npx cdk deploy EstimationFrontendStack
```

Use the stack outputs to set:

- Backend env: `COGNITO_REGION`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`
- Frontend build env: `VITE_API_URL`, `VITE_COGNITO_REGION`, `VITE_COGNITO_CLIENT_ID`, `VITE_DISABLE_AUTH=false`

See `infra/README.md` for full details.

If you're at the App Runner service limit, reuse an existing service and
deploy only Cognito + ECR with:

```
npx cdk deploy EstimationBackendStack -c backend='{"existingRepoName":"estimation-backend","createService":false}'
```

---

## Legacy scripts (still supported)

## Overview

- **Backend**: FastAPI app (`backend/app/main.py`) deployed as a Docker container on **AWS App Runner**, pulling from ECR.
- **Frontend**: Vite/React app (`frontend/`) built to static assets and served from an **S3 static website endpoint**.
- **Auth**: CDK path provisions Cognito by default. Legacy scripts can still use `VITE_DISABLE_AUTH=true`, but auth is now intended to be enabled.
- Goal: simple, low-ops deployment you can drive from your dev machine with minimal manual AWS configuration.

## Prerequisites

- AWS CLI v2 configured (`aws configure`) with access to:
  - ECR, App Runner, S3, IAM (Cognito optional).
- Docker installed and logged in locally (for building/pushing backend images).
- Node 18+ for building the frontend.
- (Optional for later) A Cognito User Pool with:
  - An App Client (`VITE_COGNITO_CLIENT_ID` / `COGNITO_CLIENT_ID`).
  - Email as sign-in alias.
  - Auth flows enabled: `ALLOW_USER_PASSWORD_AUTH`, `ALLOW_REFRESH_TOKEN_AUTH`.

## Current implementation

The “live” setup looks like this:

- **Backend API**

  - Built from `backend/Dockerfile`.
  - Pushed to an ECR repo (e.g. `estimation-backend`).
  - Exposed via **App Runner** at a URL like `https://cqdcypvz3e.us-east-1.awsapprunner.com`.
  - Env vars set in the App Runner service:
    - `DATABASE_URL` (or SQLite default).
    - `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`.
    - `OPENAI_API_KEY` (optional).
    - `ALLOWED_ORIGINS` for CORS (`http://localhost:3000,http://localhost:3001` etc).
    - `COGNITO_REGION`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID` (only needed when auth is enabled).
  - `get_current_user()` in `backend/app/main.py` verifies Cognito JWTs when auth is enabled.

- **Frontend app**

  - Built with Vite from `frontend/` into `frontend/dist`.
  - Synced to an S3 bucket (e.g. `meshai-estimation-frontend-1`) using `aws s3 sync` and served via the S3 website endpoint:  
    `http://meshai-estimation-frontend-1.s3-website-us-east-1.amazonaws.com/`.
  - At build time, the frontend reads these Vite env vars:
    - `VITE_API_URL` → points at the App Runner backend (e.g. `https://cqdcypvz3e.us-east-1.awsapprunner.com/`).
    - `VITE_EXCEL_API_ENABLED` → enables Excel-related UI.
    - `VITE_APP_ENV` -> `dev` or `stage` shows a badge in the top nav (prod stays hidden).
    - `VITE_COGNITO_REGION` / `VITE_COGNITO_CLIENT_ID` → used to call Cognito’s JSON APIs.
  - On load, the app shows a **sign-in / sign-up gate** only when `VITE_DISABLE_AUTH=false`.

- **Cognito auth (optional)**
  - Sign-in:
    - User enters email + password on the login screen.
    - Frontend POSTs to `https://cognito-idp.<region>.amazonaws.com/` with:
      - `X-Amz-Target: AWSCognitoIdentityProviderService.InitiateAuth`.
      - `AuthFlow: USER_PASSWORD_AUTH`, `ClientId`, `USERNAME`, `PASSWORD`.
    - On success, frontend stores the returned `IdToken` in `localStorage` as `auth_token` and the email as `auth_email`.
    - All backend calls that require auth send `Authorization: Bearer <IdToken>`.
  - Sign-up:
    - User switches to the “Sign up” tab, enters email + password.
    - Frontend calls `SignUp` and then `ConfirmSignUp` with the verification code emailed by Cognito.
    - Once confirmed, the user can sign in with the same credentials.

## Simple deploy script for Windows

The file `deploy/aws/deploy-simple.ps1` automates common backend + frontend deployment steps from a Windows PowerShell session.

What it does (when run from repo root):

1. **Backend**

   - Ensures an ECR repo exists (default: `estimation-backend`).
   - Logs into ECR with `aws ecr get-login-password`.
   - Builds the backend Docker image from `backend/` and tags it as `<repo>:latest`.
   - Pushes the image to `<ACCOUNT_ID>.dkr.ecr.<region>.amazonaws.com/<repo>:latest`.
   - Looks up the existing App Runner service by name (default: `estimation-backend-AR`) and prints its Service URL (it does **not** create or modify the App Runner service; that is assumed already configured).

2. **Frontend**
   - Builds the React app from `frontend/` with `VITE_API_URL` set to the App Runner URL and `VITE_EXCEL_API_ENABLED=true`.
   - Uses `npm ci` if `package-lock.json` is present, otherwise `npm install`.
   - Runs `npm run build` to produce `frontend/dist`.
   - Syncs `frontend/dist` to the S3 bucket you specify (default: `meshai-estimation-frontend-1`) via `aws s3 sync ... --delete`.

Usage example:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\deploy\aws\deploy-simple.ps1 `
  -Region "us-east-1" `
  -EcrRepo "estimation-backend" `
  -Bucket "meshai-estimation-frontend-1" `
  -ServiceName "estimation-backend-AR"
```

## Dev / Stage / Prod environments

The repo now includes a small wrapper that reads environment-specific settings
and calls `deploy-simple.ps1` with the correct resource names.

1) Copy the example config:

```powershell
Copy-Item deploy/aws/environments.example.json deploy/aws/environments.json
```

2) Edit `deploy/aws/environments.json` with your real bucket names, App Runner
service names, and optional frontend Vite variables (no secrets should go here).

3) Deploy:

```powershell
.\deploy\aws\deploy-env.ps1 -Environment dev
.\deploy\aws\deploy-env.ps1 -Environment stage
.\deploy\aws\deploy-env.ps1 -Environment prod
```

Notes:
- Each environment should have its own App Runner service + S3 bucket.
- If you need different Cognito pools per environment, set `VITE_COGNITO_REGION` and `VITE_COGNITO_CLIENT_ID` in the config file for each environment.
- Set `VITE_APP_ENV` to `dev` or `stage` to show the environment badge.
- `deploy-simple.ps1` respects any `VITE_*` variables already set in your shell,
  so you can also export them directly instead of using the config.

## Manual deploy overview

If you prefer to run the steps yourself:

1. **Backend image → ECR**

   - Build: `docker build -t estimation-backend:latest backend`
   - Tag: `docker tag estimation-backend:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/estimation-backend:latest`
   - Push: `docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/estimation-backend:latest`

2. **App Runner service**

   - In console, create a service (`estimation-backend-AR`) pointing at the ECR image.
   - Port: `8000`.
   - Environment variables: as described in “Current implementation” above.

3. **Frontend build → S3 website**

   - From `frontend/`:

     ```powershell
     $env:VITE_API_URL = "https://<your-apprunner-url>/"
     $env:VITE_EXCEL_API_ENABLED = "true"
     $env:VITE_DISABLE_AUTH = "false"
     $env:VITE_APP_ENV = "dev"
     # Cognito vars only needed when auth is enabled
     $env:VITE_COGNITO_REGION = "us-east-1"
     $env:VITE_COGNITO_CLIENT_ID = "<your-app-client-id>"
     npm install
     npm run build
     ```

   - Sync build artifacts to S3:

     ```powershell
     aws s3 sync .\dist "s3://meshai-estimation-frontend-1/" --delete --region us-east-1
     ```

   - Enable static website hosting / set index document (`index.html`) on the S3 bucket if not already configured.

## Auth and security notes

- The frontend never sees AWS credentials; it only calls Cognito’s public endpoints and your App Runner API.
- The backend never stores passwords; it only trusts Cognito JWTs (and enforces `iss`, `aud/client_id`, and token expiry).
- You can restrict which emails are allowed in your User Pool (via Cognito policies) rather than in the app.
- For production:
  - Consider putting CloudFront in front of the S3 website for HTTPS and better performance.

## CloudFormation-based path (optional)

This folder also contains templates for a more automated, CloudFormation-driven setup (including CloudFront). The original workflow was:

- `deploy/aws/apprunner-backend.yaml` – defines the App Runner service and its IAM role.
- `deploy/aws/cf-s3-static-site.yaml` – defines an S3 bucket + CloudFront distribution for the frontend.
- `deploy/aws/deploy-apprunner.sh` – a Bash script that builds and pushes the backend image, deploys the App Runner stack, builds the frontend, deploys the S3+CloudFront stack, and invalidates CloudFront.

In environments where you _can_ manage CloudFront, that remains the most production-friendly option. In this project’s current setup, the simpler App Runner + S3 website + Cognito direct-auth path described above is what’s actually in use.

### Multi-environment CloudFormation example

The Bash deployer already supports distinct app names. For example:

```bash
./deploy/aws/deploy-apprunner.sh --app-name estimation-dev --s3-bucket meshai-estimation-frontend-dev
./deploy/aws/deploy-apprunner.sh --app-name estimation-stage --s3-bucket meshai-estimation-frontend-stage
./deploy/aws/deploy-apprunner.sh --app-name estimation-prod --s3-bucket meshai-estimation-frontend-prod
```
