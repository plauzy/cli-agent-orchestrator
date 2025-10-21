export interface Config {
  environment: string;
  account: string;
  region: string;

  // Domain configuration
  domainName?: string;
  certificateArn?: string;
  hostedZoneId?: string;

  // Frontend configuration
  frontend: {
    buildCommand: string;
    buildOutputDir: string;
    cacheControl: {
      html: string;
      static: string;
    };
  };

  // Backend configuration
  backend: {
    runtime: string;
    memorySize: number;
    timeout: number;
    environment: {
      [key: string]: string;
    };
  };

  // Pipeline configuration
  pipeline?: {
    githubOwner: string;
    githubRepo: string;
    githubBranch: string;
    githubTokenSecretName: string;
  };
}

const devConfig: Config = {
  environment: 'dev',
  account: process.env.CDK_DEFAULT_ACCOUNT || '',
  region: process.env.CDK_DEFAULT_REGION || 'us-east-1',

  frontend: {
    buildCommand: 'npm run build',
    buildOutputDir: 'dist',
    cacheControl: {
      html: 'public, max-age=0, must-revalidate',
      static: 'public, max-age=31536000, immutable'
    }
  },

  backend: {
    runtime: 'python3.11',
    memorySize: 512,
    timeout: 30,
    environment: {
      ENVIRONMENT: 'dev',
      LOG_LEVEL: 'DEBUG'
    }
  }
};

const prodConfig: Config = {
  environment: 'prod',
  account: process.env.CDK_DEFAULT_ACCOUNT || '',
  region: process.env.CDK_DEFAULT_REGION || 'us-east-1',

  // Uncomment and configure for custom domain
  // domainName: 'cao.example.com',
  // certificateArn: 'arn:aws:acm:us-east-1:ACCOUNT:certificate/CERT_ID',
  // hostedZoneId: 'HOSTED_ZONE_ID',

  frontend: {
    buildCommand: 'npm run build',
    buildOutputDir: 'dist',
    cacheControl: {
      html: 'public, max-age=0, must-revalidate',
      static: 'public, max-age=31536000, immutable'
    }
  },

  backend: {
    runtime: 'python3.11',
    memorySize: 1024,
    timeout: 60,
    environment: {
      ENVIRONMENT: 'prod',
      LOG_LEVEL: 'INFO'
    }
  },

  pipeline: {
    githubOwner: 'awslabs',
    githubRepo: 'cli-agent-orchestrator',
    githubBranch: 'main',
    githubTokenSecretName: 'github-token'
  }
};

export function getConfig(environment: string): Config {
  switch (environment) {
    case 'dev':
      return devConfig;
    case 'prod':
      return prodConfig;
    default:
      throw new Error(`Unknown environment: ${environment}`);
  }
}
