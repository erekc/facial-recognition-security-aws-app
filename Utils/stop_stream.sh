#! /bin/bash

aws rekognition stop-stream-processor --name face-rekog-processor --region us-west-2
aws rekognition delete-stream-processor --name face-rekog-processor --region us-west-2
aws rekognition delete-collection --collection-id door-security --region us-west-2