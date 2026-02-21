import * as cdk from 'aws-cdk-lib';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';
import * as path from 'path';
import { config } from './config';

export class SreAgentStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const removalPolicy = config.isProduction
      ? cdk.RemovalPolicy.RETAIN
      : cdk.RemovalPolicy.DESTROY;

    // --- VPC (Phase 3: enableVpc = true で有効化) ---
    let vpc: ec2.IVpc | undefined;
    let vpcSubnets: ec2.SubnetSelection | undefined;
    let securityGroups: ec2.ISecurityGroup[] | undefined;

    if (config.enableVpc) {
      vpc = ec2.Vpc.fromLookup(this, 'Vpc', { vpcId: config.vpcConfig.vpcId });
      vpcSubnets = {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      };
      securityGroups = config.vpcConfig.securityGroupIds.map((sgId, i) =>
        ec2.SecurityGroup.fromSecurityGroupId(this, `SG${i}`, sgId)
      );
    }

    // --- ECR Repositories ---
    const agents = ['orchestrator', 'diagnostic', 'knowledge'] as const;
    const ecrRepos: Record<string, ecr.Repository> = {};

    for (const agent of agents) {
      ecrRepos[agent] = new ecr.Repository(this, `${agent}Repo`, {
        repositoryName: `sre-agent/${agent}`,
        removalPolicy,
        lifecycleRules: [
          {
            maxImageCount: 5,
            description: 'Keep only 5 images',
          },
        ],
      });
    }

    // --- IAM: AgentCore Runtime Role ---
    const agentRuntimeRole = new iam.Role(this, 'AgentRuntimeRole', {
      roleName: 'sre-agent-runtime-role',
      assumedBy: new iam.CompositePrincipal(
        new iam.ServicePrincipal('bedrock.amazonaws.com'),
        new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
      ),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Bedrock model invocation
    agentRuntimeRole.addToPolicy(new iam.PolicyStatement({
      sid: 'BedrockModelInvocation',
      actions: [
        'bedrock:InvokeModel',
        'bedrock:InvokeModelWithResponseStream',
      ],
      resources: [`arn:aws:bedrock:${this.region}::foundation-model/*`],
    }));

    // AgentCore Runtime - 最小権限
    agentRuntimeRole.addToPolicy(new iam.PolicyStatement({
      sid: 'AgentCoreRuntime',
      actions: [
        'bedrock-agentcore:InvokeAgent',
        'bedrock-agentcore:InvokeAgentRuntime',
      ],
      resources: [`arn:aws:bedrock-agentcore:${this.region}:${this.account}:agent/*`],
    }));

    // AgentCore Memory API
    agentRuntimeRole.addToPolicy(new iam.PolicyStatement({
      sid: 'AgentCoreMemory',
      actions: [
        'bedrock-agentcore:Retrieve',
        'bedrock-agentcore:CreateMemory',
        'bedrock-agentcore:UpdateMemory',
      ],
      resources: [`arn:aws:bedrock-agentcore:${this.region}:${this.account}:memory/*`],
    }));

    // --- IAM: Gateway Interceptor Lambda Role ---
    const interceptorRole = new iam.Role(this, 'InterceptorRole', {
      roleName: 'sre-agent-interceptor-role',
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // --- Secrets Manager: Langfuse Keys ---
    const langfuseSecret = new secretsmanager.Secret(this, 'LangfuseKeys', {
      secretName: config.langfuse.secretName,
      description: 'Langfuse API keys for SRE Agent observability',
      generateSecretString: {
        secretStringTemplate: JSON.stringify({
          LANGFUSE_PUBLIC_KEY: 'pk-lf-xxx',
          LANGFUSE_SECRET_KEY: 'sk-lf-xxx',
        }),
        generateStringKey: 'placeholder',
      },
    });

    // Agent に Langfuse シークレット読み取り権限
    langfuseSecret.grantRead(agentRuntimeRole);

    // --- Gateway Interceptor Lambda ---
    const interceptorLambda = new lambda.Function(this, 'InterceptorLambda', {
      functionName: 'sre-agent-interceptor',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../gateway/interceptor')),
      role: interceptorRole,
      timeout: cdk.Duration.seconds(10),
      memorySize: 128,
      environment: {
        LOG_LEVEL: 'INFO',
        MEMORY_ID: config.memoryId,
      },
      ...(vpc && {
        vpc,
        vpcSubnets,
        securityGroups,
      }),
    });

    // --- CloudWatch Log Groups ---
    for (const agent of agents) {
      new logs.LogGroup(this, `${agent}LogGroup`, {
        logGroupName: `/sre-agent/${agent}`,
        retention: logs.RetentionDays.TWO_WEEKS,
        removalPolicy,
      });
    }

    // --- CloudWatch Dashboard ---
    const dashboard = new cloudwatch.Dashboard(this, 'SreAgentDashboard', {
      dashboardName: 'sre-agent-operations',
    });

    // Interceptor Lambda metrics
    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'Interceptor Lambda - Invocations & Errors',
        left: [interceptorLambda.metricInvocations()],
        right: [interceptorLambda.metricErrors()],
        width: 12,
      }),
      new cloudwatch.GraphWidget({
        title: 'Interceptor Lambda - Duration',
        left: [interceptorLambda.metricDuration({ statistic: 'p95' })],
        width: 12,
      }),
    );

    // --- CloudWatch Alarms ---
    new cloudwatch.Alarm(this, 'InterceptorErrorAlarm', {
      alarmName: 'sre-agent-interceptor-errors',
      metric: interceptorLambda.metricErrors({ period: cdk.Duration.minutes(5) }),
      threshold: 3,
      evaluationPeriods: 1,
      alarmDescription: 'Gateway Interceptor Lambda error rate high',
    });

    // --- Outputs ---
    for (const [name, repo] of Object.entries(ecrRepos)) {
      new cdk.CfnOutput(this, `${name}EcrUri`, {
        value: repo.repositoryUri,
        description: `ECR URI for ${name} agent`,
      });
    }

    // Agent config outputs (config.ts の agents/memoryId を実際にスタックで使用)
    new cdk.CfnOutput(this, 'OrchestratorModelId', {
      value: config.agents.orchestrator.modelId,
      description: 'Orchestrator agent model ID',
    });

    new cdk.CfnOutput(this, 'DiagnosticModelId', {
      value: config.agents.diagnostic.modelId,
      description: 'Diagnostic agent model ID',
    });

    new cdk.CfnOutput(this, 'KnowledgeModelId', {
      value: config.agents.knowledge.modelId,
      description: 'Knowledge agent model ID',
    });

    new cdk.CfnOutput(this, 'MemoryId', {
      value: config.memoryId || 'NOT_SET',
      description: 'AgentCore Memory ID',
    });

    new cdk.CfnOutput(this, 'InterceptorLambdaArn', {
      value: interceptorLambda.functionArn,
      description: 'Gateway Interceptor Lambda ARN',
    });

    new cdk.CfnOutput(this, 'AgentRuntimeRoleArn', {
      value: agentRuntimeRole.roleArn,
      description: 'Agent Runtime IAM Role ARN',
    });
  }
}
