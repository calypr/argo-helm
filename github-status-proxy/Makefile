.PHONY: help build test test-unit test-coverage clean docker-build

GO := go
BINARY_NAME := github-status-proxy
DOCKER_IMAGE := ghcr.io/calypr/github-status-proxy:latest

help:
	@echo 'Available commands:'
	@echo '  build         Build the Go binary'
	@echo '  test          Run all tests'
	@echo '  test-unit     Run unit tests'
	@echo '  test-coverage Run tests with coverage'
	@echo '  docker-build  Build Docker image'
	@echo '  clean         Clean up build artifacts'

build:
	$(GO) build -o $(BINARY_NAME) .

test: test-coverage

test-unit:
	$(GO) test -v ./...

test-coverage:
	$(GO) test -v -coverprofile=coverage.out ./...
	$(GO) tool cover -html=coverage.out -o coverage.html

docker-build:
	docker build -t $(DOCKER_IMAGE) .

clean:
	rm -f $(BINARY_NAME)
	rm -f coverage.out coverage.html
	$(GO) clean
