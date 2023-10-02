import subprocess
import time
import configparser
import logging
import argparse

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Camera RTSP Recording Service")
parser.add_argument("config_path", help="Path to the configuration file")
args = parser.parse_args()

# Configuration
CONFIG_PATH = args.config_path
config = configparser.ConfigParser()
config.read(CONFIG_PATH)

# Constants from Config
SEGMENT_TIME = config["Settings"]["segment_time"]
LOG_PATH = config["Settings"]["log_path"]

# Setup Logging
logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

processes_and_cmds = []

def start_process(rtsp_url, save_path):
    cmd = f"ffmpeg -hide_banner -y -loglevel error -rtsp_transport tcp -use_wallclock_as_timestamps 1 \
    -i {rtsp_url} \
    -vcodec copy -acodec copy -f segment -reset_timestamps 1 -segment_time {SEGMENT_TIME} -segment_format mkv \
    -segment_atclocktime 1 -strftime 1 \
    {save_path}"
    process = subprocess.Popen(cmd, shell=True)
    return (process, cmd)

# Start all processes
for rtsp_url, save_path in config["CommandParams"].items():
    processes_and_cmds.append(start_process(rtsp_url, save_path))

while True:
    for idx, (process, cmd) in enumerate(processes_and_cmds):
        return_code = process.poll()
        if return_code is not None:  # process has terminated
            logging.error(f"Process for {cmd} terminated with code {return_code}. Restarting...")
            processes_and_cmds[idx] = start_process(rtsp_url, save_path)  # Restart the process
    time.sleep(10)  # Sleep for 10 seconds

