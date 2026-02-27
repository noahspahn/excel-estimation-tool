"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.FrontendStack = void 0;
const cdk = __importStar(require("aws-cdk-lib"));
const aws_cdk_lib_1 = require("aws-cdk-lib");
const cloudfront = __importStar(require("aws-cdk-lib/aws-cloudfront"));
const origins = __importStar(require("aws-cdk-lib/aws-cloudfront-origins"));
const s3 = __importStar(require("aws-cdk-lib/aws-s3"));
const s3deploy = __importStar(require("aws-cdk-lib/aws-s3-deployment"));
const url_1 = require("url");
function resolveApiOrigin(domainInput, urlInput, protocolInput) {
    const domainValue = (domainInput || '').trim();
    const urlValue = (urlInput || '').trim();
    if (domainValue) {
        return {
            domain: domainValue,
            protocol: protocolInput ?? 'https',
        };
    }
    if (!urlValue) {
        return undefined;
    }
    try {
        const parsed = new url_1.URL(urlValue);
        return {
            domain: parsed.hostname,
            protocol: protocolInput ?? (parsed.protocol === 'http:' ? 'http' : 'https'),
            originPath: parsed.pathname && parsed.pathname !== '/' ? parsed.pathname.replace(/\/+$/, '') : undefined,
        };
    }
    catch {
        return {
            domain: urlValue,
            protocol: protocolInput ?? 'https',
        };
    }
}
class FrontendStack extends aws_cdk_lib_1.Stack {
    constructor(scope, id, props) {
        super(scope, id, props);
        const rawCfg = this.node.tryGetContext('frontend');
        const cfg = (() => {
            if (typeof rawCfg === 'string') {
                try {
                    return JSON.parse(rawCfg);
                }
                catch {
                    return {};
                }
            }
            return (rawCfg || {});
        })();
        const bucket = new s3.Bucket(this, 'FrontendBucket', {
            bucketName: cfg.bucketName,
            blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
            enforceSSL: true,
            removalPolicy: cdk.RemovalPolicy.RETAIN,
        });
        const additionalBehaviors = {};
        const apiOrigin = resolveApiOrigin(cfg.apiDomain, cfg.apiUrl, cfg.apiProtocol);
        if (apiOrigin) {
            additionalBehaviors['api/*'] = {
                origin: new origins.HttpOrigin(apiOrigin.domain, {
                    protocolPolicy: apiOrigin.protocol === 'http'
                        ? cloudfront.OriginProtocolPolicy.HTTP_ONLY
                        : cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
                    originPath: apiOrigin.originPath,
                }),
                allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
                cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
                originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            };
        }
        const nextApiOrigin = resolveApiOrigin(cfg.nextApiDomain, cfg.nextApiUrl, cfg.nextApiProtocol);
        if (nextApiOrigin) {
            additionalBehaviors['api-next/*'] = {
                origin: new origins.HttpOrigin(nextApiOrigin.domain, {
                    protocolPolicy: nextApiOrigin.protocol === 'http'
                        ? cloudfront.OriginProtocolPolicy.HTTP_ONLY
                        : cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
                    originPath: nextApiOrigin.originPath,
                }),
                allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
                cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
                originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            };
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
        });
        const deployAssets = Boolean(cfg.deployAssets);
        if (deployAssets && cfg.assetPath) {
            new s3deploy.BucketDeployment(this, 'FrontendDeployment', {
                sources: [s3deploy.Source.asset(cfg.assetPath)],
                destinationBucket: bucket,
                distribution,
                distributionPaths: ['/*'],
            });
        }
        new aws_cdk_lib_1.CfnOutput(this, 'FrontendBucketName', { value: bucket.bucketName });
        new aws_cdk_lib_1.CfnOutput(this, 'FrontendDistributionId', { value: distribution.distributionId });
        new aws_cdk_lib_1.CfnOutput(this, 'FrontendUrl', { value: `https://${distribution.domainName}` });
    }
}
exports.FrontendStack = FrontendStack;
