#!/bin/bash

# Check if the path to the configuration file is provided as an argument
if [ -z "$1" ]; then
    echo "Please provide the path to the configuration file."
    exit 1
fi

# Source the configuration file to get the required variables
source "$1"

# Declare an associative array to store camera details
declare -A CAMS

# Define a lock file for timeout checks
TIMEOUT_LOCK="/tmp/camera_timeout.lock"

# Load camera settings from the text file
# Read the file line by line and extract the IP, login, and password
# Construct a camera name based on the IP (by replacing dots with underscores)
while IFS=: read -r cam_name ip login password; do
    # CAM_NAME=$"cam_${ip//./_}"
    CAM_NAME=$cam_name
    CAMS["$CAM_NAME"]="$ip:$login:$password"
done < $CAM_SETTINGS

# Function to log errors
log_error() {
    local message="$1"
    # Use a lock to ensure exclusive access to the log file
    (
        flock 200
        # Log the error message with a timestamp
        echo "$(date +"%Y-%m-%d %H:%M:%S") - $message" >> $LOG_FILE
        # Send the error to Zabbix server
        zabbix_sender -z $ZABBIX_SERVER_IP -s "$YOUR_HOSTNAME" -k camera_snapshot -o "$message"
    ) 200>$TIMEOUT_LOCK
}

# Function to take a snapshot from a camera
take_snapshot() {
    CAM_NAME=$1
    IP=$(echo "${CAMS[$CAM_NAME]}" | cut -d':' -f1)
    LOGIN=$(echo "${CAMS[$CAM_NAME]}" | cut -d':' -f2)
    PASSWORD=$(echo "${CAMS[$CAM_NAME]}" | cut -d':' -f3)

    DATE=$(date +"%Y-%m-%d_%H-%M-%S")
    DIR="${ROOT_FOLDER}/${CAM_NAME}/${DATE}"
    SNAP_NAME="${CAM_NAME}_${DATE}.jpg"

    mkdir -p "$DIR"
    # Try to get the snapshot using curl
    # If it fails, log the error
    if ! curl --max-time 10 -o "${DIR}/${SNAP_NAME}" "http://${LOGIN}:${PASSWORD}@${IP}:80/GetSnapshot/0"; then
        log_error "Failed to take snapshot for $CAM_NAME"
    fi
}

# Main loop to continuously take snapshots

# Calculate time until the next even interval
current_time=$(date +%s)
sleep_duration=$((SNAPSHOT_INTERVAL - current_time % SNAPSHOT_INTERVAL))

# Sleep until the next even interval
sleep $sleep_duration

while true; do
    START_TIME=$(date +%s)

    # For each camera, try to take a snapshot
    # If the snapshot process takes more than 15 seconds, check for a timeout
    for CAM_NAME in "${!CAMS[@]}"; do
        timeout 15s bash -c "take_snapshot $CAM_NAME"
        
        # Check the exit status of timeout
        if [ $? -eq 124 ]; then
            # Check if the log_error lock is held
            if ! flock -n 300; then
                log_error "Timeout reached for $CAM_NAME"
            fi
        fi
    done &  # This runs all the camera snapshot processes concurrently

    # Calculate the elapsed time and determine how long to sleep before the next iteration
    END_TIME=$(date +%s)
    ELAPSED_TIME=$((END_TIME - START_TIME))
    SLEEP_TIME=$(($SNAPSHOT_INTERVAL - ELAPSED_TIME))

    # Ensure the sleep time is not negative
    if [ $SLEEP_TIME -lt 0 ]; then
        SLEEP_TIME=0
    fi

    sleep $SLEEP_TIME
done 300>$TIMEOUT_LOCK
