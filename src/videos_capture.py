import argparse
import json
import logging
import re
import signal
import subprocess
import time
import os

from types import FrameType


child_processes = []


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Camera RTSP Recording Service")
    parser.add_argument("config_path", help="Path to the configuration file")
    args = parser.parse_args()
    return args


def read_json_config(config_path: os.PathLike) -> dict:
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)
    return config


def setup_logging(log_path: os.PathLike) -> None:
    logging.basicConfig(filename=log_path, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')


def signal_handler(signum: int, frame: FrameType) -> None:
    global running
    running = False
    logging.info("Signal received. Shutting down gracefully...")

    # Terminate all child processes
    for process in child_processes:
        try:
            process.terminate()  # Send SIGTERM to each child process
        except Exception as e:
            logging.error(f"Error while terminating child process: {str(e)}")

    # Wait for all child processes to terminate with a total timeout of 10 seconds
    try:
        for process in child_processes:
            process.wait(timeout=30 / len(child_processes))
    except subprocess.TimeoutExpired:
        logging.error("Timeout while waiting for child processes to terminate")

    # Optionally, check if any processes are still alive and handle them accordingly
    for process in child_processes:
        if process.poll() is None:
            logging.error("Child process did not terminate within the timeout. Handling it...")
            # Handle the process as needed, e.g., forcefully terminate it or perform other actions


def hide_url(text: str, replace_with: str = '[HIDED_URL] ') -> str:
    protocol_pattern = r'(rtsp://|http://|https://|tcp://|udp://|ftp://)(\S*?)(\s|$)'
    redacted = re.sub(protocol_pattern, rf'\1{replace_with}', text)
    return redacted


def start_process(rtsp_url: str, save_path: str, segment_time: int) -> subprocess.Popen:
    # TODO pass stimeout as variable
    cmd = (
        f"ffmpeg -hide_banner -y -loglevel error -rtsp_transport tcp "
        f"-stimeout 10000000 "
        f"-use_wallclock_as_timestamps 1 -i {rtsp_url} -vcodec copy "
        f"-acodec copy -f segment -reset_timestamps 1 -segment_time {segment_time} "
        f"-segment_format mkv -segment_atclocktime 1 -strftime 1 {save_path}"
    )
    process = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE)
    return process


if __name__ == '__main__':
    args = parse_arguments()
    config = read_json_config(args.config_path)

    LOG_PATH = config["Settings"].get("log_path")
    setup_logging(LOG_PATH)
    SEGMENT_TIME = int(config["Settings"].get("segment_time"))
    SLEEP_TIME = int(config["Settings"].get("sleep_time"))

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Init rtsp stream capturing processes for each IP cam
    processes = []

    unique_paths = set()
    for cam_capture_config in config["CamsConfig"]:
        cam_name = cam_capture_config['cam_name']
        rtsp_url = cam_capture_config['rtsp_url']
        save_path = cam_capture_config['save_path']

        # Veirfy if there are no duplication
        if save_path not in unique_paths:
            unique_paths.add(save_path)
        else:
            logging.error("Duplicated save_path for {cam_name}. Check config. Skipping...")
            continue

        process = start_process(rtsp_url, save_path, SEGMENT_TIME)
        processes.append((process, cam_name, rtsp_url, save_path))

    # For each process check if it has been terminated
    # log errors and restart
    running = True
    while running:
        for idx, (process, cam_name, rtsp_url, save_path) in enumerate(processes):
            return_code = process.poll()
            if return_code is not None:  # process has terminated
                stderr_output = process.stderr.read().decode('utf-8')
                if return_code != 0:
                    stderr_output = stderr_output.replace(rtsp_url, 'HIDED_URL')
                    stderr_output = hide_url(stderr_output)
                    logging.error((f"Process for {cam_name} terminated with code {return_code}."
                                   f"FFmpeg Error Output:\n{stderr_output}"))
                else:
                    logging.info(f"Process for {cam_name} has terminated gracefully.")
                process = start_process(rtsp_url, save_path, SEGMENT_TIME)  # Restart the process
                processes[idx] = (process, cam_name, rtsp_url, save_path)
        time.sleep(SLEEP_TIME)

    logging.info("Script terminated gracefully.")
