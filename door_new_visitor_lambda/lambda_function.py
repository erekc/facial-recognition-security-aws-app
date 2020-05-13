"""
door_new_visitor
"""

import json
import string
import random
import boto3
import time

def lambda_handler(event, context):
    
    """
    Use the faceId to attempt to extract pending visitor.
    """
    face_id = event["face_id"]
    dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
    pending_table = dynamodb.Table("pending")
    pending_response = pending_table.get_item(Key={"faceId": face_id})
    
    """
    If visitor does not exist in pending table return nonexistent confirmation
    """
    if len(pending_response) < 2:
        return {
            "body": {
                "exists": "False",
                "face_id": face_id
            }
        }
    
    if event["approved"] == "True":
        
        """
        1) Take in faceId object from Gateway.
        """
        visitor_name = event["name"]
        visitor_phone_number = event["phone_number"]
        
        """
        2) Get pending visitor object.
        """
        pending_visitor = pending_response["Item"]
        
        """
        3) Delete object from pending table.
        """
        pending_table.delete_item(Key={"faceId": face_id})
        
        """
        4) Put visitor into visitors table.
        """
        visitor = {
            "faceId": face_id,
            "name": visitor_name,
            "phoneNumber": visitor_phone_number,
            "photos": pending_visitor["photos"]
        }
        visitors_table = dynamodb.Table("visitors")
        visitors_table.put_item(Item=visitor)
        
        """
        5) Create OTP and record it in passcodes table.
        """
        passcodes_table = dynamodb.Table("passcodes")
        otp = ''.join([random.choice(string.ascii_lowercase+string.ascii_uppercase+string.digits)\
            for n in range(10)])
        seeded = int(time.time())
        expiration = seeded + 300
        otp_object = {
            "otp": otp,
            "faceId": face_id,
            "seeded": str(seeded),
            "expiration": str(expiration)
        }
        passcodes_table.put_item(Item=otp_object)
        
        """
        6) Send SNS to vistor with OTP.
        """
        msg = "Your OTP:\n{}".format(otp)
        print("Newly Visitor: {} Phone Number: {}".format(visitor_name, visitor_phone_number))
        sns = boto3.client("sns")
        sns.publish(PhoneNumber=visitor_phone_number, Message=msg)
        
        """
        7) Return confirmation JSON object.
        """
        response_object = {
            "body": {
                "exists": "True",
                "name": visitor_name,
                "phone_number": visitor_phone_number,
                "otp": otp
            }
        }
        
        return response_object
    
    else:
        """
        1) Get pending object.
        """
        pending_visitor = pending_response["Item"]
        
        """
        2) Delete pending visitor from pending table.
        """
        pending_table.delete_item(Key={"faceId": face_id})
        
        """
        3) Get photo name and delete photo from S3 bucket.
        """
        photo = pending_visitor["photos"][0]
        s3_client = boto3.client("s3")
        s3_client.delete_object(Bucket="ds-b1", Key=photo["objectkey"])
        
        """
        4) Delete photo from Rekognition collection.
        """
        rekognition_client = boto3.client("rekognition")
        rekognition_client.delete_faces(
            CollectionId="door-security",
            FaceIds=[face_id]
        )
        
        """
        5) Return denial response.
        """
        denial_response = {
            "body": {
                "exists": "True",
                "face_id": face_id
            }
        }
        
        return denial_response