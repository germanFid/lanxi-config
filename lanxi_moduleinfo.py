from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class HardwareType:
    model: str = ""
    number: str = ""
    prefix: str = ""
    variant: str = ""

@dataclass
class HardwareVersion:
    hardware: str = ""
    firmware: Optional[str] = None

@dataclass
class FrontPanelInfo:
    serial: int = 0
    type: HardwareType = field(default_factory=HardwareType)
    version: HardwareVersion = field(default_factory=HardwareVersion)

@dataclass
class ModuleHardwareInfo:
    serial: int = 0
    type: HardwareType = field(default_factory=HardwareType)
    version: HardwareVersion = field(default_factory=HardwareVersion)

@dataclass
class DeviceInfo:
    license: str = "noLicense"
    moduleState: str = "Idle"
    numberOfInputChannels: int = 0
    numberOfOutputChannels: int = 0
    preampInputSupported: bool = False
    sdCardInserted: bool = False
    supportedBridgeCompletion: List[str] = field(default_factory=list)
    supportedBridgeSupply: List[str] = field(default_factory=list)
    supportedConnectors: List[str] = field(default_factory=list)
    supportedDestinations: List[str] = field(default_factory=list)
    supportedFilters: List[str] = field(default_factory=list)
    supportedHatsChannelPairs: List[List[int]] = field(default_factory=list)
    supportedMaxBridgeCurrent: float = 0.0
    supportedMaxBridgeVoltage: float = 0.0
    supportedOutputRanges: List[str] = field(default_factory=list)
    supportedQuarterCompletionImpedance: List[str] = field(default_factory=list)
    supportedRanges: List[str] = field(default_factory=list)
    supportedRemoteSenseWiring: List[str] = field(default_factory=list)
    supportedSampleRates: List[int] = field(default_factory=list)
    module: ModuleHardwareInfo = field(default_factory=ModuleHardwareInfo)

    @classmethod
    def from_dict(cls, data: dict) -> 'DeviceInfo':
        """Фабричный метод для парсинга сырого JSON ответа устройства."""
        module_data = data.get("module", {})
        fp_data = module_data.get("frontpanel", {})

        # Парсинг структуры фронтпанели
        fp_type = HardwareType(**fp_data.get("type", {}))
        fp_version = HardwareVersion(**fp_data.get("version", {}))
        frontpanel = FrontPanelInfo(serial=fp_data.get("serial", 0), type=fp_type, version=fp_version)

        # Парсинг структуры самого модуля
        mod_type = HardwareType(**module_data.get("type", {}))
        mod_version = HardwareVersion(**module_data.get("version", {}))
        module_info = ModuleHardwareInfo(serial=module_data.get("serial", 0), type=mod_type, version=mod_version)

        # Базовые поля верхнего уровня
        clean_data = {k: v for k, v in data.items() if k not in ['module', 'license']}
        
        return cls(
            license=data.get("license", "noLicense"),
            module=module_info,
            **clean_data
        )
