echo "==============================================="
echo "S3 Bucket Initialization Started..."
echo "==============================================="

aws --endpoint-url=http://localstack:4566 s3 mb s3://toss-datalake-raw-zone-prd || echo "Bucket already exists. Skipping..."

echo "==============================================="
echo "S3 Bucket Initialization Completed!"
echo "==============================================="
