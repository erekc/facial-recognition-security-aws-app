#!/bin/bash

aws rekognition create-collection --collection-id door-security --region us-west-2
aws rekognition create-stream-processor --region us-west-2 --cli-input-json file://stream.json
aws rekognition start-stream-processor --name face-rekog-processor --region us-west-2