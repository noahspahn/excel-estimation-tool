import * as cdk from 'aws-cdk-lib'
import { CfnOutput, Stack, StackProps } from 'aws-cdk-lib'
import * as apigateway from 'aws-cdk-lib/aws-apigateway'
import * as lambda from 'aws-cdk-lib/aws-lambda'
import * as logs from 'aws-cdk-lib/aws-logs'
import * as path from 'path'

type BackendLambdaContext = {
  apiName?: string
  stageName?: string
  legacyBackendUrl?: string
  timeoutSeconds?: number | string
  memorySize?: number | string
  env?: Record<string, string>
}

export class BackendLambdaStack extends Stack {
  constructor(scope: cdk.App, id: string, props?: StackProps) {
    super(scope, id, props)

    const rawCfg = this.node.tryGetContext('backendLambda')
    const cfg = (() => {
      if (typeof rawCfg === 'string') {
        try {
          return JSON.parse(rawCfg) as BackendLambdaContext
        } catch {
          return {}
        }
      }
      return (rawCfg || {}) as BackendLambdaContext
    })()

    const apiName = cfg.apiName ?? 'estimation-backend-next'
    const stageName = cfg.stageName ?? 'prod'
    const timeoutSeconds = Number(cfg.timeoutSeconds ?? 60)
    const memorySize = Number(cfg.memorySize ?? 512)
    const legacyBackendUrl = String(cfg.legacyBackendUrl ?? '').trim().replace(/\/+$/, '')

    const handler = new lambda.Function(this, 'BackendNextHandler', {
      functionName: `${apiName}-handler`,
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambda', 'backend-next')),
      timeout: cdk.Duration.seconds(timeoutSeconds),
      memorySize,
      environment: {
        LEGACY_BASE_URL: legacyBackendUrl,
        ...(cfg.env || {}),
      },
    })

    const accessLogs = new logs.LogGroup(this, 'BackendNextApiAccessLogs', {
      retention: logs.RetentionDays.TWO_WEEKS,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    })

    const api = new apigateway.LambdaRestApi(this, 'BackendNextApi', {
      restApiName: apiName,
      handler,
      proxy: true,
      binaryMediaTypes: ['application/pdf', 'application/octet-stream'],
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['*'],
      },
      deployOptions: {
        stageName,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: true,
        metricsEnabled: true,
        accessLogDestination: new apigateway.LogGroupLogDestination(accessLogs),
        accessLogFormat: apigateway.AccessLogFormat.jsonWithStandardFields({
          caller: true,
          httpMethod: true,
          ip: true,
          protocol: true,
          requestTime: true,
          resourcePath: true,
          responseLength: true,
          status: true,
          user: true,
        }),
      },
    })

    const apiDomain = cdk.Fn.select(2, cdk.Fn.split('/', api.url))
    new CfnOutput(this, 'BackendLambdaApiUrl', {
      value: api.url,
    })
    new CfnOutput(this, 'BackendLambdaApiDomain', {
      value: apiDomain,
    })
    new CfnOutput(this, 'BackendLambdaStageName', {
      value: stageName,
    })
    new CfnOutput(this, 'BackendNextHandlerName', {
      value: handler.functionName,
    })
  }
}
