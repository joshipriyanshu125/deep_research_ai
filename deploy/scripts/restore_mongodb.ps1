# MongoDB Restore Script (PowerShell)
param (
    [Parameter(Mandatory=$true)]
    [string]$ArchivePath,
    [string]$MongoUri = "mongodb://localhost:27017",
    [string]$DbName = "deep_research_ai",
    [switch]$DropExisting
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ArchivePath)) {
    Write-Error "Backup archive not found at: $ArchivePath"
    exit 1
}

Write-Host "Restoring MongoDB database '$DbName' from archive '$ArchivePath'..."

$DropFlag = if ($DropExisting) { "--drop" } else { "" }

if (Get-Command mongorestore -ErrorAction SilentlyContinue) {
    & mongorestore --uri="$MongoUri" --nsInclude="${DbName}.*" --gzip --archive="$ArchivePath" $DropFlag
    Write-Host "Restore operation completed successfully."
} else {
    Write-Warning "mongorestore not found on PATH. If running with Docker, execute: docker exec -i deep_research_mongodb mongorestore --nsInclude=${DbName}.* --gzip --archive < $ArchivePath"
}
