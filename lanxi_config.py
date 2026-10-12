import requests
import json
import time
import os

class LanXiRecorderClient:
    def __init__(self, ip_address):
        self.ip = ip_address
        self.base_url = f"http://{self.ip}/rest/rec"
        self.headers = {'Content-Type': 'application/json'}

    def _log(self, message):
        print(f"{int(time.time())}: {message}")

    def get_stored_recordings(self):
        self._log("Fetching stored configurations from device...")
        try:
            response = requests.get(f"{self.base_url}/measurements")
            if response.status_code == 200:
                recordings = response.json()
                self._log(f"Found {len(recordings)} stored configurations.")
                return recordings
            self._log(f"Failed to fetch stored configurations. Status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            self._log(f"Network error: {e}")
        return None

    def save_device_config_to_json(self, file_path="atomic_config.json", recording=None):
        if recording is None:
            recordings = self.get_stored_recordings()
            if not recordings:
                self._log("No configurations available to save.")
                return False
            recording = recordings[-1]
        
        atomic_config = recording.get("setup", {})
        
        if not atomic_config or "channels" not in atomic_config:
            self._log("Latest recording does not contain a valid channel setup configuration.")
            return False
            
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(atomic_config, f, indent=4, ensure_ascii=False)
            self._log(f"Successfully saved latest atomic configuration to: {file_path}")
            return True
        except IOError as e:
            self._log(f"File write error: {e}")
            return False

    def load_and_apply_config_from_json(self, file_path):
        if not os.path.exists(file_path):
            self._log(f"Configuration file not found: {file_path}")
            return False
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                config_to_apply = json.load(f)
            
            # Проверяем, что это атомарный объект конфигурации, а не массив
            if not isinstance(config_to_apply, dict) or "channels" not in config_to_apply:
                self._log("Invalid atomic configuration format in JSON file.")
                return False

            self._log(f"Loaded atomic configuration '{config_to_apply.get('name')}' from file.")
            return self.apply_configuration(config_to_apply)
            
        except json.JSONDecodeError as e:
            self._log(f"Failed to parse JSON file: {e}")
            return False
        except IOError as e:
            self._log(f"File read error: {e}")
            return False

    def apply_configuration(self, config_dict):
        self._log("Opening recorder application...")
        res_open = requests.put(f"{self.base_url}/open", json={"performTransducerDetection": False, "singleModule": True})
        if res_open.status_code != 200:
            self._log(f"Recorder open warning. Status code: {res_open.status_code}")

        self._log("Initializing configuration session...")
        res_create = requests.put(f"{self.base_url}/create")
        if res_create.status_code != 200:
            self._log(f"Failed to initialize session. Status code: {res_create.status_code}")
            return False

        self._log("Applying JSON configuration to device...")
        res_config = requests.put(f"{self.base_url}/channels/input", data=json.dumps(config_dict), headers=self.headers)
        if res_config.status_code == 200:
            self._log("Configuration successfully applied. Device state: RecorderStreaming")
            return True
            
        self._log(f"Failed to apply configuration. Status code: {res_config.status_code}")
        self._log(f"Device response: {res_config.text}")
        return False

    def stop_and_close(self):
        self._log("Stopping recording and closing recorder session...")
        requests.put(f"{self.base_url}/measurements/stop")
        
        res_finish = requests.put(f"{self.base_url}/finish")
        if res_finish.status_code == 200:
            self._log("Recording session finished. State: RecorderOpened")
        else:
            self._log(f"Failed to finish session. Status code: {res_finish.status_code}")

        res_close = requests.put(f"{self.base_url}/close")
        if res_close.status_code == 200:
            self._log("Recorder application closed. Device state: Idle")
            return True
            
        self._log(f"Failed to close recorder. Status code: {res_close.status_code}")
        return False
