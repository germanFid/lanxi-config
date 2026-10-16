# For dataclass definitions
from dataclasses import dataclass, field, asdict
from typing import List, Optional

def transition(func):
    """Декоратор для автоматической валидации и выполнения переходов FSM."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        rule = TRANSITIONS.get(func.__name__)
        if not rule:
            return func(self, *args, **kwargs)

        self.sync_state()
        
        # Если мы уже находимся в целевом состоянии (например, повторный open_recorder)
        if self.state == rule["to_state"]:
            return True
            
        # Проверка валидности текущего состояния для этого шага
        if self.state not in rule["from_states"]:
            allowed = [s.value for s in rule["from_states"]]
            self._log(f"FSM Blocked '{func.__name__}': state is '{self.state.value}', but must be one of {allowed}")
            return False

        # Выполняем саму сетевую операцию
        if func(self, *args, **kwargs):
            self.state = rule["to_state"]
            return True
        return False
    return wrapper

# --- OBJECT MODELS ---
@dataclass
class TransducerType:
    model: str = ""
    number: str = "None"
    prefix: str = ""
    variant: str = ""

@dataclass
class TransducerConfig:
    requiresCcld: bool = False
    requires200V: bool = False
    sensitivity: float = 1.0
    serialNumber: int = 0
    type: TransducerType = field(default_factory=TransducerType)
    unit: str = "V"

@dataclass
class ChannelConfig:
    channel: int
    name: str
    enabled: bool = True
    range: str = "10 Vpeak"
    filter: str = "7.0 Hz"
    floating: bool = False
    ccld: bool = False
    destinations: List[str] = field(default_factory=lambda: ["sd"])
    bandwidth: str = "51.2 kHz"
    transducer: Optional[TransducerConfig] = field(default_factory=TransducerConfig)

@dataclass
class ModuleConfig:
    name: str = "test_run"
    fileFormat: str = "wav"
    maxSize: int = 2147483648
    recordingMode: str = "Single"
    channels: List[ChannelConfig] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)
