#!/bin/bash

aws rekognition index-faces --image '{"S3Object":{"Bucket":"<BUCKET>","Name":"<PHOTOKEY>"}}' --collection-id "<COLLECTIONID>" --detection-attributes "ALL" --external-image-id "<IMAGEID>" --region <REGION>
echo "Added Vistor to Collection. Now call add_visitor.py <face_id>"