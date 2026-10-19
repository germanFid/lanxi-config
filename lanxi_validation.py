import json

from lanxi_moduleinfo import DeviceInfo

class ValidationError(Exception):
    """Исключение для индикации ошибок валидации."""
    pass

class ValidationRule:
    def validate(self, config: dict, device_info: 'DeviceInfo') -> bool:
        """
        Интерфейсный метод для проверки конфигурации по аппаратным возможностям устройства.
        Должен вызывать ValidationError, если проверка не пройдена.
        """
        raise NotImplementedError("Метод validate должен быть реализован в подклассе.")


class SupportedFeatureRule(ValidationRule):
    def __init__(self, feature_name: str, config_selector):
        self.feature_name = feature_name
        self.config_selector = config_selector

    def validate(self, config: dict, device_info: 'DeviceInfo') -> bool:
        allowed_values = getattr(device_info, self.feature_name, None)
        
        if allowed_values is None:
            raise ValidationError(f"Feature '{self.feature_name}' is not supported or present on this hardware.")
        if len(allowed_values) == 0:
            raise ValidationError(f"Device reports that feature '{self.feature_name}' has no available options.")

        try:
            requested_value = self.config_selector(config)
        except (KeyError, IndexError, TypeError):
            return True

        # --- ИСПРАВЛЕННЫЙ БЛОК: Проверка одиночного значения или списка значений ---
        # Превращаем одиночное значение в список для универсальности итерации
        requested_list = requested_value if isinstance(requested_value, list) else [requested_value]

        for val in requested_list:
            if val not in allowed_values:
                raise ValidationError(
                    f"Hardware limitation breach! Value '{val}' is not supported for '{self.feature_name}'. "
                    f"Supported values by this module: {allowed_values}"
                )
        
        return True


class BridgeExcitationRule(ValidationRule):
    """
    Проверяет бизнес-логику: включен ли bridgeExcOn на модуле без поддержки мостов.
    """
    def validate(self, config: dict, device_info: 'DeviceInfo') -> bool:
        # Проверяем, поддерживает ли прибор коннектор моста
        has_bridge = "Bridge" in device_info.supportedConnectors
        
        for ch in config.get("channels", []):
            if ch.get("enabled", False) and ch.get("bridgeExcOn", False) and not has_bridge:
                raise ValidationError(
                    f"Conflict on Channel {ch.get('channel')}: 'bridgeExcOn' is set to True, "
                    f"but physical module {device_info.module.type.number} does not support Bridge interfaces."
                )
        return True

class ConfigurationValidator:
    def __init__(self):
        # Проверяем все включенные каналы в цикле через универсальные правила
        self._rules = [
            SupportedFeatureRule(
                feature_name="supportedFilters",
                config_selector=lambda cfg: [ch["filter"] for ch in cfg["channels"] if ch["enabled"]]
            ),
            SupportedFeatureRule(
                feature_name="supportedRanges",
                config_selector=lambda cfg: [ch["range"] for ch in cfg["channels"] if ch["enabled"]]
            ),
            BridgeExcitationRule()
        ]

    def run_all(self, config: dict, device_info: DeviceInfo):
        for rule in self._rules:
            rule.validate(config, device_info)