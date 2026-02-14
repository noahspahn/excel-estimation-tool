import * as cdk from 'aws-cdk-lib'
import { CfnOutput, Stack, StackProps } from 'aws-cdk-lib'
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront'
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins'
import * as s3 from 'aws-cdk-lib/aws-s3'
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment'

type FrontendContext = {
  bucketName?: string
  deployAssets?: boolean
  assetPath?: string
}

export class FrontendStack extends Stack {
  constructor(scope: cdk.App, id: string, props?: StackProps) {
    super(scope, id, props)

    const rawCfg = this.node.tryGetContext('frontend')
    const cfg = (() => {
      if (typeof rawCfg === 'string') {
        try {
          return JSON.parse(rawCfg) as FrontendContext
        } catch {
          return {}
        }
      }
      return (rawCfg || {}) as FrontendContext
    })()
    const bucket = new s3.Bucket(this, 'FrontendBucket', {
      bucketName: cfg.bucketName,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    })

    const distribution = new cloudfront.Distribution(this, 'FrontendDistribution', {
      defaultRootObject: 'index.html',
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(bucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      },
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
        },
      ],
    })

    const deployAssets = Boolean(cfg.deployAssets)
    if (deployAssets && cfg.assetPath) {
      new s3deploy.BucketDeployment(this, 'FrontendDeployment', {
        sources: [s3deploy.Source.asset(cfg.assetPath)],
        destinationBucket: bucket,
        distribution,
        distributionPaths: ['/*'],
      })
    }

    new CfnOutput(this, 'FrontendBucketName', { value: bucket.bucketName })
    new CfnOutput(this, 'FrontendDistributionId', { value: distribution.distributionId })
    new CfnOutput(this, 'FrontendUrl', { value: `https://${distribution.domainName}` })
  }
}
