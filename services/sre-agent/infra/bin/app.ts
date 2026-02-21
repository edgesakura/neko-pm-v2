#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { SreAgentStack } from '../lib/sre-agent-stack';
import { config } from '../lib/config';

const app = new cdk.App();

new SreAgentStack(app, 'SreAgentStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: config.region,
  },
  description: 'SRE Agent on AgentCore + A2A - Multi-agent SRE system with context engineering',
});
