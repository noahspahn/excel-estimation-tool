import * as cdk from 'aws-cdk-lib'
import { CfnOutput, Stack, StackProps } from 'aws-cdk-lib'
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront'
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins'
import * as s3 from 'aws-cdk-lib/aws-s3'
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment'
import { URL } from 'url'

type FrontendContext = {
  bucketName?: string
  deployAssets?: boolean
  assetPath?: string
  apiDomain?: string
  apiUrl?: string
  apiProtocol?: 'http' | 'https'
  nextApiDomain?: string
  nextApiUrl?: string
  nextApiProtocol?: 'http' | 'https'
}

type ApiOriginConfig = {
  domain: string
  protocol: 'http' | 'https'
  originPath?: string
}

function resolveApiOrigin(
  domainInput?: string,
  urlInput?: string,
  protocolInput?: 'http' | 'https',
): ApiOriginConfig | undefined {
  const domainValue = (domainInput || '').trim()
  const urlValue = (urlInput || '').trim()

  if (domainValue) {
    return {
      domain: domainValue,
      protocol: protocolInput ?? 'https',
    }
  }

  if (!urlValue) {
    return undefined
  }

  try {
    const parsed = new URL(urlValue)
    return {
      domain: parsed.hostname,
      protocol: protocolInput ?? (parsed.protocol === 'http:' ? 'http' : 'https'),
      originPath: parsed.pathname && parsed.pathname !== '/' ? parsed.pathname.replace(/\/+$/, '') : undefined,
    }
  } catch {
    return {
      domain: urlValue,
      protocol: protocolInput ?? 'https',
    }
  }
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

    const additionalBehaviors: Record<string, cloudfront.BehaviorOptions> = {}

    const apiOrigin = resolveApiOrigin(cfg.apiDomain, cfg.apiUrl, cfg.apiProtocol)
    if (apiOrigin) {
      additionalBehaviors['api/*'] = {
        origin: new origins.HttpOrigin(apiOrigin.domain, {
          protocolPolicy:
            apiOrigin.protocol === 'http'
              ? cloudfront.OriginProtocolPolicy.HTTP_ONLY
              : cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
          originPath: apiOrigin.originPath,
        }),
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      }
    }

    const nextApiOrigin = resolveApiOrigin(cfg.nextApiDomain, cfg.nextApiUrl, cfg.nextApiProtocol)
    if (nextApiOrigin) {
      additionalBehaviors['api-next/*'] = {
        origin: new origins.HttpOrigin(nextApiOrigin.domain, {
          protocolPolicy:
            nextApiOrigin.protocol === 'http'
              ? cloudfront.OriginProtocolPolicy.HTTP_ONLY
              : cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
          originPath: nextApiOrigin.originPath,
        }),
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      }
    }

    const distribution = new cloudfront.Distribution(this, 'FrontendDistribution', {
      defaultRootObject: 'index.html',
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(bucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      },
      additionalBehaviors: Object.keys(additionalBehaviors).length ? additionalBehaviors : undefined,
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
