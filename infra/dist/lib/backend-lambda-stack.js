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
exports.BackendLambdaStack = void 0;
const cdk = __importStar(require("aws-cdk-lib"));
const aws_cdk_lib_1 = require("aws-cdk-lib");
const apigateway = __importStar(require("aws-cdk-lib/aws-apigateway"));
const iam = __importStar(require("aws-cdk-lib/aws-iam"));
const lambda = __importStar(require("aws-cdk-lib/aws-lambda"));
const logs = __importStar(require("aws-cdk-lib/aws-logs"));
const path = __importStar(require("path"));
class BackendLambdaStack extends aws_cdk_lib_1.Stack {
    constructor(scope, id, props) {
        super(scope, id, props);
        const rawCfg = this.node.tryGetContext('backendLambda');
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
        const apiName = cfg.apiName ?? 'estimation-backend-next';
        const stageName = cfg.stageName ?? 'prod';
        const mode = cfg.mode === 'router' ? 'router' : 'fastapi';
        const lambdaTimeoutSeconds = Number(cfg.timeoutSeconds ?? 60);
        const apiTimeoutSeconds = Number(cfg.apiTimeoutSeconds ?? 29);
        const normalizedLambdaTimeoutSeconds = Number.isFinite(lambdaTimeoutSeconds) && lambdaTimeoutSeconds > 0
            ? Math.floor(lambdaTimeoutSeconds)
            : 60;
        const normalizedApiTimeoutSeconds = Number.isFinite(apiTimeoutSeconds) && apiTimeoutSeconds > 0 ? Math.floor(apiTimeoutSeconds) : 29;
        const effectiveApiTimeoutSeconds = Math.min(normalizedApiTimeoutSeconds, normalizedLambdaTimeoutSeconds);
        const memorySize = Number(cfg.memorySize ?? 512);
        const legacyBackendUrl = String(cfg.legacyBackendUrl ?? '').trim().replace(/\/+$/, '');
        const reservedLambdaEnvKeys = new Set(['AWS_REGION', 'AWS_DEFAULT_REGION']);
        const droppedKeys = [];
        const envVars = {};
        for (const [key, value] of Object.entries(cfg.env || {})) {
            if (reservedLambdaEnvKeys.has(key)) {
                droppedKeys.push(key);
                continue;
            }
            envVars[key] = value;
        }
        envVars.BACKEND_MODE = 'api-next';
        if (droppedKeys.length > 0) {
            cdk.Annotations.of(this).addWarning(`Ignoring reserved Lambda environment variable(s): ${droppedKeys.join(', ')}`);
        }
        let handler;
        if (mode === 'router') {
            if (!legacyBackendUrl) {
                throw new Error('backendLambda.legacyBackendUrl is required in router mode. Example: ' +
                    `-c backendLambda='{"mode":"router","legacyBackendUrl":"https://<app-runner-domain>"}'`);
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
            });
        }
        else {
            handler = new lambda.DockerImageFunction(this, 'BackendNextHandler', {
                functionName: `${apiName}-handler`,
                code: lambda.DockerImageCode.fromImageAsset(path.join(__dirname, '..', '..', 'backend'), {
                    file: 'Dockerfile.lambda',
                }),
                timeout: cdk.Duration.seconds(normalizedLambdaTimeoutSeconds),
                memorySize,
                environment: envVars,
            });
        }
        if (mode === 'fastapi' && handler instanceof lambda.Function) {
            const selfInvokeArn = cdk.Stack.of(this).formatArn({
                service: 'lambda',
                resource: 'function',
                resourceName: `${apiName}-handler`,
            });
            handler.addToRolePolicy(new iam.PolicyStatement({
                actions: ['lambda:InvokeFunction'],
                resources: [selfInvokeArn],
            }));
        }
        const accessLogs = new logs.LogGroup(this, 'BackendNextApiAccessLogs', {
            retention: logs.RetentionDays.TWO_WEEKS,
            removalPolicy: cdk.RemovalPolicy.RETAIN,
        });
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
        });
        const apiDomain = cdk.Fn.select(2, cdk.Fn.split('/', api.url));
        new aws_cdk_lib_1.CfnOutput(this, 'BackendLambdaApiUrl', {
            value: api.url,
        });
        new aws_cdk_lib_1.CfnOutput(this, 'BackendLambdaApiDomain', {
            value: apiDomain,
        });
        new aws_cdk_lib_1.CfnOutput(this, 'BackendLambdaStageName', {
            value: stageName,
        });
        new aws_cdk_lib_1.CfnOutput(this, 'BackendNextHandlerName', {
            value: handler.functionName,
        });
        new aws_cdk_lib_1.CfnOutput(this, 'BackendLambdaMode', {
            value: mode,
        });
        new aws_cdk_lib_1.CfnOutput(this, 'BackendLambdaApiTimeoutSeconds', {
            value: String(effectiveApiTimeoutSeconds),
        });
    }
}
exports.BackendLambdaStack = BackendLambdaStack;
