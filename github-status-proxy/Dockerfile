# Use busybox as a minimal base with basic utilities
FROM busybox:glibc

WORKDIR /app

# Copy the pre-built binary
# The binary should be built before running docker build using:
# CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -a -installsuffix cgo -o github-status-proxy .
COPY github-status-proxy /app/github-status-proxy

# Make the binary executable
RUN chmod +x /app/github-status-proxy

# Expose port
EXPOSE 8080

# Run the binary
CMD ["/app/github-status-proxy"]
