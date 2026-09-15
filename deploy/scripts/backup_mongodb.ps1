# Automated MongoDB Backup Script (PowerShell)
param (
    [string]$MongoUri = "mongodb://localhost:27017",
    [string]$DbName = "deep_research_ai",
    [string]$BackupDir = "./backups",
    [int]$RetentionDays = 7
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ArchiveName = "${DbName}_backup_${Timestamp}.gz"
$ArchivePath = Join-Path $BackupDir $ArchiveName

Write-Host "Starting MongoDB backup for database: $DbName..."
Write-Host "Target archive: $ArchivePath"

if (Get-Command mongodump -ErrorAction SilentlyContinue) {
    & mongodump --uri="$MongoUri" --db="$DbName" --gzip --archive="$ArchivePath"
    $FileSize = (Get-Item $ArchivePath).Length / 1MB
    Write-Host ("Backup completed successfully ({0:N2} MB)." -f $FileSize)
} else {
    Write-Warning "mongodump not found on PATH. If running with Docker, execute: docker exec deep_research_mongodb mongodump --db=$DbName --gzip --archive=/data/db/$ArchiveName"
}

# Rotate old backups
Write-Host "Pruning backups older than $RetentionDays days..."
$CutoffDate = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem -Path $BackupDir -Filter "*.gz" | Where-Object { $_.LastWriteTime -lt $CutoffDate } | ForEach-Object {
    Write-Host "Removing old backup: $($_.Name)"
    Remove-Item $_.FullName -Force
}

Write-Host "Backup operation finished."
