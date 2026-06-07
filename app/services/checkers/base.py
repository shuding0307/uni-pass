from abc import ABC, abstractmethod

from app.services.checkers.context import ValidationContext


class RuleChecker(ABC):
    @abstractmethod
    def check(self, ctx: ValidationContext) -> None:
        ...
