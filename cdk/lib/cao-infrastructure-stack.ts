import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as elasticache from 'aws-cdk-lib/aws-elasticache';
import { Construct } from 'constructs';

export interface CAOInfrastructureStackProps extends cdk.StackProps {
  vpc: ec2.Vpc;
  userPool: cognito.UserPool;
}

export class CAOInfrastructureStack extends cdk.Stack {
  public readonly cluster: ecs.Cluster;
  public readonly service: ecs.FargateService;
  public readonly loadBalancer: elbv2.ApplicationLoadBalancer;

  constructor(scope: Construct, id: string, props: CAOInfrastructureStackProps) {
    super(scope, id, props);

    const { vpc, userPool } = props;

    // Create ECR repository for CAO server image
    const repository = new ecr.Repository(this, 'CAORepository', {
      repositoryName: 'cli-agent-orchestrator',
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      imageScanOnPush: true,
      lifecycleRules: [
        {
          maxImageCount: 10,
          description: 'Keep last 10 images',
        },
      ],
    });

    // Create ECS Cluster
    this.cluster = new ecs.Cluster(this, 'CAOCluster', {
      vpc,
      clusterName: 'cao-cluster',
      containerInsights: true,
    });

    // Create DynamoDB table for session management
    const sessionTable = new dynamodb.Table(this, 'CAOSessionTable', {
      tableName: 'cao-sessions',
      partitionKey: {
        name: 'session_id',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecovery: true,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
    });

    // Add TTL attribute for automatic cleanup
    sessionTable.addGlobalSecondaryIndex({
      indexName: 'user-index',
      partitionKey: {
        name: 'user_id',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Create ElastiCache Redis for session storage
    const subnetGroup = new elasticache.CfnSubnetGroup(this, 'CAOCacheSubnetGroup', {
      description: 'Subnet group for CAO Redis cache',
      subnetIds: vpc.privateSubnets.map(subnet => subnet.subnetId),
      cacheSubnetGroupName: 'cao-cache-subnet-group',
    });

    const cacheSecurityGroup = new ec2.SecurityGroup(this, 'CacheSecurityGroup', {
      vpc,
      description: 'Security group for Redis cache',
      allowAllOutbound: true,
    });

    const redisCluster = new elasticache.CfnCacheCluster(this, 'CAORedisCluster', {
      cacheNodeType: 'cache.t3.micro',
      engine: 'redis',
      numCacheNodes: 1,
      vpcSecurityGroupIds: [cacheSecurityGroup.securityGroupId],
      cacheSubnetGroupName: subnetGroup.cacheSubnetGroupName,
      clusterName: 'cao-session-cache',
    });

    redisCluster.addDependency(subnetGroup);

    // Task execution role
    const executionRole = new iam.Role(this, 'CAOExecutionRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          'service-role/AmazonECSTaskExecutionRolePolicy'
        ),
      ],
    });

    // Task role with permissions for CAO operations
    const taskRole = new iam.Role(this, 'CAOTaskRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
    });

    sessionTable.grantReadWriteData(taskRole);

    // Create Task Definition
    const taskDefinition = new ecs.FargateTaskDefinition(this, 'CAOTaskDef', {
      memoryLimitMiB: 2048,
      cpu: 1024,
      executionRole,
      taskRole,
    });

    // Create CloudWatch Logs group
    const logGroup = new logs.LogGroup(this, 'CAOLogGroup', {
      logGroupName: '/ecs/cao-server',
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // Add container to task definition
    const container = taskDefinition.addContainer('CAOContainer', {
      image: ecs.ContainerImage.fromEcrRepository(repository),
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'cao',
        logGroup,
      }),
      environment: {
        PORT: '9889',
        USER_POOL_ID: userPool.userPoolId,
        DYNAMODB_TABLE: sessionTable.tableName,
        REDIS_HOST: redisCluster.attrRedisEndpointAddress,
        REDIS_PORT: redisCluster.attrRedisEndpointPort,
      },
      healthCheck: {
        command: ['CMD-SHELL', 'curl -f http://localhost:9889/health || exit 1'],
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(5),
        retries: 3,
        startPeriod: cdk.Duration.seconds(60),
      },
    });

    container.addPortMappings({
      containerPort: 9889,
      protocol: ecs.Protocol.TCP,
    });

    // Create Application Load Balancer
    this.loadBalancer = new elbv2.ApplicationLoadBalancer(this, 'CAOALB', {
      vpc,
      internetFacing: true,
      loadBalancerName: 'cao-alb',
    });

    // Create target group
    const targetGroup = new elbv2.ApplicationTargetGroup(this, 'CAOTargetGroup', {
      vpc,
      port: 9889,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targetType: elbv2.TargetType.IP,
      healthCheck: {
        path: '/health',
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(5),
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 3,
      },
      deregistrationDelay: cdk.Duration.seconds(30),
      stickinessCookieDuration: cdk.Duration.hours(1),
      stickinessCookieName: 'cao-session',
    });

    // Enable sticky sessions
    targetGroup.setAttribute('stickiness.enabled', 'true');
    targetGroup.setAttribute('stickiness.type', 'lb_cookie');
    targetGroup.setAttribute('stickiness.lb_cookie.duration_seconds', '3600');

    // Add listener
    const listener = this.loadBalancer.addListener('CAOListener', {
      port: 80,
      protocol: elbv2.ApplicationProtocol.HTTP,
      defaultAction: elbv2.ListenerAction.forward([targetGroup]),
    });

    // Create Fargate Service
    this.service = new ecs.FargateService(this, 'CAOService', {
      cluster: this.cluster,
      taskDefinition,
      desiredCount: 2,
      serviceName: 'cao-service',
      assignPublicIp: false,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
      healthCheckGracePeriod: cdk.Duration.seconds(60),
      minHealthyPercent: 50,
      maxHealthyPercent: 200,
    });

    // Attach service to target group
    this.service.attachToApplicationTargetGroup(targetGroup);

    // Configure Auto Scaling
    const scaling = this.service.autoScaleTaskCount({
      minCapacity: 2,
      maxCapacity: 10,
    });

    // Scale based on CPU utilization
    scaling.scaleOnCpuUtilization('CAOCpuScaling', {
      targetUtilizationPercent: 70,
      scaleInCooldown: cdk.Duration.seconds(60),
      scaleOutCooldown: cdk.Duration.seconds(60),
    });

    // Scale based on request count
    scaling.scaleOnRequestCount('CAORequestScaling', {
      requestsPerTarget: 1000,
      targetGroup,
      scaleInCooldown: cdk.Duration.seconds(60),
      scaleOutCooldown: cdk.Duration.seconds(60),
    });

    // Allow cache access from ECS tasks
    cacheSecurityGroup.addIngressRule(
      ec2.Peer.securityGroupId(this.service.connections.securityGroups[0].securityGroupId),
      ec2.Port.tcp(6379),
      'Allow Redis access from ECS tasks'
    );

    // Outputs
    new cdk.CfnOutput(this, 'LoadBalancerDNS', {
      value: this.loadBalancer.loadBalancerDnsName,
      description: 'DNS name of the load balancer',
      exportName: 'CAOLoadBalancerDNS',
    });

    new cdk.CfnOutput(this, 'RepositoryUri', {
      value: repository.repositoryUri,
      description: 'ECR Repository URI',
      exportName: 'CAORepositoryUri',
    });

    new cdk.CfnOutput(this, 'SessionTableName', {
      value: sessionTable.tableName,
      description: 'DynamoDB Session Table Name',
      exportName: 'CAOSessionTableName',
    });

    new cdk.CfnOutput(this, 'RedisEndpoint', {
      value: `${redisCluster.attrRedisEndpointAddress}:${redisCluster.attrRedisEndpointPort}`,
      description: 'Redis Cluster Endpoint',
      exportName: 'CAORedisEndpoint',
    });
  }
}
