export interface SreAgentConfig {
  /** AWS リージョン (VPC 対応リージョン) */
  region: string;

  /** 本番環境かどうか (RemovalPolicy 等に影響) */
  isProduction: boolean;

  /** VPC を有効にするか (Phase 3 で true に変更) */
  enableVpc: boolean;

  /** VPC 設定 (enableVpc: true の場合に使用) */
  vpcConfig: {
    vpcId: string;
    subnetIds: string[];
    securityGroupIds: string[];
  };

  /** AgentCore Memory ID */
  memoryId: string;

  /** エージェント設定 */
  agents: {
    orchestrator: { modelId: string };
    diagnostic: { modelId: string };
    knowledge: { modelId: string };
  };

  /** Langfuse 設定 (Phase 1) */
  langfuse: {
    host: string;
    secretName: string;  // Secrets Manager のシークレット名
  };
}

export const config: SreAgentConfig = {
  region: 'us-west-2',

  isProduction: process.env.ENVIRONMENT === 'production',

  enableVpc: false,  // Phase 3 で true に変更するだけ
  vpcConfig: {
    vpcId: '',          // Phase 3 で設定
    subnetIds: [],      // Phase 3 で設定
    securityGroupIds: [], // Phase 3 で設定
  },

  memoryId: process.env.MEMORY_ID || '',

  agents: {
    orchestrator: { modelId: 'anthropic.claude-sonnet-4-5-20250929-v1:0' },
    diagnostic: { modelId: 'anthropic.claude-sonnet-4-5-20250929-v1:0' },
    knowledge: { modelId: 'anthropic.claude-haiku-4-5-20251001-v1:0' },
  },

  langfuse: {
    host: 'https://cloud.langfuse.com',
    secretName: 'sre-agent/langfuse-keys',
  },
};
