import requests
import json
import time
import os
from enum import Enum
from functools import wraps

from lanxi_datamodel import *

class ModuleState(Enum):
    IDLE = "Idle"
    RECORDER_OPENED = "RecorderOpened"
    RECORDER_CONFIGURING = "RecorderConfiguring"
    RECORDER_STREAMING = "RecorderStreaming"
    RECORDER_RECORDING = "RecorderRecording"
    RECORDER_DOWNLOADING = "RecorderDownloading"
    UNKNOWN = "Unknown"

# Декларативная карта: какой метод из какого исходного состояния в какое целевое переводит прибор
TRANSITIONS = {
    "open_recorder":   {"from_states": [ModuleState.IDLE], "to_state": ModuleState.RECORDER_OPENED},
    "create_session":  {"from_states": [ModuleState.RECORDER_OPENED], "to_state": ModuleState.RECORDER_CONFIGURING},
    "submit_channels": {"from_states": [ModuleState.RECORDER_CONFIGURING], "to_state": ModuleState.RECORDER_STREAMING},
    "start_recording": {"from_states": [ModuleState.RECORDER_STREAMING], "to_state": ModuleState.RECORDER_RECORDING},
    "stop_recording":  {"from_states": [ModuleState.RECORDER_RECORDING], "to_state": ModuleState.RECORDER_STREAMING},
    "finish_session":  {"from_states": [ModuleState.RECORDER_STREAMING, ModuleState.RECORDER_CONFIGURING], "to_state": ModuleState.RECORDER_OPENED},
    "close_recorder":  {"from_states": [ModuleState.RECORDER_OPENED], "to_state": ModuleState.IDLE},
}

class LanXiRecorderClient:
    def __init__(self, ip_address):
        self.ip = ip_address
        self.base_url = f"http://{self.ip}/rest/rec"
        self.headers = {'Content-Type': 'application/json'}
        self.state = ModuleState.UNKNOWN
        self.sync_state()

    def _log(self, message):
        readable_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"{readable_time}: {message}")

    def sync_state(self):
        try:
            response = requests.get(f"{self.base_url}/module/info", timeout=3)
            if response.status_code == 200:
                state_str = response.json().get("moduleState", "Idle")
                self.state = ModuleState(state_str) if state_str in [s.value for s in ModuleState] else ModuleState.UNKNOWN
                return self.state
        except requests.exceptions.RequestException:
            self.state = ModuleState.UNKNOWN
        return self.state

    @transition
    def open_recorder(self):
        self._log("Opening recorder application...")
        res = requests.put(f"{self.base_url}/open", json={"performTransducerDetection": False, "singleModule": True})
        return res.status_code == 200

    @transition
    def create_session(self):
        self._log("Initializing configuration session...")
        res = requests.put(f"{self.base_url}/create")
        return res.status_code == 200

    @transition
    def submit_channels(self, config_dict):
        self._log("Applying JSON configuration to device...")
        res = requests.put(f"{self.base_url}/channels/input", data=json.dumps(config_dict), headers=self.headers)
        if res.status_code == 200:
            self.state = ModuleState.RECORDER_STREAMING
            self._log("Configuration successfully applied. Device state: RecorderStreaming")
            return True
            
        self._log(f"Device rejected config! HTTP Status: {res.status_code}")
        try:
            self._log(f"Device Message: {res.json()}")
        except Exception:
            self._log(f"Device Raw Response: {res.text}")
        return False

    @transition
    def start_recording(self):
        self._log("Starting hardware recording to SD card...")
        res = requests.post(f"{self.base_url}/measurements")
        return res.status_code == 200

    @transition
    def stop_recording(self):
        self._log("Stopping active recording...")
        res = requests.put(f"{self.base_url}/measurements/stop")
        return res.status_code == 200

    @transition
    def finish_session(self):
        self._log("Finishing current recording session...")
        res = requests.put(f"{self.base_url}/finish")
        return res.status_code == 200

    @transition
    def close_recorder(self):
        self._log("Closing recorder application...")
        res = requests.put(f"{self.base_url}/close")
        return res.status_code == 200

    def apply_configuration(self, config_dict):
        self.sync_state()
        if self.state in [ModuleState.RECORDER_STREAMING, ModuleState.RECORDER_RECORDING]:
            self.stop_and_close()
        return self.open_recorder() and self.create_session() and self.submit_channels(config_dict)

    def stop_and_close(self):
        self.sync_state()
        if self.state in [ModuleState.RECORDER_STREAMING, ModuleState.RECORDER_CONFIGURING]:
            self.finish_session()
        if self.state == ModuleState.RECORDER_OPENED:
            self.close_recorder()
        return self.state == ModuleState.IDLE

    def get_stored_recordings(self):
        self._log("Fetching stored configurations from device...")
        try:
            response = requests.get(f"{self.base_url}/measurements")
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException as e:
            self._log(f"Network error: {e}")
        return None

    def save_device_config_to_json(self, file_path="atomic_config.json", recording=None):
        if recording is None:
            recordings = self.get_stored_recordings()
            if not recordings: return False
            recording = recordings[-1]
        atomic_config = recording.get("setup", {})
        if not atomic_config or "channels" not in atomic_config: return False
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(atomic_config, f, indent=4, ensure_ascii=False)
            return True
        except IOError:
            return False

    def load_and_apply_config_from_json(self, file_path):
        if not os.path.exists(file_path): return False
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                config_to_apply = json.load(f)
            if not isinstance(config_to_apply, dict) or "channels" not in config_to_apply: return False
            return self.apply_configuration(config_to_apply)
        except (json.JSONDecodeError, IOError):
            return False

    def force_reset_to_idle(self):
        self._log("Initiating forced hard reset to Idle state...")
        
        try:
            requests.put(f"{self.base_url}/generator/stop", timeout=2)
        except requests.exceptions.RequestException:
            pass

        try:
            requests.put(f"{self.base_url}/measurements/stop", timeout=2)
        except requests.exceptions.RequestException:
            pass
            
        try:
            requests.put(f"{self.base_url}/finish", timeout=2)
        except requests.exceptions.RequestException:
            pass
            
        try:
            requests.put(f"{self.base_url}/cancel", timeout=2)
        except requests.exceptions.RequestException:
            pass

        try:
            res = requests.put(f"{self.base_url}/close", timeout=2)
            if res.status_code == 200:
                self._log("Device successfully forced into Idle state.")
            else:
                self._log(f"Close signal sent, device response status: {res.status_code}")
        except requests.exceptions.RequestException as e:
            self._log(f"Network error during hard reset: {e}")
            
        self.sync_state()
        self._log(f"Current FSM confirmed state: {self.state.value}")
        return self.state == ModuleState.IDLE

    def display_current_state(self):
        """Fetches and displays the current FSM state of the device."""
        self.sync_state()
        self._log(f"Current FSM state: {self.state.value}")
        return self.state

