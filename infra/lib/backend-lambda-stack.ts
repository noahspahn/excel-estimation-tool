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
    const configuredProposalsTableName = (envVars.PROPOSALS_TABLE_NAME || '').trim()
    let proposalsTable: dynamodb.ITable
    let proposalsTableName = configuredProposalsTableName
    if (configuredProposalsTableName) {
      proposalsTable = dynamodb.Table.fromTableName(
        this,
        'ProposalsTableRef',
        configuredProposalsTableName,
      )
    } else {
      const createdProposalsTable = new dynamodb.Table(this, 'ProposalsTable', {
        partitionKey: { name: 'proposal_id', type: dynamodb.AttributeType.STRING },
        billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
        pointInTimeRecovery: true,
        removalPolicy: cdk.RemovalPolicy.RETAIN,
      })
      createdProposalsTable.addGlobalSecondaryIndex({
        indexName: 'public-id-index',
        partitionKey: { name: 'public_id', type: dynamodb.AttributeType.STRING },
      })
      proposalsTable = createdProposalsTable
      proposalsTableName = createdProposalsTable.tableName
      envVars.PROPOSALS_TABLE_NAME = proposalsTableName
    }
    const configuredProposalVersionsTableName = (envVars.PROPOSAL_VERSIONS_TABLE_NAME || '').trim()
    let proposalVersionsTable: dynamodb.ITable
    let proposalVersionsTableName = configuredProposalVersionsTableName
    if (configuredProposalVersionsTableName) {
      proposalVersionsTable = dynamodb.Table.fromTableName(
        this,
        'ProposalVersionsTableRef',
        configuredProposalVersionsTableName,
      )
    } else {
      const createdProposalVersionsTable = new dynamodb.Table(this, 'ProposalVersionsTable', {
        partitionKey: { name: 'proposal_id', type: dynamodb.AttributeType.STRING },
        sortKey: { name: 'version', type: dynamodb.AttributeType.NUMBER },
        billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
        pointInTimeRecovery: true,
        removalPolicy: cdk.RemovalPolicy.RETAIN,
      })
      proposalVersionsTable = createdProposalVersionsTable
      proposalVersionsTableName = createdProposalVersionsTable.tableName
      envVars.PROPOSAL_VERSIONS_TABLE_NAME = proposalVersionsTableName
    }
    const configuredProposalDocumentsTableName = (envVars.PROPOSAL_DOCUMENTS_TABLE_NAME || '').trim()
    let proposalDocumentsTable: dynamodb.ITable
    let proposalDocumentsTableName = configuredProposalDocumentsTableName
    if (configuredProposalDocumentsTableName) {
      proposalDocumentsTable = dynamodb.Table.fromTableName(
        this,
        'ProposalDocumentsTableRef',
        configuredProposalDocumentsTableName,
      )
    } else {
      const createdProposalDocumentsTable = new dynamodb.Table(this, 'ProposalDocumentsTable', {
        partitionKey: { name: 'proposal_id', type: dynamodb.AttributeType.STRING },
        sortKey: { name: 'document_id', type: dynamodb.AttributeType.STRING },
        billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
        pointInTimeRecovery: true,
        removalPolicy: cdk.RemovalPolicy.RETAIN,
      })
      proposalDocumentsTable = createdProposalDocumentsTable
      proposalDocumentsTableName = createdProposalDocumentsTable.tableName
      envVars.PROPOSAL_DOCUMENTS_TABLE_NAME = proposalDocumentsTableName
    }
    const configuredContractsTableName = (envVars.CONTRACTS_TABLE_NAME || '').trim()
    let contractsTable: dynamodb.ITable
    let contractsTableName = configuredContractsTableName
    if (configuredContractsTableName) {
      contractsTable = dynamodb.Table.fromTableName(
        this,
        'ContractsTableRef',
        configuredContractsTableName,
      )
    } else {
      const createdContractsTable = new dynamodb.Table(this, 'ContractsTable', {
        partitionKey: { name: 'contract_id', type: dynamodb.AttributeType.STRING },
        billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
        pointInTimeRecovery: true,
        removalPolicy: cdk.RemovalPolicy.RETAIN,
      })
      createdContractsTable.addGlobalSecondaryIndex({
        indexName: 'source-id-index',
        partitionKey: { name: 'source', type: dynamodb.AttributeType.STRING },
        sortKey: { name: 'source_id', type: dynamodb.AttributeType.STRING },
      })
      contractsTable = createdContractsTable
      contractsTableName = createdContractsTable.tableName
      envVars.CONTRACTS_TABLE_NAME = contractsTableName
    }
    const configuredContractSyncTableName = (envVars.CONTRACT_SYNC_TABLE_NAME || '').trim()
    let contractSyncTable: dynamodb.ITable
    let contractSyncTableName = configuredContractSyncTableName
    if (configuredContractSyncTableName) {
      contractSyncTable = dynamodb.Table.fromTableName(
        this,
        'ContractSyncTableRef',
        configuredContractSyncTableName,
      )
    } else {
      const createdContractSyncTable = new dynamodb.Table(this, 'ContractSyncTable', {
        partitionKey: { name: 'source', type: dynamodb.AttributeType.STRING },
        billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
        pointInTimeRecovery: true,
        removalPolicy: cdk.RemovalPolicy.RETAIN,
      })
      contractSyncTable = createdContractSyncTable
      contractSyncTableName = createdContractSyncTable.tableName
      envVars.CONTRACT_SYNC_TABLE_NAME = contractSyncTableName
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

    handler.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['lambda:InvokeFunction'],
        // Include qualified and unqualified function ARNs so self-invoke works
        // regardless of whether Lambda resolves to $LATEST or a versioned ARN.
        resources: [handler.functionArn, `${handler.functionArn}:*`],
      }),
    )
    reportJobsTable.grantReadWriteData(handler)
    proposalsTable.grantReadWriteData(handler)
    proposalVersionsTable.grantReadWriteData(handler)
    proposalDocumentsTable.grantReadWriteData(handler)
    contractsTable.grantReadWriteData(handler)
    contractSyncTable.grantReadWriteData(handler)
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
    new CfnOutput(this, 'ProposalsTableName', {
      value: proposalsTableName,
    })
    new CfnOutput(this, 'ProposalVersionsTableName', {
      value: proposalVersionsTableName,
    })
    new CfnOutput(this, 'ProposalDocumentsTableName', {
      value: proposalDocumentsTableName,
    })
    new CfnOutput(this, 'ContractsTableName', {
      value: contractsTableName,
    })
    new CfnOutput(this, 'ContractSyncTableName', {
      value: contractSyncTableName,
    })
    new CfnOutput(this, 'BackendLambdaApiTimeoutSeconds', {
      value: String(effectiveApiTimeoutSeconds),
    })
  }
}
