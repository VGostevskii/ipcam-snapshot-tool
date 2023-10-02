# IPCam Snapshot Tool

A robust tool designed to capture snapshots from multiple IP cameras at regular intervals and log any issues to a Zabbix server.
Once you've set up the IPCam Snapshot Tool, it will start capturing snapshots from the specified IP cameras. 

The tool is designed to take the first snapshot at an even interval, such as on the hour, half-past the hour, etc., depending on the `SNAPSHOT_INTERVAL` set in the configuration. Subsequent snapshots will be taken at intervals of `SNAPSHOT_INTERVAL`.

For example, if you start the tool at 14:53 and the `SNAPSHOT_INTERVAL` is set to 10 minutes, the first snapshot will be taken at 15:00, then at 15:10, 15:20, and so on.

## Prerequisites

- A system with `bash`, `curl`, and `flock` installed.
- Zabbix active agent for logging issues.
- `zabbix_sender` tool installed for sending logs to the Zabbix server.

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/VGostevskii/ipcam-snapshot-tool.git
cd ipcam-snapshot-tool
```

### 2. Configuration
- Copy the `config_template.txt` to `config.txt`:

```bash
cp config/config_template.txt config/config.txt
```

- Edit `config/config.txt` with the appropriate values for your setup, such as the camera IPs, logins, passwords, and Zabbix server details.

### 3. Systemd Service Configuration

If you're planning to run the IPCam Snapshot Tool as a systemd service, you'll need to make a few adjustments to the provided service file template.

#### Adjusting the `ipcam-snapshot.service` file:

1. **Path to the Script and Configuration**:
   In the `ExecStart` directive, replace `/path/to/ipcam-snapshot-tool/` with the actual path where you've cloned or placed the repository.

   ```
   ExecStart=/path/to/ipcam-snapshot-tool/src/snapshots_capture.sh /path/to/ipcam-snapshot-tool/config/config.txt
   ```

2. **User and Group**:
   Replace `your_username` with the username under which you want the service to run. Similarly, replace `your_groupname` with the group name under which you want the service to run.

   ```
   User=your_username
   Group=your_groupname
   ```

After making these changes, you can proceed with the instructions to copy the service file to the appropriate directory and start the service:

```bash
sudo cp dist/ipcam-snapshot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ipcam-snapshot
sudo systemctl start ipcam-snapshot
```

### 4. Logging

Errors will be logged to the path specified in `config.txt`. Ensure the directory has the appropriate permissions for the script to write to the log file.

### 5. Zabbix Configuration

- On your Zabbix server, create an item with the key `camera_snapshot` for the host specified in `config.txt`.
- Set up triggers or actions based on the received data if needed.

## Troubleshooting

- Ensure the script has permissions to read the configuration file and camera settings file.
- Ensure the script has write permissions to the log file and the directory where snapshots are saved.
- Check the log file for any errors or issues.
- If using Zabbix, ensure the Zabbix agent and `zabbix_sender` are correctly configured.

## TODO List

- [ ] Do naming improvments
- [ ] Remove bash and zabbix (as there are python with logging and zabbix log parser independet)
- [ ] Clear README.md

## Contributing

If you find any issues or have suggestions for improvements, please open an issue or submit a pull request.
