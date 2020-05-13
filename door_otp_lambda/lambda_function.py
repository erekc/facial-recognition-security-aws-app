"""
door_otp
"""

import json
import boto3
import time
from boto3.dynamodb.conditions import Key, Attr

def lambda_handler(event, context):
    otp = event["otp"]
    print("Input OTP: {}".format(otp))
    dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
    otp_table = dynamodb.Table("passcodes")
    otp_response = otp_table.get_item(Key={"otp": otp})
    print(otp_response)
    
    """
    Return approval response if otp is found and hasn't past TTL.
    Else return denial response.
    """
    if len(otp_response) < 2:
        print("OTP nonexistent")
        return {
            'statusCode': 500,
            'body': {
                "approval": "denied",
                "otp": otp
            }
        }
        
    otp_item = otp_response["Item"]
        
    """
    If approved return personalized welcome.
    TODO: Maybe delete OTP???
    """
    if time.time() < int(otp_item["expiration"]):
        print("Valid OTP")
        visitor_table = dynamodb.Table("visitors")
        face_id = otp_item["faceId"]
        visitor = visitor_table.get_item(Key={"faceId": face_id})
        visitor_name = visitor["Item"]["name"]
        print("Visitor: {}".format(visitor_name))
        response = {
            'statusCode': 200,
            'body': {
                "approval": "approved",
                "otp": otp,
                "visitor": visitor_name
            }
        }
        print(response)
        """
        Delete OTP from table
        """
        otp_table.delete_item(Key={"otp": otp})
        return response
    else:
        print("Expired OTP")
        return {
            'statusCode': 500,
            'body': {
                "approval": "denied",
                "otp": otp
            }
        }