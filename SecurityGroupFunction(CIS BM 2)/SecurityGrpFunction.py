import boto3
import logging
from botocore.exceptions import ClientError

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def has_insecure_ingress(sg):
    """Check if security group has overly permissive rules"""
    for permission in sg['IpPermissions']:
        # Check IPv4 rules
        for ip_range in permission.get('IpRanges', []):
            if ip_range['CidrIp'] == '0.0.0.0/0':
                return True
        
        # Check IPv6 rules
        for ipv6_range in permission.get('Ipv6Ranges', []):
            if ipv6_range['CidrIpv6'] == '::/0':
                return True
    return False

def lambda_handler(event, context):
    ec2 = boto3.client('ec2')
    tag_key = "InsecureSecurityGroup"
    tag_value = "NeedsReview"
    
    try:
        # Get all running instances
        instances = ec2.describe_instances(
            Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
        )['Reservations']
        
        tagged_instances = []
        
        for reservation in instances:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                instance_tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                
                # Skip if already tagged
                if tag_key in instance_tags:
                    logger.info(f"Instance {instance_id} already tagged, skipping")
                    continue
                
                # Check security groups
                for sg in instance['SecurityGroups']:
                    sg_details = ec2.describe_security_groups(
                        GroupIds=[sg['GroupId']]
                    )['SecurityGroups'][0]
                    
                    if has_insecure_ingress(sg_details):
                        # Tag the instance
                        try:
                            ec2.create_tags(
                                Resources=[instance_id],
                                Tags=[{'Key': tag_key, 'Value': tag_value}]
                            )
                            tagged_instances.append(instance_id)
                            logger.info(f"Tagged instance {instance_id} for insecure security group")
                            break  # No need to check other SGs for this instance
                        except ClientError as e:
                            logger.error(f"Failed to tag instance {instance_id}: {str(e)}")
        
        return {
            'statusCode': 200,
            'body': f"Tagged {len(tagged_instances)} instances with insecure security groups",
            'tagged_instances': tagged_instances
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': f"Error processing request: {str(e)}"
        }
