#!/bin/bash
# =======================================================================
# Load common functions
# =======================================================================
. "/root/gravitino/common/common.sh"

# =======================================================================
# Prepare target directory for packages
# =======================================================================
target_dir="/root/gravitino"
if [[ ! -d "${target_dir}/packages" ]]; then
  mkdir -p "${target_dir}/packages"
fi

# =======================================================================
# Download Hadoop Common JAR and MD5
# Why?: This is needed as a dependency for hadoop-aws (provides AuditSpanSource and other classes)
# =======================================================================
HADOOP_COMMON_JAR="https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-common/${HADOOP_AWS_JAR_VERSION}/hadoop-common-${HADOOP_AWS_JAR_VERSION}.jar"
echo "Downloading hadoop-common ${HADOOP_AWS_JAR_VERSION}"
HADOOP_COMMON_MD5="${HADOOP_COMMON_JAR}.md5"
download_and_verify "${HADOOP_COMMON_JAR}" "${HADOOP_COMMON_MD5}" ${target_dir}

# =======================================================================
# Download Hadoop AWS JAR and MD5
# Why?: This is needed for Gravitino to connect to S3 compatible storage like MinIO
# =======================================================================
HADOOP_AWS_JAR="https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/${HADOOP_AWS_JAR_VERSION}/hadoop-aws-${HADOOP_AWS_JAR_VERSION}.jar"
echo "Downloading hadoop-aws ${HADOOP_AWS_JAR_VERSION}"
HADOOP_AWS_MD5="${HADOOP_AWS_JAR}.md5"
download_and_verify "${HADOOP_AWS_JAR}" "${HADOOP_AWS_MD5}" ${target_dir}

# Download Spark Protobuf connector
RUN wget "https://repo1.maven.org/maven2/org/apache/spark/spark-protobuf_2.12/3.5.5/spark-protobuf_2.12-3.5.5.jar" \
    -O $SPARK_HOME/jars/spark-protobuf_2.12-3.5.5.jar

# =======================================================================
# Download AWS Java SDK Bundle JAR and MD5
# Why?: This is needed for Gravitino to connect to S3 compatible storage like MinIO
# =======================================================================
AWS_JAVA_SDK_BUNDLE_JAR="https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/${AWS_JAVA_SDK_BUNDLE_JAR_VERSION}/aws-java-sdk-bundle-${AWS_JAVA_SDK_BUNDLE_JAR_VERSION}.jar"
AWS_JAVA_SDK_BUNDLE_MD5="${AWS_JAVA_SDK_BUNDLE_JAR}.md5"
download_and_verify "${AWS_JAVA_SDK_BUNDLE_JAR}" "${AWS_JAVA_SDK_BUNDLE_MD5}" ${target_dir}

# =======================================================================
# Download Iceberg AWS JAR and MD5
# Why?: This is needed for S3FileIO support in Iceberg REST Catalog
# =======================================================================
ICEBERG_AWS_JAR="https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-aws/${ICEBERG_VERSION}/iceberg-aws-${ICEBERG_VERSION}.jar"
ICEBERG_AWS_MD5="${ICEBERG_AWS_JAR}.md5"
download_and_verify "${ICEBERG_AWS_JAR}" "${ICEBERG_AWS_MD5}" ${target_dir}

# =======================================================================
# Download AWS SDK v2 Bundle JAR
# Why?: Required by Iceberg AWS for S3FileIO with modern AWS SDK
# =======================================================================
echo "Downloading AWS SDK v2 Bundle ${AWS_SDK_V2_VERSION}"
AWS_SDK_V2_BUNDLE_JAR="https://repo1.maven.org/maven2/software/amazon/awssdk/bundle/${AWS_SDK_V2_VERSION}/bundle-${AWS_SDK_V2_VERSION}.jar"
wget -q "${AWS_SDK_V2_BUNDLE_JAR}" -P "${target_dir}/packages"

AWS_SDK_V2_URL_CLIENT_JAR="https://repo1.maven.org/maven2/software/amazon/awssdk/url-connection-client/${AWS_SDK_V2_VERSION}/url-connection-client-${AWS_SDK_V2_VERSION}.jar"
wget -q "${AWS_SDK_V2_URL_CLIENT_JAR}" -P "${target_dir}/packages"
