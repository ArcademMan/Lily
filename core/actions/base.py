from abc import ABC, abstractmethod


class Action(ABC):
    @abstractmethod
    def execute(self, intent: dict, config) -> str:
        pass
