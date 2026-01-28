import boto3
import botocore

# Replace with your S3 bucket name and object key (file path in S3)
BUCKET_NAME = 'neuro-san-factory-sense-medic'
KEY = 'SOP.txt'

# Replace with the desired local path and filename for the downloaded file
LOCAL_FILENAME = 'SOP.txt'

# Create an S3 client or resource object
# It's recommended to configure AWS credentials securely (e.g., environment variables, AWS config file)
# If not configured, boto3 will attempt to use default credentials (e.g., from ~/.aws/credentials)
s3 = boto3.client('s3') 

try:
    s3.download_file(BUCKET_NAME, KEY, LOCAL_FILENAME)
    print(f"File '{KEY}' successfully downloaded from S3 to '{LOCAL_FILENAME}'.")
except botocore.exceptions.ClientError as e:
    if e.response['Error']['Code'] == "404":
        print(f"The object '{KEY}' does not exist in bucket '{BUCKET_NAME}'.")
    else:
        print(f"An error occurred: {e}")