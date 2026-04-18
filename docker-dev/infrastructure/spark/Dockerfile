# Declare ARGs before first FROM for global scope
ARG PYTHON_VERSION
ARG SPARK_VERSION
ARG SPARK_SCALA_VERSION
ARG ICEBERG_VERSION
ARG POSTGRESQL_JAR_VERSION
ARG HADOOP_AWS_JAR_VERSION
ARG AWS_JAVA_SDK_BUNDLE_JAR_VERSION
ARG AWS_SDK_V2_VERSION=2.25.11
ARG KAFKA_VERSION
ARG SPARK_KAFKA_VERSION

# Stage 1: Base Image
FROM python:${PYTHON_VERSION}-slim-bookworm AS spark-base

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    sudo \
    curl \
    wget \
    vim \
    unzip \
    rsync \
    software-properties-common \
    openjdk-17-jdk \
    build-essential \
    ssh && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Stage 2: Spark Installation
FROM spark-base AS spark

# Redeclare ARGs inside stage if needed
ARG SPARK_VERSION
ARG SPARK_SCALA_VERSION
ARG ICEBERG_VERSION
ARG POSTGRESQL_JAR_VERSION
ARG HADOOP_AWS_JAR_VERSION
ARG AWS_JAVA_SDK_BUNDLE_JAR_VERSION
ARG AWS_SDK_V2_VERSION
ARG KAFKA_VERSION
ARG SPARK_KAFKA_VERSION

ENV SPARK_HOME="/root/spark"
RUN mkdir -p ${SPARK_HOME}
WORKDIR ${SPARK_HOME}

RUN curl https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop3.tgz -o ${SPARK_HOME}/spark-${SPARK_VERSION}-bin-hadoop3.tgz \
    && tar xvzf ${SPARK_HOME}/spark-${SPARK_VERSION}-bin-hadoop3.tgz --directory ${SPARK_HOME} --strip-components 1 \
    && rm -rf ${SPARK_HOME}/spark-${SPARK_VERSION}-bin-hadoop3.tgz

# Install Kafka and Protobuf JARs
RUN wget "https://repo1.maven.org/maven2/org/apache/spark/spark-protobuf_2.12/${SPARK_KAFKA_VERSION}/spark-protobuf_2.12-${SPARK_KAFKA_VERSION}.jar" \
    -O $SPARK_HOME/jars/spark-protobuf_2.12-${SPARK_KAFKA_VERSION}.jar && \
    wget "https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/${SPARK_KAFKA_VERSION}/spark-token-provider-kafka-0-10_2.12-${SPARK_KAFKA_VERSION}.jar" \
    -O $SPARK_HOME/jars/spark-token-provider-kafka-0-10_2.12-${SPARK_KAFKA_VERSION}.jar && \
    wget "https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/${KAFKA_VERSION}/kafka-clients-${KAFKA_VERSION}.jar" \
    -O $SPARK_HOME/jars/kafka-clients-${KAFKA_VERSION}.jar && \
    wget "https://repo1.maven.org/maven2/org/apache/kafka/kafka_2.12/${KAFKA_VERSION}/kafka_2.12-${KAFKA_VERSION}.jar" \
    -O $SPARK_HOME/jars/kafka_2.12-${KAFKA_VERSION}.jar && \
    wget "https://repo1.maven.org/maven2/commons-pool/commons-pool/1.5.4/commons-pool-1.5.4.jar" \
    -O $SPARK_HOME/jars/commons-pool-1.5.4.jar && \
    wget "https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar" \
    -O $SPARK_HOME/jars/commons-pool2-2.11.1.jar

# Install AWS SDK Bundle for S3 access (required by Iceberg S3FileIO)
RUN wget "https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/${HADOOP_AWS_JAR_VERSION}/hadoop-aws-${HADOOP_AWS_JAR_VERSION}.jar" \
    -O $SPARK_HOME/jars/hadoop-aws-${HADOOP_AWS_JAR_VERSION}.jar && \
    wget "https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/${AWS_JAVA_SDK_BUNDLE_JAR_VERSION}/aws-java-sdk-bundle-${AWS_JAVA_SDK_BUNDLE_JAR_VERSION}.jar" \
    -O $SPARK_HOME/jars/aws-java-sdk-bundle-${AWS_JAVA_SDK_BUNDLE_JAR_VERSION}.jar

# Install AWS SDK v2 for Iceberg S3FileIO
RUN wget "https://repo1.maven.org/maven2/software/amazon/awssdk/bundle/${AWS_SDK_V2_VERSION}/bundle-${AWS_SDK_V2_VERSION}.jar" \
    -O $SPARK_HOME/jars/aws-sdk-v2-bundle-${AWS_SDK_V2_VERSION}.jar && \
    wget "https://repo1.maven.org/maven2/software/amazon/awssdk/url-connection-client/${AWS_SDK_V2_VERSION}/url-connection-client-${AWS_SDK_V2_VERSION}.jar" \
    -O $SPARK_HOME/jars/url-connection-client-${AWS_SDK_V2_VERSION}.jar

# Stage 3: Spark Dependencies
FROM spark AS spark-deps

# Copy scripts
COPY ./infrastructure/common/ ./common/
COPY ./infrastructure/spark/init/ ./init/

# Fix line endings (CRLF to LF)
RUN sed -i 's/\r$//' ./init/*.sh ./common/*.sh

# Run dependency script
RUN chmod u+x ./init/dependency.sh && ./init/dependency.sh

# Stage 4: Python Libraries
FROM spark-deps AS spark-python

COPY ./infrastructure/spark/requirements.txt .
RUN pip3 install -r requirements.txt

ENV PATH="${SPARK_HOME}/sbin:${SPARK_HOME}/bin:${PATH}"
ENV SPARK_MASTER="spark://spark-master:7077"
ENV SPARK_MASTER_HOST=spark-master
ENV SPARK_MASTER_PORT=7077
ENV PYSPARK_PYTHON=python3

RUN chmod u+x ./sbin/* && chmod u+x ./bin/*
ENV PYTHONPATH=$SPARK_HOME/python/:$PYTHONPATH

RUN chmod u+x ./init/init.sh
ENTRYPOINT [ "./init/init.sh" ]