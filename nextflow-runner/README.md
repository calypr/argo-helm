# Nextflow Runner Container Image

This directory contains the Dockerfile for a custom Nextflow runner container image used by the `nextflow-runner` WorkflowTemplate.

## Purpose

This image pre-installs Nextflow and all required system dependencies, eliminating the need to install them at runtime during workflow execution. This improves workflow startup time and efficiency.

## Pre-installed Components

- Eclipse Temurin JRE 17 (base image)
- Nextflow (installed from https://get.nextflow.io)
- System packages: curl, git, ca-certificates, coreutils

## Building the Image

```bash
docker build -t nextflow-runner:latest .
```

## Usage

This image is referenced in the `workflowtemplate-nextflow-runner.yaml` Helm template. Update the `image` field in the container spec to use this custom image instead of the base `eclipse-temurin:17-jre-jammy` image.

## Environment Variables

- `NXF_ANSI_LOG`: Set to `false` to disable ANSI colors in logs
- `NXF_VER`: Nextflow version (default: `23.10.1`)

These can be overridden in the workflow template if needed.
