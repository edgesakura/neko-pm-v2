#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { IzakayaStack } from '../lib/izakaya-stack';

const app = new cdk.App();

new IzakayaStack(app, 'IzakayaAgentStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: 'ap-northeast-1', // 東京リージョン
  },
  description: '居酒屋検索AIエージェント「イザカヤくん」インフラスタック',
});

app.synth();
