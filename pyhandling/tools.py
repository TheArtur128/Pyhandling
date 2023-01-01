from copy import copy
from dataclasses import dataclass, field
from functools import wraps
from math import inf
from typing import Iterable, Self, Callable


def to_clone(method: Callable[[object, ...], None]) -> Callable[[...], object]:
    """
    Decorator function to spawn new objects by cloning and applying an input
    method to them.
    """

    @wraps(method)
    def wrapper(instance: object, *args, **kwargs) -> object:
        clone = copy(instance)
        method(clone, *args, **kwargs)

        return clone

    return wrapper


@dataclass(frozen=True)
class ArgumentPack:
    args: Iterable = tuple()
    kwargs: dict = field(default_factory=dict)

    @to_clone
    def expand_with(self, *args, **kwargs) -> Self:
        self.args = (*self.args, *args)
        self.kwargs = self.kwargs | kwargs

    @to_clone
    def merge_with(self, argument_pack: Self) -> Self:
        self.args = (*self.args, *argument_pack.args)
        self.kwargs = self.kwargs | argument_pack.kwargs

    def call(self, caller: Callable) -> any:
        return caller(*self.args, **self.kwargs)

    @classmethod
    def create_via_call(cls, *args, **kwargs) -> Self:
        return cls(args, kwargs)


class DelegatingProperty:
    def __init__(
        self,
        delegated_attribute_name: str,
        *,
        settable: bool = False,
        value_converter: Callable[[any], any] = lambda resource: resource
    ):
        self.delegated_attribute_name = delegated_attribute_name
        self.settable = settable
        self.value_converter = value_converter

    def __get__(self, instance: object, owner: type) -> any:
        return getattr(instance, self.delegated_attribute_name)

    def __set__(self, instance: object, value: any) -> None:
        if not self.settable:
            raise AttributeError(
                "delegating property of '{attribute_name}' for '{class_name}' object is not settable".format(
                    attribute_name=self.delegated_attribute_name,
                    class_name=type(instance).__name__
                )
            )

        setattr(instance, self.delegated_attribute_name, self.value_converter(value))


class Clock:
    ticks_to_disability = DelegatingProperty('_ticks_to_disability')

    def __init__(self, ticks_to_disability: int):
        self._ticks_to_disability = ticks_to_disability

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.ticks_to_disability})"

    def __bool__(self) -> bool:
        return self._ticks_to_disability > 0

    def tick(self) -> None:
        self._ticks_to_disability -= 1