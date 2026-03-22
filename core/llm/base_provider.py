from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def chat(self, model: str, messages: list[dict], format_json: bool = False,
             temperature: float = 0.0, num_predict: int = 128, timeout: int = 60) -> str:
        pass

    @abstractmethod
    def check(self) -> bool:
        pass

    @abstractmethod
    def get_models(self) -> list[str]:
        pass
