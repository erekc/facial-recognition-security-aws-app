"""
LF1
"""

import json
import boto3
import base64
import time
import random
import string
import sys
from boto3.dynamodb.conditions import Key, Attr
sys.path.insert(1, '/opt')
import cv2

"""
DynamoDB Client to connect to DynamoDB.
"""
class DynamoDBClient:
    
    def __init__(self, region_name='us-west-2'):
        self.dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
    
    def insert_to_table(self, table_name, item):
        table = self.dynamodb.Table(table_name)
        table.put_item(Item=item)
        
    def get_from_table_key(self, table_name, key):
        table = self.dynamodb.Table(table_name)
        item = table.get_item(Key=key)
        return item
    
    def get_from_table_attr(self, table_name, attr, value, index_name):
        table = self.dynamodb.Table(table_name)
        response = table.query(
            IndexName=index_name,
            KeyConditionExpression=Key(attr).eq(value)
        )
        return response
"""
Handles inputing and comparing OTP.
"""
class OTPManager:
    
    def __init__(self):
        self.dynamodb_client = DynamoDBClient()
        self.table_name = "passcodes"
        
    def __visitor_already_in_table(self, face_id):
        response = self.dynamodb_client.get_from_table_attr(self.table_name, "faceId", face_id, "faceId-index")
        return True if response["Count"] != 0 else False
    
    def __otp_already_in_table(self, otp):
        item = self.dynamodb_client.get_from_table_key(self.table_name, {"otp": otp})
        return True if len(item) == 2 else False
    
    def insert_to_table(self, otp, face_id):
        print("OTP: {} FaceId: {}".format(otp, face_id))
        """ 
        Check if otp is already in table.
        """
        if not self.__otp_already_in_table(otp):
            """
            Check if id was already given OTP.
            """
            if not self.__visitor_already_in_table(face_id):
                seeded = int(time.time())
                expiration = seeded + 300
                item = {}
                item["otp"] = otp
                item["faceId"] = face_id
                item["seeded"] = str(seeded)
                item["expiration"] = str(expiration)
                self.dynamodb_client.insert_to_table(self.table_name, item)
                return 1
            return 0
        return -1
        
        
    def create_otp(self):
        otp = ''.join([random.choice(string.ascii_lowercase+string\
                .ascii_uppercase+string.digits) for n in range(10)])
        return otp

"""
Record handling for face search response and matches.
"""
class KinesisRecordHandler:
    
    def __init__(self, record):
        self.record = record
        self.face_search_response = self.__get_face_search_response()
        self.match_ids = self.__get_match_ids()
    
    def __get_face_search_response(self):
        data = self.record["kinesis"]["data"]
        data = base64.b64decode(data)
        kinesis_object = json.loads(data)
        face_search_response = kinesis_object["FaceSearchResponse"]
        return face_search_response
    
    def has_detected_faces(self):
        return True if self.face_search_response != [] else False
    
    def __get_match_ids(self):
        matched_ids = []
        if self.has_detected_faces():
            for detection in self.face_search_response:
                matched_faces = detection["MatchedFaces"]
                if matched_faces != []:
                    for match in matched_faces:
                        match_id = match["Face"]["FaceId"]
                        if match_id not in matched_ids:
                            matched_ids.append(match_id)
        return matched_ids
    
    def has_matches(self):
        return True if self.match_ids != [] else False

"""
Handles data from KDS.
"""
class KinesisHandler:
    
    def __init__(self, event):
        self.event = event
        self.dynamodb_client = DynamoDBClient()
    
    def handle_event(self):
        for record in self.event["Records"]:
            print("Handling Kinesis record")
            record_handler = KinesisRecordHandler(record)
            print("Created KinesisRecordHandler object")
            """
            If the face matches, send visitor OTP.
            """
            if record_handler.has_detected_faces():
                if record_handler.has_matches():
                    print("Face has a match")
                    self.__handle_matched_face(record_handler)
                else:
                    print("Face doesn't have matches")
                    self.__handle_unmatched_face(record_handler, "ds-b1", "pending")
                    
    def __handle_unmatched_face(self, record_handler, photo_bucket, dynamo_table):
        print("Handling unmatched face")
        """
        Assumes only one person in photo.
        """
        """
        1) Undetected face comes in.
        """
        photo_handler = PhotoHandler(
            "ds-b1",
            "<KVS Stream Arn>",
            "us-west-2"
        )
        """
        2 & 3) Use OpenCV to upload image to S3
        """
        new_face_photo, new_face_url = photo_handler.capture_and_upload_image()
        if new_face_photo == None:
            return False
        
        """
        4) Send image to Rekognition collection and obtain FaceId
        """
        rekognition_client = boto3.client("rekognition")
        insert_collection_response = rekognition_client.index_faces(
            CollectionId = "door-security",
            Image = {
                "S3Object": {
                    "Bucket": photo_bucket,
                    "Name": new_face_photo,
                }
            },
            ExternalImageId = new_face_photo.split(".")[0],
            MaxFaces = 1
        )
        indexed_face_object = insert_collection_response["FaceRecords"][0]
        indexed_face_id = indexed_face_object["Face"]["FaceId"]
        
        """
        5) Put pending visitor into "pending" table
        """
        pending_object = {
            "faceId": indexed_face_id,
            "photos": [
                {
                    "objectkey": new_face_photo,
                    "bucket": "ds-b1",
                    "createdtimestamp": new_face_photo.split(".")[0]
                }
            ]
        }
        self.dynamodb_client.insert_to_table(dynamo_table, pending_object)
        
        """
        6) Send owner faceId, WP1 link, and link to str(created).jpg
        """
        sns = boto3.client("sns")
        link = "http://door-wp1.s3-website-us-west-2.amazonaws.com/?faceId={}"\
            .format(indexed_face_id)
        msg = "NEW VISITOR PENDING APPROVAL\n"\
            + "FaceId: {}\n".format(indexed_face_id)\
            + "URL: {}\n".format(new_face_url)\
            + "Use link to approve: {}".format(link)
        sns.publish(PhoneNumber="<phone_number>", Message=msg)
        topic = boto3.resource("sns").Topic("arn:aws:sns:us-west-2:<AccountId>:LF1")
        topic.publish(Message=msg)
        
        return True
        
        
    
    def __handle_matched_face(self, record_handler):
        print("Handling matched face")
        """
        Assumes only one person in photo.
        """
        face_id = record_handler.match_ids[0]
        print("FaceId: {}".format(face_id))
        
        """
        If id not in visitors, do nothing because the face hasn't yet been approved.
        """
        if len(self.dynamodb_client.get_from_table_key("visitors", {"faceId": face_id})) < 2:
            print("Visitor not yet approved")
            return False
        
        otp_manager = OTPManager()
        
        """
        Send SMS if visitor not already given OTP. Return True
        Stop if visitor has already been given OTP. Return False
        """
        otp = otp_manager.create_otp()
        success_criteria = otp_manager.insert_to_table(otp, face_id)
        print("Sucess Criteria: {}".format(success_criteria))
        
        """
        If faceId already been given OTP or OTP already in table
        """
        if success_criteria < 1:
            
            """
            If faceId already been given OTP
            """
            if success_criteria == 0:
                return False
            
            """
            If OTP already in table
            """
            print("Getting new OTP")
            while success_criteria != 1:
                otp = otp_manager.create_otp()
                success_criteria = otp_manager.insert_to_table(otp, face_id)
            
        print("Sending SMS")
        sns = boto3.client("sns")
        msg = "Your OTP:\n{}".format(otp)
        dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
        visitor_table = dynamodb.Table("visitors")
        visitor = visitor_table.get_item(Key={"faceId": face_id})
        phone_number = visitor["Item"]["phoneNumber"]
        print("Visitor: {} Phone Number: {}".format(visitor, phone_number))
        sns.publish(PhoneNumber=phone_number, Message=msg)
        return True
        
        
"""
Handles getting image from stream then uploading to S3.
"""
class PhotoHandler:
    
    def __init__(self, bucket, stream_arn, region):
        self.bucket = bucket
        self.stream_arn = stream_arn
        self.region = region
    
    def capture_and_upload_image(self):
        print("Capturing Image")
        kvs_client = boto3.client('kinesisvideo', region_name="us-west-2")
        kvs_data_pt = kvs_client.get_data_endpoint(
            StreamARN=self.stream_arn, # kinesis stream arn
            APIName='GET_MEDIA'
        )
        
        print(kvs_data_pt)
        
        end_pt = kvs_data_pt['DataEndpoint']
        kvs_video_client = boto3.client('kinesis-video-media', endpoint_url=end_pt, region_name=self.region) # provide your region
        kvs_stream = kvs_video_client.get_media(
            StreamARN=self.stream_arn, # kinesis stream arn
            StartSelector={'StartSelectorType': 'NOW'} # to keep getting latest available chunk on the stream
        )
        print(kvs_stream)
        
        payload = kvs_stream['Payload']
        print(payload)
        print("Writing Locally")
        # write locally
        i = 1
        mkv = 'stream.mkv'
        video_path = '/tmp/' + mkv
        with open('/tmp/' + mkv, 'w+b') as f:
            print("Reading from Payload")
            chunk = payload.read(1024*8)
            print(chunk)
            print("Payload Read")
            while chunk and i < 2000:
                f.write(chunk)
                print(chunk)
                chunk = payload.read(1024 * 8)
                i += 1
        f.close()
        
        print("Capture Frame")
        vidcap = cv2.VideoCapture(video_path)
        success, image = vidcap.read()
        if success:
            print("Success")
            image_name = 'frame.png'
            image_path = '/tmp/' + image_name
            cv2.imwrite(image_path, image)
        
            print("Uploading to S3")
            photo_name = str(time.time()) + ".png"    
            s3_client = boto3.client('s3')
            s3_client.upload_file(
                '/tmp/frame.png',
                self.bucket, # replace with your bucket name
                photo_name
            )
            return photo_name, "https://{}.s3-{}.amazonaws.com/{}".format(self.bucket, self.region, photo_name)
        return None

def lambda_handler(event, context):
    kinesis_handler = KinesisHandler(event)
    kinesis_handler.handle_event()
        
    return {
        'statusCode': 200,
        'body': "Finished"
    }
