import boto3
import sys

def add_visitor(face_id):
    dynamodb_client = boto3.resource('dynamodb', region_name='us-west-2')
    visitor_table = dynamodb_client.Table("visitors")
    item = {
        "faceId": face_id,
        "name": "Erek Cox",
        "phoneNumber": "+14049189495",
        "photos": []
    }
    visitor_table.put_item(Item=item)
    print("Face added to DynamoDB")

if __name__ == "__main__":
    face_id = sys.argv[1]
    add_visitor(face_id)