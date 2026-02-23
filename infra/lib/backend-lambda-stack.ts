import * as cdk from 'aws-cdk-lib'
import { CfnOutput, Stack, StackProps } from 'aws-cdk-lib'
import * as apigateway from 'aws-cdk-lib/aws-apigateway'
import * as iam from 'aws-cdk-lib/aws-iam'
import * as lambda from 'aws-cdk-lib/aws-lambda'
import * as logs from 'aws-cdk-lib/aws-logs'
import * as path from 'path'

type BackendLambdaContext = {
  apiName?: string
  stageName?: string
  mode?: 'fastapi' | 'router'
  legacyBackendUrl?: string
  timeoutSeconds?: number | string
  apiTimeoutSeconds?: number | string
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
    const mode = cfg.mode === 'router' ? 'router' : 'fastapi'
    const lambdaTimeoutSeconds = Number(cfg.timeoutSeconds ?? 60)
    const apiTimeoutSeconds = Number(cfg.apiTimeoutSeconds ?? 29)
    const normalizedLambdaTimeoutSeconds =
      Number.isFinite(lambdaTimeoutSeconds) && lambdaTimeoutSeconds > 0
        ? Math.floor(lambdaTimeoutSeconds)
        : 60
    const normalizedApiTimeoutSeconds =
      Number.isFinite(apiTimeoutSeconds) && apiTimeoutSeconds > 0 ? Math.floor(apiTimeoutSeconds) : 29
    const effectiveApiTimeoutSeconds = Math.min(normalizedApiTimeoutSeconds, normalizedLambdaTimeoutSeconds)
    const memorySize = Number(cfg.memorySize ?? 512)
    const legacyBackendUrl = String(cfg.legacyBackendUrl ?? '').trim().replace(/\/+$/, '')
    const reservedLambdaEnvKeys = new Set(['AWS_REGION', 'AWS_DEFAULT_REGION'])
    const droppedKeys: string[] = []
    const envVars: Record<string, string> = {}
    for (const [key, value] of Object.entries(cfg.env || {})) {
      if (reservedLambdaEnvKeys.has(key)) {
        droppedKeys.push(key)
        continue
      }
      envVars[key] = value
    }
    envVars.BACKEND_MODE = 'api-next'
    if (droppedKeys.length > 0) {
      cdk.Annotations.of(this).addWarning(
        `Ignoring reserved Lambda environment variable(s): ${droppedKeys.join(', ')}`,
      )
    }

    let handler: lambda.IFunction
    if (mode === 'router') {
      if (!legacyBackendUrl) {
        throw new Error(
          'backendLambda.legacyBackendUrl is required in router mode. Example: ' +
            `-c backendLambda='{"mode":"router","legacyBackendUrl":"https://<app-runner-domain>"}'`,
        )
      }
      handler = new lambda.Function(this, 'BackendNextHandler', {
        functionName: `${apiName}-handler`,
        runtime: lambda.Runtime.PYTHON_3_11,
        handler: 'index.handler',
        code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambda', 'backend-next')),
        timeout: cdk.Duration.seconds(normalizedLambdaTimeoutSeconds),
        memorySize,
        environment: {
          LEGACY_BASE_URL: legacyBackendUrl,
          ...envVars,
        },
      })
    } else {
      handler = new lambda.DockerImageFunction(this, 'BackendNextHandler', {
        functionName: `${apiName}-handler`,
        code: lambda.DockerImageCode.fromImageAsset(path.join(__dirname, '..', '..', 'backend'), {
          file: 'Dockerfile.lambda',
        }),
        timeout: cdk.Duration.seconds(normalizedLambdaTimeoutSeconds),
        memorySize,
        environment: envVars,
      })
    }

    if (mode === 'fastapi' && handler instanceof lambda.Function) {
      handler.addToRolePolicy(
        new iam.PolicyStatement({
          actions: ['lambda:InvokeFunction'],
          resources: [handler.functionArn],
        }),
      )
    }

    const accessLogs = new logs.LogGroup(this, 'BackendNextApiAccessLogs', {
      retention: logs.RetentionDays.TWO_WEEKS,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    })

    const api = new apigateway.LambdaRestApi(this, 'BackendNextApi', {
      restApiName: apiName,
      handler,
      proxy: true,
      integrationOptions: {
        timeout: cdk.Duration.seconds(effectiveApiTimeoutSeconds),
      },
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
    new CfnOutput(this, 'BackendLambdaMode', {
      value: mode,
    })
    new CfnOutput(this, 'BackendLambdaApiTimeoutSeconds', {
      value: String(effectiveApiTimeoutSeconds),
    })
  }
}
