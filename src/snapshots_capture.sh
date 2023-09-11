#!/bin/bash

# Check if the path to the configuration file is provided as an argument
if [ -z "$1" ]; then
    echo "Please provide the path to the configuration file."
    exit 1
fi

# Source the configuration file to get the required variables
source "$1"
echo "ROOT_FOLDER is: $ROOT_FOLDER"

# Declare an associative array to store camera details
declare -A SNAPSHOT_ENDPOINTS


# Define a lock file for timeout checks
TIMEOUT_LOCK="/tmp/camera_timeout.lock"

# Load camera settings from the text file
# Read the file line by line and extract the IP, login, and password
# Construct a camera name based on the IP (by replacing dots with underscores)
while IFS=: read -r cam_name snapshot_url; do
    echo $snapshot_url
    SNAPSHOT_ENDPOINTS["$cam_name"]="$snapshot_url"
done < $CAMS_CONFIG

for key in "${!SNAPSHOT_ENDPOINTS[@]}"; do
    echo "$key -> ${SNAPSHOT_ENDPOINTS[$key]}"
done

# Function to log errors
log_error() {
    local message="$1"
    # Use a lock to ensure exclusive access to the log file
    (
        flock 200
        # Log the error message with a timestamp
        echo "$(date +"%Y-%m-%d %H:%M:%S") - $message" >> $LOG_FILE
        # Send the error to Zabbix server
        zabbix_sender -z $ZABBIX_SERVER_IP -s "$HOSTNAME" -k camera_snapshot -o "$message"
    ) 200>$TIMEOUT_LOCK
}
export -f log_error

# Function to take a snapshot from a camera
take_snapshot() {
    CAM_NAME=$1
    SNAPSHOT_ENDPOINT=$2
    SAVE_PATH=$3
    # Try to get the snapshot using curl
    # If it fails, log the error
    if ! curl --max-time 10 -o "$SAVE_PATH" "$SNAPSHOT_ENDPOINT"; then
        echo "Failed to take snapshot for $CAM_NAME"
    fi
}
export -f take_snapshot

# Main loop to continuously take snapshots

# Calculate time until the next even interval
current_time=$(date +%s)
sleep_duration=$((SNAPSHOT_INTERVAL - current_time % SNAPSHOT_INTERVAL))

# Sleep until the next even interval
#sleep $sleep_duration

while true; do
    START_TIME=$(date +%s)
    # For each camera, try to take a snapshot
    # If the snapshot process takes more than 15 seconds, check for a timeout
    for CAM_NAME in "${!SNAPSHOT_ENDPOINTS[@]}"; do
        # timeout 15s bash -c "take_snapshot $CAM_NAME"
        SNAPSHOT_ENDPOINT="${SNAPSHOT_ENDPOINTS[$CAM_NAME]}"
        DATE=$(date +"%Y-%m-%d_%H-%M-%S")
        DIR="${ROOT_FOLDER}/${CAM_NAME}/${DATE}"
        mkdir -p "$DIR"
        SNAP_NAME="${CAM_NAME}_${DATE}.jpg"
        SAVE_PATH="${DIR}/${SNAP_NAME}"
        timeout 15s bash -c "take_snapshot $CAM_NAME $SNAPSHOT_ENDPOINT $SAVE_PATH" &
    done  # This runs all the camera snapshot processes concurrently
    wait

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
