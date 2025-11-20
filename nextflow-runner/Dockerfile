FROM eclipse-temurin:17-jre-jammy

# Install system dependencies
RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    coreutils && \
    rm -rf /var/lib/apt/lists/*

# Install Nextflow
RUN curl -fsSL https://get.nextflow.io | bash && \
    mv nextflow /usr/local/bin/ && \
    chmod +x /usr/local/bin/nextflow

# Verify installation
RUN nextflow -version

# Set working directory
WORKDIR /workspace

# Set environment variables
ENV NXF_ANSI_LOG=false
ENV NXF_VER=23.10.1
