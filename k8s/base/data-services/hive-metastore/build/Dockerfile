# ====================================================================
# Hive Metastore 3.1.2 Dockerfile
# Base: openjdk:8-jre-slim (Hive 3.x requires Java 8)
# Installs Hadoop 3.3.1, Hive 3.1.2, PostgreSQL JDBC, and AWS S3 JARs
# ====================================================================
FROM openjdk:8-jre-slim

ARG HADOOP_VERSION=3.3.1
ARG HIVE_VERSION=3.1.2
ARG POSTGRESQL_JAR_VERSION=42.7.5
ARG AWS_JAVA_SDK_BUNDLE_JAR_VERSION=1.12.367

USER root

# Install dependencies
RUN apt-get update && apt-get install -y wget curl bash netcat-traditional && rm -rf /var/lib/apt/lists/*

# Download and extract Hadoop
RUN wget -q https://archive.apache.org/dist/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz && \
    tar -xzf hadoop-${HADOOP_VERSION}.tar.gz -C /opt/ && \
    rm hadoop-${HADOOP_VERSION}.tar.gz && \
    ln -s /opt/hadoop-${HADOOP_VERSION} /opt/hadoop

# Download and extract Hive
RUN wget -q https://archive.apache.org/dist/hive/hive-${HIVE_VERSION}/apache-hive-${HIVE_VERSION}-bin.tar.gz && \
    tar -xzf apache-hive-${HIVE_VERSION}-bin.tar.gz -C /opt/ && \
    rm apache-hive-${HIVE_VERSION}-bin.tar.gz && \
    ln -s /opt/apache-hive-${HIVE_VERSION}-bin /opt/hive

ENV HADOOP_HOME=/opt/hadoop
ENV HIVE_HOME=/opt/hive
ENV HADOOP_CLASSPATH=${HADOOP_HOME}/share/hadoop/tools/lib/*
ENV PATH=${HIVE_HOME}/bin:${HADOOP_HOME}/bin:$PATH

# Add PostgreSQL JDBC and AWS S3 Jars
RUN wget -q "https://repo1.maven.org/maven2/org/postgresql/postgresql/${POSTGRESQL_JAR_VERSION}/postgresql-${POSTGRESQL_JAR_VERSION}.jar" \
        -O /opt/hive/lib/postgresql-${POSTGRESQL_JAR_VERSION}.jar && \
    wget -q "https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/${HADOOP_VERSION}/hadoop-aws-${HADOOP_VERSION}.jar" \
        -O /opt/hive/lib/hadoop-aws-${HADOOP_VERSION}.jar && \
    wget -q "https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/${AWS_JAVA_SDK_BUNDLE_JAR_VERSION}/aws-java-sdk-bundle-${AWS_JAVA_SDK_BUNDLE_JAR_VERSION}.jar" \
        -O /opt/hive/lib/aws-java-sdk-bundle-${AWS_JAVA_SDK_BUNDLE_JAR_VERSION}.jar

# Fix Guava version conflict (Hive 3.1.2 bundles Guava 19, Hadoop 3.3.1 uses Guava 27)
RUN rm /opt/hive/lib/guava-19.0.jar && \
    cp /opt/hadoop/share/hadoop/hdfs/lib/guava-27.0-jre.jar /opt/hive/lib/ || true

# Copy configuration
COPY conf/hive-site.xml /opt/hive/conf/hive-site.xml

EXPOSE 9083

# Run schema initialization (fails safely if already exists) and then start the metastore
ENTRYPOINT ["/bin/bash", "-c", "/opt/hive/bin/schematool -dbType postgres -initSchema --verbose || true ; /opt/hive/bin/hive --service metastore"]
