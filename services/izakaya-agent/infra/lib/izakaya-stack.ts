import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as path from 'path';

export class IzakayaStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ========================================
    // Secrets Manager
    // ========================================

    const hotpepperApiKey = new secretsmanager.Secret(this, 'HotpepperApiKey', {
      secretName: 'izakaya-agent/hotpepper-api-key',
      description: 'Hotpepper Gourmet API Key',
    });

    const googlePlacesApiKey = new secretsmanager.Secret(this, 'GooglePlacesApiKey', {
      secretName: 'izakaya-agent/google-places-api-key',
      description: 'Google Places API Key',
    });

    const lineChannelSecret = new secretsmanager.Secret(this, 'LineChannelSecret', {
      secretName: 'izakaya-agent/line-channel-secret',
      description: 'LINE Channel Secret',
    });

    const lineChannelAccessToken = new secretsmanager.Secret(this, 'LineChannelAccessToken', {
      secretName: 'izakaya-agent/line-channel-access-token',
      description: 'LINE Channel Access Token',
    });

    // ========================================
    // IAM Role - Lambda実行ロール
    // ========================================

    const lambdaRole = new iam.Role(this, 'LambdaExecutionRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'LINE Webhook Lambda Execution Role',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Bedrock AgentCore Runtime呼び出し権限
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        'bedrock:InvokeAgent',
        'bedrock-agentcore:InvokeAgentRuntime',
      ],
      resources: ['*'],
      effect: iam.Effect.ALLOW,
    }));

    // Secrets Manager読み取り権限
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      actions: ['secretsmanager:GetSecretValue'],
      resources: [
        hotpepperApiKey.secretArn,
        googlePlacesApiKey.secretArn,
        lineChannelSecret.secretArn,
        lineChannelAccessToken.secretArn,
      ],
      effect: iam.Effect.ALLOW,
    }));

    // ========================================
    // AgentCore Runtime Role - A2A権限（Orchestrator → Worker）
    // ========================================

    const agentCoreRuntimeRole = iam.Role.fromRoleName(
      this,
      'AgentCoreRuntimeRole',
      'AmazonBedrockAgentCoreSDKRuntime-ap-northeast-1-1fcb41dc28',
    );

    agentCoreRuntimeRole.addToPrincipalPolicy(new iam.PolicyStatement({
      sid: 'AllowA2AInvokeWorker',
      actions: ['bedrock-agentcore:InvokeAgentRuntime'],
      resources: [
        'arn:aws:bedrock-agentcore:ap-northeast-1:921563379197:runtime/izakayaperspectiveworker_Agent-lzpXHR7q3i',
        'arn:aws:bedrock-agentcore:ap-northeast-1:921563379197:runtime/izakayaperspectiveworker_Agent-lzpXHR7q3i/*',
      ],
      effect: iam.Effect.ALLOW,
    }));

    // ========================================
    // Lambda Layer - Python Dependencies
    // ========================================

    const pythonDepsLayer = new lambda.LayerVersion(this, 'PythonDepsLayer', {
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda-layer')),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: 'Python dependencies (line-bot-sdk, boto3)',
    });

    // ========================================
    // Lambda Function - LINE Webhook
    // ========================================

    const webhookLambda = new lambda.Function(this, 'LineWebhookLambda', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda')),
      role: lambdaRole,
      functionName: 'izakaya-agent-line-webhook',
      description: 'LINE Webhook to Bedrock AgentCore',
      layers: [pythonDepsLayer],
      environment: {
        SECRETS_PREFIX: 'izakaya-agent/',
        RUNTIME_ARN: 'arn:aws:bedrock-agentcore:ap-northeast-1:921563379197:runtime/izakaya_agent-9JGtN3Enat',
        MEMORY_ID: process.env.MEMORY_ID || 'izakaya_agent_mem-ZOMh0R8tfz',
        CORS_ALLOWED_ORIGINS: 'http://localhost:3000,http://localhost:3001,http://localhost:3002,https://main.d2mtz6tk9wfbf0.amplifyapp.com',
        // v2 A2A対応: Perspective Worker Runtime ARN
        WORKER_RUNTIME_ARN: process.env.WORKER_RUNTIME_ARN || '',
      },
      timeout: cdk.Duration.seconds(60),
      memorySize: 256,
    });

    // Function URL有効化（認証なし、LINE署名検証で保護）
    const functionUrl = webhookLambda.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
    });

    // ========================================
    // CloudWatch Logs
    // ========================================

    const lambdaLogGroup = new logs.LogGroup(this, 'LambdaLogGroup', {
      logGroupName: `/aws/lambda/${webhookLambda.functionName}`,
      retention: logs.RetentionDays.TWO_WEEKS,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // ========================================
    // CloudWatch Alarms
    // ========================================

    // Lambda エラー率アラーム（5分間で3回以上エラー）
    const errorAlarm = new cloudwatch.Alarm(this, 'LambdaErrorAlarm', {
      alarmName: 'izakaya-agent-lambda-errors',
      alarmDescription: 'Lambda function error rate exceeds threshold',
      metric: webhookLambda.metricErrors({
        period: cdk.Duration.minutes(5),
        statistic: 'Sum',
      }),
      threshold: 3,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // Lambda レイテンシアラーム（P95 > 50秒）
    const latencyAlarm = new cloudwatch.Alarm(this, 'LambdaLatencyAlarm', {
      alarmName: 'izakaya-agent-lambda-latency',
      alarmDescription: 'Lambda function P95 latency exceeds 50 seconds',
      metric: webhookLambda.metricDuration({
        period: cdk.Duration.minutes(5),
        statistic: 'p95',
      }),
      threshold: 50000, // 50 seconds in ms
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // Lambda スロットリングアラーム
    const throttleAlarm = new cloudwatch.Alarm(this, 'LambdaThrottleAlarm', {
      alarmName: 'izakaya-agent-lambda-throttles',
      alarmDescription: 'Lambda function is being throttled',
      metric: webhookLambda.metricThrottles({
        period: cdk.Duration.minutes(5),
        statistic: 'Sum',
      }),
      threshold: 1,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // ========================================
    // CloudWatch Dashboard
    // ========================================

    const dashboard = new cloudwatch.Dashboard(this, 'IzakayaDashboard', {
      dashboardName: 'izakaya-agent-operations',
    });

    // Row 1: Lambda 概要
    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'Lambda Invocations & Errors',
        width: 12,
        left: [
          webhookLambda.metricInvocations({ period: cdk.Duration.minutes(5) }),
        ],
        right: [
          webhookLambda.metricErrors({ period: cdk.Duration.minutes(5), color: '#d62728' }),
        ],
      }),
      new cloudwatch.GraphWidget({
        title: 'Lambda Duration (ms)',
        width: 12,
        left: [
          webhookLambda.metricDuration({ period: cdk.Duration.minutes(5), statistic: 'Average' }),
          webhookLambda.metricDuration({ period: cdk.Duration.minutes(5), statistic: 'p95', color: '#ff7f0e' }),
          webhookLambda.metricDuration({ period: cdk.Duration.minutes(5), statistic: 'Maximum', color: '#d62728' }),
        ],
      }),
    );

    // Row 2: スロットリング & コンカレンシー
    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'Throttles & Concurrent Executions',
        width: 12,
        left: [
          webhookLambda.metricThrottles({ period: cdk.Duration.minutes(5) }),
        ],
        right: [
          webhookLambda.metric('ConcurrentExecutions', {
            period: cdk.Duration.minutes(5),
            statistic: 'Maximum',
          }),
        ],
      }),
      new cloudwatch.AlarmStatusWidget({
        title: 'Alarm Status',
        width: 12,
        alarms: [errorAlarm, latencyAlarm, throttleAlarm],
      }),
    );

    // Row 3: API Gateway メトリクス
    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'API Gateway Requests',
        width: 12,
        left: [
          new cloudwatch.Metric({
            namespace: 'AWS/ApiGateway',
            metricName: 'Count',
            dimensionsMap: { ApiName: 'Izakaya Agent API' },
            period: cdk.Duration.minutes(5),
            statistic: 'Sum',
          }),
        ],
        right: [
          new cloudwatch.Metric({
            namespace: 'AWS/ApiGateway',
            metricName: '4XXError',
            dimensionsMap: { ApiName: 'Izakaya Agent API' },
            period: cdk.Duration.minutes(5),
            statistic: 'Sum',
            color: '#ff7f0e',
          }),
          new cloudwatch.Metric({
            namespace: 'AWS/ApiGateway',
            metricName: '5XXError',
            dimensionsMap: { ApiName: 'Izakaya Agent API' },
            period: cdk.Duration.minutes(5),
            statistic: 'Sum',
            color: '#d62728',
          }),
        ],
      }),
      new cloudwatch.GraphWidget({
        title: 'API Gateway Latency (ms)',
        width: 12,
        left: [
          new cloudwatch.Metric({
            namespace: 'AWS/ApiGateway',
            metricName: 'Latency',
            dimensionsMap: { ApiName: 'Izakaya Agent API' },
            period: cdk.Duration.minutes(5),
            statistic: 'Average',
          }),
          new cloudwatch.Metric({
            namespace: 'AWS/ApiGateway',
            metricName: 'Latency',
            dimensionsMap: { ApiName: 'Izakaya Agent API' },
            period: cdk.Duration.minutes(5),
            statistic: 'p95',
            color: '#ff7f0e',
          }),
        ],
      }),
    );

    // Row 4: CloudWatch Logs Insights クエリリンク
    dashboard.addWidgets(
      new cloudwatch.LogQueryWidget({
        title: 'Recent Errors (Lambda)',
        width: 12,
        logGroupNames: [lambdaLogGroup.logGroupName],
        queryLines: [
          'fields @timestamp, @message',
          'filter @message like /error/',
          'sort @timestamp desc',
          'limit 20',
        ],
        view: cloudwatch.LogQueryVisualizationType.TABLE,
      }),
      new cloudwatch.LogQueryWidget({
        title: 'Request Latency (Lambda structured logs)',
        width: 12,
        logGroupNames: [lambdaLogGroup.logGroupName],
        queryLines: [
          'fields @timestamp',
          'parse @message /"event":\\s*"request_complete"/ as is_complete',
          'parse @message /"total_ms":\\s*(\\d+)/ as total_ms',
          'parse @message /"source":\\s*"(\\w+)"/ as source',
          'filter is_complete',
          'stats avg(total_ms) as avg_ms, max(total_ms) as max_ms, count(*) as requests by bin(5m)',
        ],
        view: cloudwatch.LogQueryVisualizationType.LINE,
      }),
    );

    // ========================================
    // Cognito User Pool (from Amplify Gen 2)
    // ========================================

    const userPool = cognito.UserPool.fromUserPoolId(
      this,
      'AmplifyUserPool',
      'ap-northeast-1_VwL7teKWl'
    );

    // ========================================
    // API Gateway REST API
    // ========================================

    const api = new apigateway.RestApi(this, 'IzakayaApi', {
      restApiName: 'Izakaya Agent API',
      description: 'REST API for Izakaya Agent (Web frontend)',
      deployOptions: {
        stageName: 'prod',
      },
    });

    // Cognito Authorizer
    const authorizer = new apigateway.CognitoUserPoolsAuthorizer(this, 'CognitoAuthorizer', {
      cognitoUserPools: [userPool],
      authorizerName: 'IzakayaCognitoAuthorizer',
    });

    // Lambda Integration
    const lambdaIntegration = new apigateway.LambdaIntegration(webhookLambda, {
      proxy: true,
    });

    // /chat endpoint (POST requires auth, OPTIONS handled by Lambda for dynamic CORS)
    const chatResource = api.root.addResource('chat');
    chatResource.addMethod('POST', lambdaIntegration, {
      authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });
    chatResource.addMethod('OPTIONS', lambdaIntegration, {
      authorizationType: apigateway.AuthorizationType.NONE,
    });

    // ========================================
    // Outputs
    // ========================================

    new cdk.CfnOutput(this, 'LineWebhookUrl', {
      value: functionUrl.url,
      description: 'LINE Webhook URL（LINE Developers Console に設定）',
      exportName: 'IzakayaAgentLineWebhookUrl',
    });

    new cdk.CfnOutput(this, 'ApiGatewayUrl', {
      value: api.url,
      description: 'API Gateway URL (Web frontend用)',
      exportName: 'IzakayaAgentApiGatewayUrl',
    });

    new cdk.CfnOutput(this, 'ChatEndpoint', {
      value: `${api.url}chat`,
      description: '/chat endpoint URL',
      exportName: 'IzakayaAgentChatEndpoint',
    });

    new cdk.CfnOutput(this, 'UserPoolId', {
      value: userPool.userPoolId,
      description: 'Cognito User Pool ID (Amplify Gen 2で管理)',
      exportName: 'IzakayaAgentUserPoolId',
    });

    new cdk.CfnOutput(this, 'LambdaFunctionName', {
      value: webhookLambda.functionName,
      description: 'Lambda関数名',
      exportName: 'IzakayaAgentLambdaFunctionName',
    });

    new cdk.CfnOutput(this, 'SecretsPrefix', {
      value: 'izakaya-agent/',
      description: 'Secrets Managerプレフィックス',
    });

    new cdk.CfnOutput(this, 'DashboardUrl', {
      value: `https://console.aws.amazon.com/cloudwatch/home?region=${this.region}#dashboards/dashboard/izakaya-agent-operations`,
      description: 'CloudWatch Operations Dashboard',
    });

    // ========================================
    // Streaming Lambda (Lambda Web Adapter + Function URL)
    // ========================================

    const streamingLambda = new lambda.DockerImageFunction(this, 'StreamingLambda', {
      code: lambda.DockerImageCode.fromImageAsset(
        path.join(__dirname, '../../lambda-streaming')
      ),
      functionName: 'izakaya-agent-streaming',
      description: 'Streaming response Lambda (SSE via Lambda Web Adapter)',
      role: lambdaRole,  // 既存ロールを再利用
      environment: {
        RUNTIME_ARN: 'arn:aws:bedrock-agentcore:ap-northeast-1:921563379197:runtime/izakaya_agent-9JGtN3Enat',
        MEMORY_ID: process.env.MEMORY_ID || 'izakaya_agent_mem-ZOMh0R8tfz',
        CORS_ALLOWED_ORIGINS: 'http://localhost:3000,http://localhost:3001,http://localhost:3002,https://main.d2mtz6tk9wfbf0.amplifyapp.com',
        COGNITO_USER_POOL_ID: 'ap-northeast-1_VwL7teKWl',
        COGNITO_REGION: 'ap-northeast-1',
        AWS_LWA_INVOKE_MODE: 'response_stream',
        // v2 A2A対応: Perspective Worker Runtime ARN
        WORKER_RUNTIME_ARN: process.env.WORKER_RUNTIME_ARN || '',
      },
      timeout: cdk.Duration.seconds(120),
      memorySize: 512,
    });

    const streamingUrl = streamingLambda.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
      invokeMode: lambda.InvokeMode.RESPONSE_STREAM,
      cors: {
        allowedOrigins: ['http://localhost:3000', 'http://localhost:3001',
                         'http://localhost:3002', 'https://main.d2mtz6tk9wfbf0.amplifyapp.com'],
        allowedHeaders: ['Content-Type', 'Authorization'],
        allowedMethods: [lambda.HttpMethod.POST],
        allowCredentials: true,
      },
    });

    // Streaming Lambda CloudWatch Logs
    const streamingLogGroup = new logs.LogGroup(this, 'StreamingLambdaLogGroup', {
      logGroupName: `/aws/lambda/${streamingLambda.functionName}`,
      retention: logs.RetentionDays.TWO_WEEKS,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    new cdk.CfnOutput(this, 'StreamingEndpoint', {
      value: streamingUrl.url,
      description: 'Streaming Lambda Function URL',
    });
  }
}
