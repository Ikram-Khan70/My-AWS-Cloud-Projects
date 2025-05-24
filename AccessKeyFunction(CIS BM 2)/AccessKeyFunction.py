import boto3
import logging
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
import os

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
iam_client = boto3.client('iam')
sns_client = boto3.client('sns')

def lambda_handler(event, context):
    """
    Simple Lambda function to delete IAM access keys older than 90 days
    """
    try:
        # Configuration
        DRY_RUN = os.environ.get('DRY_RUN', 'true').lower() == 'true'
        DAYS_THRESHOLD = int(os.environ.get('DAYS_THRESHOLD', '90'))
        EXCLUDED_USERS = os.environ.get('EXCLUDED_USERS', '').split(',')
        SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')
        
        # Clean excluded users list
        excluded_users = [user.strip() for user in EXCLUDED_USERS if user.strip()]
        
        logger.info(f"Starting key deletion process - Dry Run: {DRY_RUN}, Threshold: {DAYS_THRESHOLD} days")
        
        # Track results
        total_users = 0
        total_keys_checked = 0
        old_keys_found = 0
        keys_deleted = 0
        errors = []
        
        # Get all IAM users
        paginator = iam_client.get_paginator('list_users')
        
        for page in paginator.paginate():
            for user in page['Users']:
                username = user['UserName']
                total_users += 1
                
                # Skip excluded users
                if username in excluded_users:
                    logger.info(f"Skipping excluded user: {username}")
                    continue
                
                try:
                    # Get access keys for this user
                    keys_response = iam_client.list_access_keys(UserName=username)
                    access_keys = keys_response['AccessKeyMetadata']
                    total_keys_checked += len(access_keys)
                    
                    for key in access_keys:
                        access_key_id = key['AccessKeyId']
                        created_date = key['CreateDate'].replace(tzinfo=None)
                        days_old = (datetime.utcnow() - created_date).days
                        
                        # Check if key is older than threshold
                        if days_old >= DAYS_THRESHOLD:
                            old_keys_found += 1
                            logger.info(f"Found old key: {access_key_id} for user {username} - {days_old} days old")
                            
                            if DRY_RUN:
                                logger.info(f"DRY RUN: Would delete key {access_key_id} for user {username}")
                            else:
                                # Delete the access key
                                try:
                                    iam_client.delete_access_key(
                                        UserName=username,
                                        AccessKeyId=access_key_id
                                    )
                                    keys_deleted += 1
                                    logger.info(f"DELETED: Access key {access_key_id} for user {username}")
                                    
                                except ClientError as e:
                                    error_msg = f"Failed to delete key {access_key_id} for user {username}: {str(e)}"
                                    logger.error(error_msg)
                                    errors.append(error_msg)
                        else:
                            logger.debug(f"Key {access_key_id} for user {username} is {days_old} days old - keeping")
                
                except ClientError as e:
                    error_msg = f"Error processing user {username}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
        
        # Prepare summary
        summary = {
            'dry_run': DRY_RUN,
            'threshold_days': DAYS_THRESHOLD,
            'total_users_scanned': total_users,
            'total_keys_checked': total_keys_checked,
            'old_keys_found': old_keys_found,
            'keys_deleted': keys_deleted,
            'errors_count': len(errors),
            'excluded_users': excluded_users
        }
        
        # Log summary
        logger.info(f"Process completed: {summary}")
        
        # Send notification if SNS topic is configured
        if SNS_TOPIC_ARN:
            send_notification(summary, errors, SNS_TOPIC_ARN)
        
        # Return response
        return {
            'statusCode': 200,
            'body': {
                'message': 'Access key deletion process completed successfully',
                'summary': summary,
                'errors': errors[:10]  # Return only first 10 errors to avoid large response
            }
        }
        
    except Exception as e:
        error_message = f"Fatal error in lambda execution: {str(e)}"
        logger.error(error_message)
        
        return {
            'statusCode': 500,
            'body': {
                'message': 'Access key deletion process failed',
                'error': error_message
            }
        }

def send_notification(summary, errors, sns_topic_arn):
    """
    Send notification via SNS
    """
    try:
        subject = f"IAM Access Key Deletion Report - {datetime.utcnow().strftime('%Y-%m-%d')}"
        
        message = f"""
IAM Access Key Deletion Report

Execution Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
Mode: {'DRY RUN' if summary['dry_run'] else 'LIVE DELETION'}
Age Threshold: {summary['threshold_days']} days

Results:
- Users Scanned: {summary['total_users_scanned']}
- Total Keys Checked: {summary['total_keys_checked']}
- Old Keys Found: {summary['old_keys_found']}
- Keys Deleted: {summary['keys_deleted']}
- Errors: {summary['errors_count']}

Excluded Users: {', '.join(summary['excluded_users']) if summary['excluded_users'] else 'None'}
"""
        
        if errors:
            message += f"\nFirst 5 Errors:\n"
            for i, error in enumerate(errors[:5]):
                message += f"{i+1}. {error}\n"
        
        if summary['dry_run']:
            message += f"\n⚠️  This was a DRY RUN - no keys were actually deleted."
        
        sns_client.publish(
            TopicArn=sns_topic_arn,
            Subject=subject,
            Message=message
        )
        
        logger.info("Notification sent successfully")
        
    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")

# Optional: Function to list old keys without deleting (for reporting)
def list_old_keys_only(event, context):
    """
    Alternative function to just list old keys without deletion
    """
    try:
        DAYS_THRESHOLD = int(os.environ.get('DAYS_THRESHOLD', '90'))
        EXCLUDED_USERS = os.environ.get('EXCLUDED_USERS', '').split(',')
        excluded_users = [user.strip() for user in EXCLUDED_USERS if user.strip()]
        
        old_keys_report = []
        
        paginator = iam_client.get_paginator('list_users')
        
        for page in paginator.paginate():
            for user in page['Users']:
                username = user['UserName']
                
                if username in excluded_users:
                    continue
                
                try:
                    keys_response = iam_client.list_access_keys(UserName=username)
                    
                    for key in keys_response['AccessKeyMetadata']:
                        created_date = key['CreateDate'].replace(tzinfo=None)
                        days_old = (datetime.utcnow() - created_date).days
                        
                        if days_old >= DAYS_THRESHOLD:
                            old_keys_report.append({
                                'username': username,
                                'access_key_id': key['AccessKeyId'],
                                'created_date': created_date.strftime('%Y-%m-%d'),
                                'days_old': days_old,
                                'status': key['Status']
                            })
                
                except ClientError as e:
                    logger.error(f"Error checking user {username}: {str(e)}")
        
        logger.info(f"Found {len(old_keys_report)} old access keys")
        
        return {
            'statusCode': 200,
            'body': {
                'message': f'Found {len(old_keys_report)} access keys older than {DAYS_THRESHOLD} days',
                'old_keys': old_keys_report
            }
        }
        
    except Exception as e:
        logger.error(f"Error in list_old_keys_only: {str(e)}")
        return {
            'statusCode': 500,
            'body': {
                'message': 'Failed to list old keys',
                'error': str(e)
            }
        }
