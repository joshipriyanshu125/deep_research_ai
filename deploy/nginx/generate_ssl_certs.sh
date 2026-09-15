#!/usr/bin/env bash
# Bash SSL Certificate Generator for Linux Production Hosts / CI
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SSL_DIR="${DIR}/ssl"

mkdir -p "${SSL_DIR}"

CERT_KEY="${SSL_DIR}/server.key"
CERT_CRT="${SSL_DIR}/server.crt"

echo "Generating self-signed SSL certificates in ${SSL_DIR}..."

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "${CERT_KEY}" -out "${CERT_CRT}" \
    -subj "/C=US/ST=State/L=City/O=DeepResearchAI/OU=Engineering/CN=localhost"

chmod 600 "${CERT_KEY}"
chmod 644 "${CERT_CRT}"

echo "SSL Certificates generated successfully:"
echo "  Private Key: ${CERT_KEY}"
echo "  Certificate: ${CERT_CRT}"
