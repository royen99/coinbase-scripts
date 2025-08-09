#!/bin/bash

# Database connection details
DB_NAME="db_name"
DB_USER="db_user"
DB_PASSWORD="db_password"
DB_HOST="localhost"
DB_PORT="5433"

# Function to clean up old records from the price_history table
# This function deletes records older than 30 days in batches to avoid long locks
# It uses a consistent cutoff time for the entire operation to ensure no records are missed
# It also verifies the number of records deleted and checks for any remaining old records after cleanup
# The function is designed to be robust against interruptions and can be run multiple times without issues
# It uses a maximum iteration limit to prevent infinite loops in case of unexpected issues.
cleanup_price_history() {
    echo "Starting price_history cleanup at $(date)"

    # Get a consistent cutoff time for the entire operation
    CUTOFF_TIME=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT (NOW() - INTERVAL '30 days')::text")

    # Check how many records will be deleted (using the same cutoff)
    OLD_RECORDS=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT COUNT(*) FROM price_history WHERE timestamp < '$CUTOFF_TIME'::timestamp")

    echo "Found $OLD_RECORDS records older than $CUTOFF_TIME"

    if [ "$OLD_RECORDS" -eq 0 ]; then
        echo "No old records to delete"
        return
    fi

    # Initialize counter
    TOTAL_DELETED=0
    BATCH_SIZE=10000
    MAX_ITERATIONS=100  # Safety net
    ITERATION=0

    echo "Beginning batched deletion..."

    while [ $ITERATION -lt $MAX_ITERATIONS ]; do
        # This approach properly captures the count of deleted rows
        DELETED=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
           "WITH deleted AS (
              DELETE FROM price_history
              WHERE ctid IN (
                SELECT ctid
                FROM price_history
                WHERE timestamp < '$CUTOFF_TIME'::timestamp
                LIMIT $BATCH_SIZE
                FOR UPDATE SKIP LOCKED
              )
              RETURNING 1
        )
        SELECT COUNT(*) FROM deleted;" | grep -Eo '[0-9]+')

        # Default to 0 if we get empty output
        DELETED=${DELETED:-0}

        # Break if no more records deleted
        if [ "$DELETED" -eq 0 ]; then
            break
        fi

        TOTAL_DELETED=$((TOTAL_DELETED + DELETED))
        ITERATION=$((ITERATION + 1))
        echo "Deleted batch of $DELETED records (total: $TOTAL_DELETED)"

        sleep 0.5
    done

    if [ $ITERATION -eq $MAX_ITERATIONS ]; then
        echo "WARNING: Hit maximum iterations ($MAX_ITERATIONS)"
    fi

    echo "Cleanup completed. Total records deleted: $TOTAL_DELETED"

    # Verify no remaining records
    REMAINING=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT COUNT(*) FROM price_history WHERE timestamp < '$CUTOFF_TIME'::timestamp")
    echo "Verification: $REMAINING old records remaining"
}

# Execute the cleanup
cleanup_price_history