import boto3
import sys

def remove_face(face_id):
    dynamodb_client = boto3.resource("dynamodb", region_name="us-west-2")
    visitor_table = dynamodb_client.Table("visitors")
    visitor_table.delete_item(Key={"faceId": face_id})
    print("Deleted Visitor")
    
if __name__ == "__main__":
    face_id = sys.argv[1]
    remove_face(face_id)