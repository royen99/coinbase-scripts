#!/bin/bash

# Database connection details
DB_NAME="db_name"
DB_USER="db_user"
DB_PASSWORD="db_password"
DB_HOST="localhost"
DB_PORT="5433"

# Backup directory and file name
BACKUP_DIR="/save/backup/here"
BACKUP_FILE="$BACKUP_DIR/db_backup_$(date +%Y%m%d_%H%M%S).sql"

# Ensure the backup directory exists
mkdir -p "$BACKUP_DIR"

# Run pg_dump to create the backup
PGPASSWORD="$DB_PASSWORD" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -F c -b -v -f "$BACKUP_FILE" "$DB_NAME"

# Check if the backup was successful
if [ $? -eq 0 ]; then
  echo "Backup completed successfully. File: $BACKUP_FILE"
else
  echo "Backup failed."
fi