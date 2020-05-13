#!/bin/bash

aws rekognition delete-faces --collection-id "<COLLECTION_ID>" --region us-west-2 --face-ids "[$1]"
python3 remove_visitor.py $1
echo "Removed Visitor"