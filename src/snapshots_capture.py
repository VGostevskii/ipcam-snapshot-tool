import logging
import signal
import time

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from types import FrameType

import yaml
import requests
from requests.auth import HTTPDigestAuth


def load_config(yaml_file: Path) -> dict:
    with yaml_file.open('r') as file:
        return yaml.safe_load(file)


def signal_handler(signum: int, frame: FrameType) -> None:
    global running
    running = False
    logging.info("Signal received. Shutting down gracefully...")


def load_cameras_config(config_file: Path) -> dict[str, dict[str, str]]:
    with config_file.open('r') as file:
        lines = file.readlines()
        cam_configs = {}
        for line in lines:
            if line.strip().startswith('#'):
                continue
            parts = line.strip().split(':', 4)
            cam_name = parts[0]
            login = parts[1]
            password = parts[2]
            auth_type = parts[3]
            url = parts[4]
            cam_configs[cam_name] = {'login': login, 'password': password, 'url': url, 'auth_type': auth_type}

        return cam_configs
        return {line.strip().split(':', 1)[0]: line.strip().split(':', 1)[1] for line in file}


def take_snapshot(cam_name: str, login: str, password: str, auth_type: str, snapshot_url: str) -> None:
    date = datetime.utcnow().strftime('%Y-%m-%d')
    datetime_str = datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')
    dir_path = STORAGE_BASE_FOLDER / cam_name / date
    dir_path.mkdir(parents=True, exist_ok=True)
    save_path = dir_path / f"{cam_name}_{datetime_str}.jpg"

    try:
        if auth_type == 'basic':
            auth = (login, password)
        elif auth_type == 'digest':
            auth = HTTPDigestAuth(login, password)
        else:
            raise ValueError('auth type must be "basic" or "digest"')
        response = requests.get(snapshot_url, timeout=TIMEOUT, auth=auth)
        response.raise_for_status()

        with save_path.open('wb') as file:
            file.write(response.content)

    except requests.HTTPError as e:
        if response.status_code == 401:  # Unauthorized
            logging.error(f"Unauthorized access for {cam_name}. HTTP Status: {response.status_code}. TB: {e}")
        else:
            logging.error(f"Failed to take snapshot for {cam_name}. HTTP Status: {response.status_code}. TB: {e}")

    except requests.RequestException as e:
        logging.error(f"Error capturing snapshot for {cam_name}: {e}")


def sleep_until_next_even_moment(interval: int) -> None:
    now = datetime.utcnow()
    seconds_until_next_moment = interval - now.second
    time.sleep(seconds_until_next_moment)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Camera Snapshot Tool")
    parser.add_argument('config_path', type=Path, help="Path to the YAML configuration file")
    args = parser.parse_args()

    # Configuration
    CONFIG = load_config(args.config_path)
    CAMS_CONFIG_FILE = Path(CONFIG['CONFIG_FILE'])
    STORAGE_BASE_FOLDER = Path(CONFIG['STORAGE_BASE_FOLDER'])
    LOG_FILE = CONFIG['LOG_FILE']
    LOG_LEVEL = getattr(logging, CONFIG['LOG_LEVEL'])
    SNAPSHOT_INTERVAL = CONFIG['SNAPSHOT_INTERVAL']
    TIMEOUT = CONFIG['TIMEOUT']
    if TIMEOUT > SNAPSHOT_INTERVAL:
        raise ValueError('Timeout must be lower then snapshot interval')

    logging.basicConfig(filename=LOG_FILE, level=LOG_LEVEL,
                        format="%(asctime)s - %(process)d-%(thread)d - %(levelname)s: %(message)s")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    CAMERAS_CONFIG = load_cameras_config(CAMS_CONFIG_FILE)

    # Main loop
    logging.info('Start loop...')
    running = True
    while running:
        sleep_until_next_even_moment(SNAPSHOT_INTERVAL)
        start_time = time.time()
        with ThreadPoolExecutor() as executor:
            futures = []
            for cam_name, endpoint_params in CAMERAS_CONFIG.items():
                login = endpoint_params['login']
                password = endpoint_params['password']
                url = endpoint_params['url']
                auth_type = endpoint_params['auth_type']
                futures.append(executor.submit(take_snapshot, cam_name, login, password, auth_type, url))
            for future in futures:
                future.result()  # it takes between 0 and TIMEOUT seconds

            elapsed_time = time.time() - start_time
            if elapsed_time > SNAPSHOT_INTERVAL:
                msg = f'Taking snapshots takes {elapsed_time} \
                    that is more then snapshot interval = {SNAPSHOT_INTERVAL}'
                logging.warning(msg)

    logging.info("Script terminated gracefully.")
