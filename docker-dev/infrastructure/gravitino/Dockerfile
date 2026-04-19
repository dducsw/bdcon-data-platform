ARG GRAVITINO_IMAGE_TAG
FROM apache/gravitino:${GRAVITINO_IMAGE_TAG} AS gravitino-base

# =======================================================================
# Build layer image from gravitino-base image
# =======================================================================
FROM gravitino-base AS gravitino

ARG HADOOP_AWS_JAR_VERSION
ARG AWS_JAVA_SDK_BUNDLE_JAR_VERSION
ARG AWS_SDK_V2_VERSION=2.25.11
ARG ICEBERG_VERSION

# Set working directory
WORKDIR /root/gravitino

# Copy all initialization scripts
# Commmon initialization scripts
COPY ./infrastructure/common/ ./common/
# Gravitino initialization scripts
COPY ./infrastructure/gravitino/init/ ./init/

# Fix line endings (CRLF to LF) for scripts just in case
RUN sed -i 's/\r$//' ./init/*.sh ./common/*.sh

# Install Gravitino Dependencies
RUN chmod u+x ./init/dependency.sh && ./init/dependency.sh

# Run Gravitino Initialization Script
RUN chmod u+x ./init/init.sh
ENTRYPOINT [ "./init/init.sh" ]