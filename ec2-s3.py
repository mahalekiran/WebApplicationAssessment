import boto3
import os

# Set AWS credentials
os.environ['AWS_ACCESS_KEY_ID'] = 'AKIAXP5HM3F5CHUIH3O6'
os.environ['AWS_SECRET_ACCESS_KEY'] = '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'

# Create an S3 client
s3 = boto3.client('s3')

# Create a new S3 bucket
bucket_name = 'kiranmahale-webapp-bucket'
s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={'LocationConstraint': 'us-east-2'})

# Upload a file to the S3 bucket
file_name = 'index.html'
s3.upload_file(file_name, bucket_name, file_name)

# Create an EC2 resource
ec2 = boto3.resource('ec2')

# Launch a new EC2 instance
instance = ec2.create_instances(
    ImageId='ami-0b8b44ec9a8f90422',
    MinCount=1,
    MaxCount=1,
    InstanceType='t2.micro',
    KeyName='KiranM_All',
)[0]

# Wait for the instance to enter the running state
instance.wait_until_running()

# Reload the instance attributes
instance.reload()

# Create an ELB client
elbv2 = boto3.client('elbv2')

# Create an Application Load Balancer
response = elbv2.create_load_balancer(
    Name='KiranM-webapp-load-balancer',
    Subnets=[
        'subnet-b00483fc',
        'subnet-6c683716'
    ],
    SecurityGroups=[
        'sg-02fca2879071bd73a',
    ],
    Scheme='internet-facing',
    Tags=[
        {
            'Key': 'Name',
            'Value': 'KiranM-webapp-load-balancer'
        },
    ],
    Type='application',
    IpAddressType='ipv4'
)

# Get the ARN of the newly created load balancer
load_balancer_arn = response['LoadBalancers'][0]['LoadBalancerArn']

# Create a target group
response = elbv2.create_target_group(
    Name='kiranm-target-group',
    Protocol='HTTP',
    Port=80,
    VpcId='vpc-7faf5614',
    HealthCheckProtocol='HTTP',
    HealthCheckPort='80',
    HealthCheckPath='/',
    HealthCheckIntervalSeconds=30,
    HealthCheckTimeoutSeconds=5,
    HealthyThresholdCount=5,
    UnhealthyThresholdCount=2,
    Matcher={
        'HttpCode': '200'
    },
    TargetType='instance'
)

# Get the ARN of the newly created target group
target_group_arn = response['TargetGroups'][0]['TargetGroupArn']

# Register the EC2 instance with the load balancer
elbv2.register_targets(
    TargetGroupArn=target_group_arn,
    Targets=[
        {
            'Id': instance.id,
            'Port': 80,
        },
    ]
)

autoscaling = boto3.client('autoscaling')
sns = boto3.client('sns')

# Create a Launch Configuration
autoscaling.create_launch_configuration(
    LaunchConfigurationName='kiranm-launch-configuration',
    ImageId='ami-0b8b44ec9a8f90422',
    InstanceType='t2.micro',
    SecurityGroups=['sg-02fca2879071bd73a'],
)

# Create an Auto Scaling Group
autoscaling.create_auto_scaling_group(
    AutoScalingGroupName='kiranm-auto-scaling-group',
    LaunchConfigurationName='kiranm-launch-configuration',
    MinSize=1,
    MaxSize=3,
    DesiredCapacity=2,
    VPCZoneIdentifier='subnet-b00483fc,subnet-6c683716',
)

# Create scaling policies
autoscaling.put_scaling_policy(
    AutoScalingGroupName='kiranm-auto-scaling-group',
    PolicyName='scaleout-policy',
    PolicyType='TargetTrackingScaling',
    TargetTrackingConfiguration={
        'PredefinedMetricSpecification': {
            'PredefinedMetricType': 'ASGAverageCPUUtilization',
        },
        'TargetValue': 50.0,
    },
)

# Create SNS topics
response = sns.create_topic(Name='health-issues')
health_issues_topic_arn = response['TopicArn']

response = sns.create_topic(Name='scaling-events')
scaling_events_topic_arn = response['TopicArn']

response = sns.create_topic(Name='high-traffic')
high_traffic_topic_arn = response['TopicArn']

# Subscribe administrators to the SNS topics
sns.subscribe(
    TopicArn=health_issues_topic_arn,
    Protocol='email',
    Endpoint='krn1988@gmail.com',
)

# Set up CloudWatch alarms to publish messages to the SNS topics
cloudwatch = boto3.client('cloudwatch')

cloudwatch.put_metric_alarm(
    AlarmName='high-cpu-utilization',
    ComparisonOperator='GreaterThanThreshold',
    EvaluationPeriods=1,
    MetricName='CPUUtilization',
    Namespace='AWS/EC2',
    Period=60,
    Statistic='Average',
    Threshold=70.0,
    ActionsEnabled=True,
    AlarmActions=[
        high_traffic_topic_arn,
    ],
    AlarmDescription='Alarm when server CPU utilization exceeds 70%',
    Dimensions=[
        {
          'Name': 'AutoScalingGroupName',
          'Value': 'my-auto-scaling-group'
        },
    ],
    Unit='Percent'
)

# Update the Auto Scaling Group
autoscaling.update_auto_scaling_group(
    AutoScalingGroupName='kiranm-auto-scaling-group',
    MinSize=1,
    MaxSize=5,  
    DesiredCapacity=3,
)

# Delete the Auto Scaling Group
autoscaling.delete_auto_scaling_group(
    AutoScalingGroupName='kiranm-auto-scaling-group',
    ForceDelete=True,
)

# Delete the Launch Configuration
autoscaling.delete_launch_configuration(
    LaunchConfigurationName='kiranm-launch-configuration',
)

