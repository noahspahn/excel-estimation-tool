import * as cdk from 'aws-cdk-lib'
import { CfnOutput, Stack, StackProps } from 'aws-cdk-lib'
import * as apprunner from 'aws-cdk-lib/aws-apprunner'
import * as ecr from 'aws-cdk-lib/aws-ecr'
import * as iam from 'aws-cdk-lib/aws-iam'
import * as cognito from 'aws-cdk-lib/aws-cognito'
import * as ec2 from 'aws-cdk-lib/aws-ec2'
import * as rds from 'aws-cdk-lib/aws-rds'
import * as s3 from 'aws-cdk-lib/aws-s3'
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb'

type BackendContext = {
  serviceName?: string
  ecrRepoName?: string
  existingRepoName?: string
  useExistingRepo?: boolean
  createRepo?: boolean
  createService?: boolean
  createDatabase?: boolean
  dbName?: string
  dbUser?: string
  dbInstanceClass?: string
  dbInstanceSize?: string
  useDefaultVpc?: boolean
  reportBucketName?: string
  reportsTableName?: string
  imageTag?: string
  containerPort?: number | string
  cpu?: string
  memory?: string
  env?: Record<string, string>
}

export class BackendStack extends Stack {
  constructor(scope: cdk.App, id: string, props?: StackProps) {
    super(scope, id, props)

    const rawCfg = this.node.tryGetContext('backend')
    const cfg = (() => {
      if (typeof rawCfg === 'string') {
        try {
          return JSON.parse(rawCfg) as BackendContext
        } catch {
          return {}
        }
      }
      return (rawCfg || {}) as BackendContext
    })()
    const serviceName = cfg.serviceName ?? 'estimation-backend'
    const repoName = cfg.ecrRepoName ?? 'estimation-backend'
    const imageTag = cfg.imageTag ?? 'latest'
    const containerPort = String(cfg.containerPort ?? 8000)
    const cpu = cfg.cpu ?? '1024'
    const memory = cfg.memory ?? '2048'
    const shouldCreateService = cfg.createService !== false
    const shouldCreateDatabase = cfg.createDatabase !== false
    const reportBucketName = cfg.reportBucketName
    const reportsTableName = cfg.reportsTableName

    const shouldCreateRepo = cfg.createRepo === true
    const repoLookupName = cfg.existingRepoName ?? repoName
    const repo: ecr.IRepository = shouldCreateRepo
      ? new ecr.Repository(this, 'BackendRepo', {
        repositoryName: repoName,
        removalPolicy: cdk.RemovalPolicy.RETAIN,
      })
      : ecr.Repository.fromRepositoryName(this, 'BackendRepo', repoLookupName)

    const vpc = cfg.useDefaultVpc
      ? ec2.Vpc.fromLookup(this, 'DefaultVpc', { isDefault: true })
      : new ec2.Vpc(this, 'AppVpc', {
        maxAzs: 2,
        natGateways: 1,
      })

    const appRunnerSecurityGroup = new ec2.SecurityGroup(this, 'AppRunnerSecurityGroup', {
      vpc,
      description: 'Security group for App Runner VPC connector',
      allowAllOutbound: true,
    })

    const privateSubnets = vpc.selectSubnets({ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS })
    const subnetIds = privateSubnets.subnetIds.length
      ? privateSubnets.subnetIds
      : vpc.selectSubnets({ subnetType: ec2.SubnetType.PUBLIC }).subnetIds

    const vpcConnector = new apprunner.CfnVpcConnector(this, 'AppRunnerVpcConnector', {
      vpcConnectorName: `${serviceName}-vpc`,
      subnets: subnetIds,
      securityGroups: [appRunnerSecurityGroup.securityGroupId],
    })

    const userPool = new cognito.UserPool(this, 'UserPool', {
      userPoolName: `${serviceName}-users`,
      selfSignUpEnabled: true,
      signInAliases: { email: true },
      autoVerify: { email: true },
      standardAttributes: { email: { required: true, mutable: true } },
    })

    const userPoolClient = new cognito.UserPoolClient(this, 'UserPoolClient', {
      userPool,
      generateSecret: false,
      authFlows: {
        userPassword: true,
        userSrp: true,
        adminUserPassword: true,
      },
    })

    const reportsBucket = new s3.Bucket(this, 'ReportsBucket', {
      bucketName: reportBucketName,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    })

    const reportsTable = new dynamodb.Table(this, 'ReportsTable', {
      tableName: reportsTableName,
      partitionKey: { name: 'owner_email', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'report_id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecoverySpecification: {
        pointInTimeRecoveryEnabled: true,
      },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    })

    let dbInstance: rds.DatabaseInstance | null = null
    let databaseUrl: string | null = null
    const dbName = cfg.dbName ?? 'estimation_db'
    const dbUser = cfg.dbUser ?? 'postgres'
    if (shouldCreateDatabase) {
      const dbSecurityGroup = new ec2.SecurityGroup(this, 'DatabaseSecurityGroup', {
        vpc,
        description: 'Security group for Postgres',
      })
      dbSecurityGroup.addIngressRule(
        appRunnerSecurityGroup,
        ec2.Port.tcp(5432),
        'Allow App Runner to access Postgres'
      )

      const classKey = String(cfg.dbInstanceClass ?? 't3').toUpperCase()
      const sizeKey = String(cfg.dbInstanceSize ?? 'micro').toUpperCase()
      const instanceClass =
        (ec2.InstanceClass as Record<string, ec2.InstanceClass>)[classKey] ?? ec2.InstanceClass.T3
      const instanceSize =
        (ec2.InstanceSize as Record<string, ec2.InstanceSize>)[sizeKey] ?? ec2.InstanceSize.MICRO

      dbInstance = new rds.DatabaseInstance(this, 'Postgres', {
        engine: rds.DatabaseInstanceEngine.postgres({ version: rds.PostgresEngineVersion.VER_15_15 }),
        vpc,
        vpcSubnets: privateSubnets.subnetIds.length
          ? { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }
          : { subnetType: ec2.SubnetType.PUBLIC },
        credentials: rds.Credentials.fromGeneratedSecret(dbUser),
        instanceType: ec2.InstanceType.of(instanceClass as ec2.InstanceClass, instanceSize as ec2.InstanceSize),
        databaseName: dbName,
        multiAz: false,
        allocatedStorage: 20,
        maxAllocatedStorage: 100,
        publiclyAccessible: false,
        securityGroups: [dbSecurityGroup],
        deletionProtection: false,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      })

      const dbPassword = dbInstance.secret?.secretValueFromJson('password').toString() || ''
      databaseUrl = cdk.Fn.join('', [
        'postgresql://',
        dbUser,
        ':',
        dbPassword,
        '@',
        dbInstance.dbInstanceEndpointAddress,
        ':',
        dbInstance.dbInstanceEndpointPort,
        '/',
        dbName,
        '?sslmode=require',
      ])
    }

    const envVars = {
      AUTH_REQUIRED: 'true',
      AWS_REGION: Stack.of(this).region,
      COGNITO_REGION: Stack.of(this).region,
      COGNITO_USER_POOL_ID: userPool.userPoolId,
      COGNITO_CLIENT_ID: userPoolClient.userPoolClientId,
      S3_REPORT_BUCKET: reportsBucket.bucketName,
      REPORTS_TABLE_NAME: reportsTable.tableName,
      ...(databaseUrl ? { DATABASE_URL: databaseUrl } : {}),
      ...(cfg.env || {}),
    }
    const runtimeEnv = Object.entries(envVars).map(([name, value]) => ({
      name,
      value: String(value),
    }))

    if (shouldCreateService) {
      const runtimeRole = new iam.Role(this, 'AppRunnerRuntimeRole', {
        assumedBy: new iam.ServicePrincipal('tasks.apprunner.amazonaws.com'),
        description: 'Runtime role for App Runner backend service',
      })
      reportsBucket.grantReadWrite(runtimeRole)
      reportsTable.grantReadWriteData(runtimeRole)

      const accessRole = new iam.Role(this, 'AppRunnerEcrAccessRole', {
        assumedBy: new iam.ServicePrincipal('build.apprunner.amazonaws.com'),
        description: 'App Runner access role for ECR image pulls',
      })
      accessRole.addManagedPolicy(
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSAppRunnerServicePolicyForECRAccess')
      )

      const service = new apprunner.CfnService(this, 'BackendService', {
        serviceName,
        sourceConfiguration: {
          autoDeploymentsEnabled: true,
          authenticationConfiguration: { accessRoleArn: accessRole.roleArn },
          imageRepository: {
            imageIdentifier: `${repo.repositoryUri}:${imageTag}`,
            imageRepositoryType: 'ECR',
            imageConfiguration: {
              port: containerPort,
              runtimeEnvironmentVariables: runtimeEnv,
            },
          },
        },
        networkConfiguration: {
          egressConfiguration: {
            egressType: 'VPC',
            vpcConnectorArn: vpcConnector.attrVpcConnectorArn,
          },
        },
        instanceConfiguration: {
          cpu,
          memory,
          instanceRoleArn: runtimeRole.roleArn,
        },
      })
      service.addDependency(vpcConnector)

      new CfnOutput(this, 'BackendServiceUrl', {
        value: service.attrServiceUrl,
      })
      new CfnOutput(this, 'BackendServiceArn', {
        value: service.attrServiceArn,
      })
    }
    new CfnOutput(this, 'BackendRepoUri', {
      value: repo.repositoryUri,
    })
    new CfnOutput(this, 'CognitoUserPoolId', {
      value: userPool.userPoolId,
    })
    new CfnOutput(this, 'CognitoUserPoolClientId', {
      value: userPoolClient.userPoolClientId,
    })
    new CfnOutput(this, 'CognitoRegion', {
      value: Stack.of(this).region,
    })
    new CfnOutput(this, 'ReportsBucketName', {
      value: reportsBucket.bucketName,
    })
    new CfnOutput(this, 'ReportsTableName', {
      value: reportsTable.tableName,
    })
    new CfnOutput(this, 'VpcConnectorArn', {
      value: vpcConnector.attrVpcConnectorArn,
    })
    new CfnOutput(this, 'VpcId', {
      value: vpc.vpcId,
    })
    if (dbInstance) {
      new CfnOutput(this, 'DatabaseEndpoint', {
        value: dbInstance.dbInstanceEndpointAddress,
      })
      new CfnOutput(this, 'DatabaseName', {
        value: dbName,
      })
      if (dbInstance.secret) {
        new CfnOutput(this, 'DatabaseSecretArn', {
          value: dbInstance.secret.secretArn,
        })
      }
    }
  }
}
