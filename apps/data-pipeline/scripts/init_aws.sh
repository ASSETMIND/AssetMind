# echo "==============================================="
# echo "S3 Bucket Initialization Started..."
# echo "==============================================="

# aws --endpoint-url=http://localstack:4566 s3 mb s3://data-pipeline-bronze || echo "Bucket already exists. Skipping..."
# aws --endpoint-url=http://localstack:4566 s3 mb s3://data-pipeline-silver || echo "Bucket already exists. Skipping..."
# aws --endpoint-url=http://localstack:4566 s3 mb s3://data-pipeline-gold || echo "Bucket already exists. Skipping..."

# echo "==============================================="
# echo "S3 Bucket Initialization Completed!"
# echo "==============================================="

#!/bin/bash
echo "==============================================="
echo "MinIO S3 Bucket Initialization Started..."
echo "==============================================="

aws --endpoint-url=http://localhost:9000 s3 mb s3://data-pipeline-bronze || echo "Bucket already exists. Skipping..."
aws --endpoint-url=http://localhost:9000 s3 mb s3://data-pipeline-silver || echo "Bucket already exists. Skipping..."
aws --endpoint-url=http://localhost:9000 s3 mb s3://data-pipeline-gold || echo "Bucket already exists. Skipping..."

echo "==============================================="
echo "MinIO S3 Bucket Initialization Completed!"
echo "==============================================="