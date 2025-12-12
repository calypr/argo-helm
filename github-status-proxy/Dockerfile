# Runtime image with CA certificates
FROM alpine:3.20

WORKDIR /app

# Install CA bundle so TLS to api.github.com works
RUN apk add --no-cache ca-certificates && update-ca-certificates

# Copy the pre-built binary
# Build it first with:
#   CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o github-status-proxy .
COPY github-status-proxy /app/github-status-proxy

# Make the binary executable
RUN chmod +x /app/github-status-proxy

EXPOSE 8080

CMD ["/app/github-status-proxy"]

