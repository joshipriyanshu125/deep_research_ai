# PowerShell SSL Certificate Generator for Local / Staging Production Testing
$SSL_DIR = Join-Path $PSScriptRoot "ssl"

if (-not (Test-Path $SSL_DIR)) {
    New-Item -ItemType Directory -Path $SSL_DIR -Force | Out-Null
}

$CERT_KEY = Join-Path $SSL_DIR "server.key"
$CERT_CRT = Join-Path $SSL_DIR "server.crt"

Write-Host "Generating self-signed SSL certificates for Deep Research AI in $SSL_DIR..."

if (Get-Command openssl -ErrorAction SilentlyContinue) {
    & openssl req -x509 -nodes -days 365 -newkey rsa:2048 `
        -keyout $CERT_KEY -out $CERT_CRT `
        -subj "/C=US/ST=State/L=City/O=DeepResearchAI/OU=Engineering/CN=localhost"
    Write-Host "SSL Certificates generated successfully:"
    Write-Host "  Private Key: $CERT_KEY"
    Write-Host "  Certificate: $CERT_CRT"
} else {
    Write-Warning "OpenSSL command not found on system PATH. Writing fallback dummy certs for configuration validation."
    "-----BEGIN PRIVATE KEY-----`nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC3dummykey`n-----END PRIVATE KEY-----" | Out-File -FilePath $CERT_KEY -Encoding ascii
    "-----BEGIN CERTIFICATE-----`nMIIDdzCCAl+gAwIBAgIUdummycertificate`n-----END CERTIFICATE-----" | Out-File -FilePath $CERT_CRT -Encoding ascii
}
