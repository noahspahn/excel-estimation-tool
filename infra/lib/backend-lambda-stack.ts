import * as cdk from 'aws-cdk-lib'
import { CfnOutput, Stack, StackProps } from 'aws-cdk-lib'
import * as apigateway from 'aws-cdk-lib/aws-apigateway'
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb'
import * as iam from 'aws-cdk-lib/aws-iam'
import * as lambda from 'aws-cdk-lib/aws-lambda'
import * as logs from 'aws-cdk-lib/aws-logs'
import * as s3 from 'aws-cdk-lib/aws-s3'
import * as path from 'path'

type BackendLambdaContext = {
  apiName?: string
  stageName?: string
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
    const functionName = `${apiName}-handler`
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
    const configuredReportJobsTableName = (envVars.REPORT_JOBS_TABLE_NAME || '').trim()
    let reportJobsTable: dynamodb.ITable
    let reportJobsTableName = configuredReportJobsTableName
    if (configuredReportJobsTableName) {
      reportJobsTable = dynamodb.Table.fromTableName(
        this,
        'ReportJobsTableRef',
        configuredReportJobsTableName,
      )
    } else {
      const createdReportJobsTable = new dynamodb.Table(this, 'ReportJobsTable', {
        partitionKey: { name: 'job_id', type: dynamodb.AttributeType.STRING },
        billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
        pointInTimeRecovery: true,
        removalPolicy: cdk.RemovalPolicy.RETAIN,
      })
      reportJobsTable = createdReportJobsTable
      reportJobsTableName = createdReportJobsTable.tableName
      envVars.REPORT_JOBS_TABLE_NAME = reportJobsTableName
    }
    envVars.BACKEND_MODE = 'lambda'
    if (droppedKeys.length > 0) {
      cdk.Annotations.of(this).addWarning(
        `Ignoring reserved Lambda environment variable(s): ${droppedKeys.join(', ')}`,
      )
    }

    const handler = new lambda.DockerImageFunction(this, 'BackendNextHandler', {
      functionName,
      code: lambda.DockerImageCode.fromImageAsset(path.join(__dirname, '..', '..', 'backend'), {
        file: 'Dockerfile.lambda',
      }),
      timeout: cdk.Duration.seconds(normalizedLambdaTimeoutSeconds),
      memorySize,
      environment: envVars,
    })

    const selfInvokeArn = cdk.Stack.of(this).formatArn({
      service: 'lambda',
      resource: 'function',
      resourceName: functionName,
    })
    handler.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['lambda:InvokeFunction'],
        resources: [selfInvokeArn],
      }),
    )
    reportJobsTable.grantReadWriteData(handler)
    const reportsTableName = (envVars.REPORTS_TABLE_NAME || '').trim()
    if (reportsTableName) {
      const reportsTable = dynamodb.Table.fromTableName(this, 'ReportsTableRef', reportsTableName)
      reportsTable.grantReadWriteData(handler)
    }

    const bucketNames = new Set(
      [envVars.S3_REPORT_BUCKET, envVars.S3_BUCKET].map((v) => String(v || '').trim()).filter(Boolean),
    )
    let bucketRefIdx = 0
    for (const bucketName of bucketNames) {
      const bucket = s3.Bucket.fromBucketName(this, `ReportsBucketRef${bucketRefIdx}`, bucketName)
      bucket.grantReadWrite(handler)
      bucketRefIdx += 1
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
    new CfnOutput(this, 'ReportJobsTableName', {
      value: reportJobsTableName,
    })
    new CfnOutput(this, 'BackendLambdaApiTimeoutSeconds', {
      value: String(effectiveApiTimeoutSeconds),
    })
  }
}
