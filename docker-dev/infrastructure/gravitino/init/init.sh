#!/bin/bash
echo "Start to download the jar packages"

# =======================================================================
# Copy all of the JAR files to their respective folders
# =======================================================================
cp "/root/gravitino/packages/hadoop-common-${HADOOP_AWS_JAR_VERSION}.jar" /root/gravitino/iceberg-rest-server/libs
cp "/root/gravitino/packages/hadoop-common-${HADOOP_AWS_JAR_VERSION}.jar" /root/gravitino/catalogs/lakehouse-iceberg/libs
cp "/root/gravitino/packages/hadoop-aws-${HADOOP_AWS_JAR_VERSION}.jar" /root/gravitino/iceberg-rest-server/libs
cp "/root/gravitino/packages/hadoop-aws-${HADOOP_AWS_JAR_VERSION}.jar" /root/gravitino/catalogs/lakehouse-iceberg/libs
cp "/root/gravitino/packages/aws-java-sdk-bundle-${AWS_JAVA_SDK_BUNDLE_JAR_VERSION}.jar" /root/gravitino/iceberg-rest-server/libs
cp "/root/gravitino/packages/aws-java-sdk-bundle-${AWS_JAVA_SDK_BUNDLE_JAR_VERSION}.jar" /root/gravitino/catalogs/lakehouse-iceberg/libs
cp "/root/gravitino/packages/iceberg-aws-${ICEBERG_VERSION}.jar" /root/gravitino/iceberg-rest-server/libs
cp "/root/gravitino/packages/iceberg-aws-${ICEBERG_VERSION}.jar" /root/gravitino/catalogs/lakehouse-iceberg/libs
cp "/root/gravitino/packages/bundle-${AWS_SDK_V2_VERSION}.jar" /root/gravitino/iceberg-rest-server/libs
cp "/root/gravitino/packages/bundle-${AWS_SDK_V2_VERSION}.jar" /root/gravitino/catalogs/lakehouse-iceberg/libs
cp "/root/gravitino/packages/url-connection-client-${AWS_SDK_V2_VERSION}.jar" /root/gravitino/iceberg-rest-server/libs
cp "/root/gravitino/packages/url-connection-client-${AWS_SDK_V2_VERSION}.jar" /root/gravitino/catalogs/lakehouse-iceberg/libs


# =======================================================================
# Copy all of the configuration in their respective folders
# =======================================================================
cp /tmp/conf/gravitino.conf /root/gravitino/conf/gravitino.conf
cp /tmp/conf/core-site.xml /root/gravitino/conf/core-site.xml
cp /tmp/conf/core-site.xml /root/gravitino/iceberg-rest-server/conf/core-site.xml

# =======================================================================
# Start Gravitino server
# =======================================================================
echo "Finish downloading"
echo "Start the Gravitino Server"
/bin/bash /root/gravitino/bin/gravitino.sh start &

# Wait for Gravitino to be ready
echo "Waiting for Gravitino to be ready..."
sleep 10

# Initialize metalake and catalog
echo "Initializing metalake and catalog..."
/bin/bash /tmp/common/init_metalake_catalog.sh

# Tail logs
tail -f /root/gravitino/logs/gravitino-server.log