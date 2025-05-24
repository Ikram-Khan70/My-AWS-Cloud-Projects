import boto3
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    ec2 = boto3.client('ec2')
    
    try:
        logger.info("Attempting to describe running instances")
        response = ec2.describe_instances(
            Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
        )
        logger.info("Successfully retrieved instance information")
        
        instances_to_stop = []
        
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                if not instance.get('Tags'):
                    logger.info(f"Found untagged instance: {instance_id}")
                    instances_to_stop.append(instance_id)
                else:
                    logger.debug(f"Instance {instance_id} has tags, skipping")
        
        if instances_to_stop:
            logger.info(f"Attempting to stop instances: {instances_to_stop}")
            stop_response = ec2.stop_instances(InstanceIds=instances_to_stop)
            logger.info(f"Stop instances response: {stop_response}")
            return {
                'statusCode': 200,
                'body': f"Successfully stopped {len(instances_to_stop)} untagged instances"
            }
        else:
            logger.info("No untagged running instances found")
            return {
                'statusCode': 200,
                'body': "No untagged running instances found"
            }
            
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        return {
            'statusCode': 500,
            'body': f"Error processing request: {str(e)}"
        }
