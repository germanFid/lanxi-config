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
        """
        feature_name: Имя поля из класса DeviceInfo (например, 'supportedFilters', 'supportedRanges').
        config_selector: Функция/лямбда, извлекающая проверяемое значение из JSON конфигурации.
        """
        self.feature_name = feature_name
        self.config_selector = config_selector

    def validate(self, config: dict, device_info: 'DeviceInfo') -> bool:
        # 1. Извлекаем список поддерживаемых фич из строго типизированного DeviceInfo
        allowed_values = getattr(device_info, self.feature_name, None)
        
        if allowed_values is None:
            raise ValidationError(f"Feature '{self.feature_name}' is not supported or present on this hardware.")
            
        if not isinstance(allowed_values, list):
            raise ValidationError(f"Feature '{self.feature_name}' on device is not a valid list collection.")
            
        if len(allowed_values) == 0:
            raise ValidationError(f"Device reports that feature '{self.feature_name}' has no available options.")

        # 2. Извлекаем значение, которое пользователь пытается применить в конфигурации
        try:
            requested_value = self.config_selector(config)
        except (KeyError, IndexError, TypeError):
            # Если параметра нет в JSON, значит пользователь его не настраивает (например, канал выключен)
            return True

        # 3. Валидируем запрошенное значение против аппаратного списка прибора
        if requested_value not in allowed_values:
            raise ValidationError(
                f"Hardware limitation breach! Value '{requested_value}' is not supported for '{self.feature_name}'. "
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
        # Настраиваем правила, передавая лямбду для поиска нужного параметра внутри Канала 1
        self._rules: list[ValidationRule] = [
            SupportedFeatureRule(
                feature_name="supportedFilters",
                config_selector=lambda cfg: cfg["channels"][0]["filter"]
            ),
            SupportedFeatureRule(
                feature_name="supportedRanges",
                config_selector=lambda cfg: cfg["channels"][0]["range"]
            ),
            SupportedFeatureRule(
                feature_name="supportedDestinations",
                config_selector=lambda cfg: cfg["channels"][0]["destinations"][0]
            ),
            SupportedFeatureRule(
                feature_name="supportedSampleRates",
                # Пример селектора, если бы мы передавали rate напрямую в герцах
                config_selector=lambda cfg: cfg.get("sampleRate") 
            ),
            # Подключаем наше специализированное правило для мостов
            BridgeExcitationRule()
        ]

    def run_all(self, config: dict, device_info: 'DeviceInfo'):
        """Последовательно запускает всю цепочку проверок. Любой raise прервет валидацию."""
        for rule in self._rules:
            rule.validate(config, device_info)
