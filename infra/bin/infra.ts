#!/usr/bin/env node
import 'source-map-support/register'
import * as cdk from 'aws-cdk-lib'
import { BackendStack } from '../lib/backend-stack'
import { BackendLambdaStack } from '../lib/backend-lambda-stack'
import { FrontendStack } from '../lib/frontend-stack'

const app = new cdk.App()
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION,
}

new BackendStack(app, 'EstimationBackendStack', { env })

const backendLambdaEnabled =
  String(app.node.tryGetContext('backendLambdaEnabled') ?? 'true').toLowerCase() !== 'false'
if (backendLambdaEnabled) {
  new BackendLambdaStack(app, 'EstimationBackendLambdaStack', { env })
}

const frontendEnabled =
  String(app.node.tryGetContext('frontendEnabled') ?? 'true').toLowerCase() !== 'false'
if (frontendEnabled) {
  new FrontendStack(app, 'EstimationFrontendStack', { env })
}
