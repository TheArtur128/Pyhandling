from abc import abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from functools import wraps, cached_property, partial
from types import MappingProxyType
from typing import Callable, Self, Type, Any, runtime_checkable, Protocol, Generic, Final, Iterable, Optional, Tuple, _UnionGenericAlias, Union

from pyannotating import method_of, Special

from pyhandling.annotations import event_for, ObjectT, ValueT, KeyT, ResultT, ContextT, atomic_action, dirty, reformer_of


__all__ = (
    "to_clone", "publicly_immutable", "ItemGetter", "ItemSetter", "ItemKeeper",
    "ContextManager", "Flag", "nothing", "ArgumentKey", "ArgumentPack",
    "DelegatingProperty", "Clock", "as_argument_pack", "with_opened_items",
    "in_collection", "documenting_by"
)


def to_clone(method: method_of[ObjectT]) -> Callable[[ObjectT, ...], ObjectT]:
    """
    Decorator function to spawn new objects by cloning and applying an input
    method to them.
    """

    @wraps(method)
    def wrapper(instance: object, *args, **kwargs) -> object:
        clone = deepcopy(instance)
        method(clone, *args, **kwargs)

        return clone

    wrapper.__annotations__["return"] = Self

    return wrapper


def publicly_immutable(class_: Type[ValueT]) -> Type[ValueT]:
    """Decorator for an input class that forbids it change its public fields."""

    old_setattr = class_.__setattr__

    @wraps(old_setattr)
    def new_setattr(instance: object, attribute_name: str, attribute_value: Any) -> Any:
        if attribute_name and attribute_name[0] != '_':
            raise AttributeError(
                f"cannot set '{attribute_name}' attribute of publicly immutable type '{class_}'"
            )

        return old_setattr(instance, attribute_name, attribute_value)

    class_.__setattr__ = new_setattr

    return class_


@runtime_checkable
class ItemGetter(Protocol, Generic[KeyT, ResultT]):
    """
    Protocol describing objects from which it is possible to get a value by
    accessing via `[]` (`item_getter[key]`).
    """

    @abstractmethod
    def __getitem__(self, key: KeyT) -> ResultT:
        ...


@runtime_checkable
class ItemSetter(Protocol, Generic[KeyT, ValueT]):
    """
    Protocol describing objects from which it is possible to set a value by
    accessing via `[]` (`item_setter[key] = value`).
    """

    @abstractmethod
    def __setitem__(self, key: KeyT, value: ValueT) -> Any:
        ...


@runtime_checkable
class ItemKeeper(Protocol, Generic[KeyT, ValueT]):
    """
    Protocol describing objects from which it is possible to get the value via
    `[]` access and write the value via the same `[]` access.

    In the form
    ```
    item_keeper[key]
    item_keeper[key] = value
    ```
    """

    @abstractmethod
    def __getitem__(self, key: KeyT) -> ResultT:
        ...

    @abstractmethod
    def __setitem__(self, key: KeyT, value: ValueT) -> Any:
        ...


@runtime_checkable
class ContextManager(Protocol, Generic[ContextT]):
    """
    Protocol describing objects managing a context via the syntactic
    `with ... as ...` construct.
    """

    @abstractmethod
    def __enter__(self) -> ContextT:
        ...

    @abstractmethod
    def __exit__(
        self,
        error_type: Optional[Type[Exception]],
        error: Optional[Exception],
        traceback: Any
    ):
        ...


@runtime_checkable
class Variable(Protocol):
    """
    Protocol describing objects capable of checking another object against a
    subvariant of the describing object (`isinstance(another, describing)`).
    """

    @abstractmethod
    def __instancecheck__(self, instance: object) -> bool:
        ...


class Flag:
    """Class for creating generic flags without using enum."""

    def __init__(self, name: str, *, is_positive: bool = True):
        self._name = name
        self._is_positive = is_positive

    def __repr__(self) -> str:
        return f"<{'positive' if self._is_positive else 'negative'} {type(self).__name__} \"{self._name}\">"

    def __hash__(self) -> int:
        return hash(self._name)

    def __bool__(self) -> bool:
        return self._is_positive

    def __eq__(self, other: Special[Self]) -> bool:
        return isinstance(other, Flag) and self._name == other._name

    def __instancecheck__(self, instance: Any) -> bool:
        return self == instance

    def __or__(self, other: ValueT) -> _UnionGenericAlias:
        return Union[self, other]

    def __ror__(self, other: ValueT) -> _UnionGenericAlias:
        return Union[other, self]

    @property
    def name(self) -> str:
        return self._name


nothing: Final[Flag] = Flag("nothing", is_positive=False)
nothing.__doc__ = """Flag to indicate the absence of anything, including `None`."""


@dataclass(frozen=True)
class ArgumentKey(Generic[KeyT, ValueT]):
    """Data class for structuring getting value from `ArgumentPack` via `[]`."""

    key: KeyT
    is_keyword: bool = field(default=False, kw_only=True)
    default: ValueT = field(default_factory=lambda: nothing, compare=False, kw_only=True)


class ArgumentPack:
    """
    Data class for structuring the storage of any arguments.

    Has the ability to get an attribute when passed to `[]` `ArgumentKey`
    instance.
    """

    def __init__(self, args: Iterable = tuple(), kwargs: Optional[dict] = None):
        self._args = tuple(args)
        self._kwargs = MappingProxyType(kwargs if kwargs is not None else dict())

    @property
    def args(self) -> Tuple:
        return self._args

    @property
    def kwargs(self) -> MappingProxyType:
        return self._kwargs

    @cached_property
    def keys(self) -> Tuple[ArgumentKey]:
        return (
            *map(ArgumentKey, range(len(self.args))),
            *map(partial(ArgumentKey, is_keyword=True), self.kwargs.keys())
        )

    def __repr__(self) -> str:
        return "{class_name}({formatted_args}{argument_separation_part}{formatted_kwargs})".format(
            class_name=self.__class__.__name__,
            formatted_args=', '.join(map(str, self.args)),
            argument_separation_part=', ' if self.args and self.kwargs else str(),
            formatted_kwargs=', '.join(map(lambda item: f"{item[0]}={item[1]}", self.kwargs.items()))
        )

    def __eq__(self, other: Self) -> bool:
        return self.args == other.args and self.kwargs == other.kwargs

    def __getitem__(self, argument: ArgumentKey) -> Any:
        return (
            (self.kwargs if argument.is_keyword else self.args)[argument.key]
            if argument in self or argument.default is nothing
            else argument.default
        )

    def __or__(self, other: Self) -> Self:
        return self.merge_with(other)

    def __contains__(self, argument: ArgumentKey) -> bool:
        return argument in self.keys

    def expand_with(self, *args, **kwargs) -> Self:
        """Method to create another pack with input arguments."""

        return self.__class__(
            (*self.args, *args),
            self.kwargs | kwargs
        )

    def merge_with(self, argument_pack: Self) -> Self:
        """Method to create another pack by merging with an input argument pack."""

        return self.__class__(
            (*self.args, *argument_pack.args),
            self.kwargs | argument_pack.kwargs
        )

    def only_with(self, *argument_keys: ArgumentKey) -> Self:
        """Method for cloning with values obtained from input keys."""

        keyword_argument_keys = set(filter(lambda argument_key: argument_key.is_keyword, argument_keys))

        return self.__class__(
            tuple(self[argument_key] for argument_key in set(argument_keys) - keyword_argument_keys),
            {keyword_argument_key.key: self[keyword_argument_key] for keyword_argument_key in keyword_argument_keys}
        )

    def without(self, *argument_keys: ArgumentKey) -> Self:
        """
        Method for cloning a pack excluding arguments whose keys are input to
        this method.
        """
        
        return self.only_with(*(set(self.keys) - set(argument_keys)))

    def call(self, caller: Callable) -> Any:
        """
        Method for calling an input function with arguments stored in an
        instance.
        """

        return caller(*self.args, **self.kwargs)

    @classmethod
    def of(cls, *args, **kwargs) -> Self:
        """Method for creating a pack with this method's input arguments."""

        return cls(args, kwargs)


class DelegatingProperty:
    """
    Descriptor class that takes data from an attribute that already exists on an
    object.

    Has the ability to set a delegating attribute (Does not set by default).
    """

    def __init__(
        self,
        delegated_attribute_name: str,
        *,
        settable: bool = False,
        getting_converter: atomic_action = lambda value: value,
        setting_converter: atomic_action = lambda value: value
    ):
        self.delegated_attribute_name = delegated_attribute_name
        self.settable = settable
        self.getting_converter = getting_converter
        self.setting_converter = setting_converter

    def __get__(self, instance: object, owner: type) -> Any:
        return self.getting_converter(getattr(instance, self.delegated_attribute_name))

    def __set__(self, instance: object, value: Any) -> None:
        if not self.settable:
            raise AttributeError(
                "delegating property of '{attribute_name}' for '{class_name}' object is not settable".format(
                    attribute_name=self.delegated_attribute_name,
                    class_name=type(instance).__name__
                )
            )

        setattr(instance, self.delegated_attribute_name, self.setting_converter(value))


class Clock:
    """
    Atomic class for saving state.

    Has a number of ticks that determines its state.
    When ticks expire, it becomes `False` and may leave negative ticks.

    Keeps the original input ticks.
    """

    initial_ticks_to_disability = DelegatingProperty("_initial_ticks_to_disability")

    def __init__(self, ticks_to_disability: int):
        self.ticks_to_disability = self._initial_ticks_to_disability = ticks_to_disability

    def __repr__(self) -> str:
        return f"{'in' if not self else str()}valid {self.__class__.__name__}({self.ticks_to_disability})"

    def __bool__(self) -> bool:
        return self.ticks_to_disability > 0


def as_argument_pack(*args, **kwargs) -> ArgumentPack:
    """
    Function to optionally convert input arguments into `ArgumentPack` with
    that input arguments.

    When passed a single positional `ArgumentPack` to the function, it returns
    it.
    """

    if len(args) == 1 and isinstance(args[0], ArgumentPack) and not kwargs:
        return args[0]

    return ArgumentPack(args, kwargs)


def with_opened_items(collection: Iterable) -> Tuple:
    """Function to expand input collection's subcollections to it."""

    collection_with_opened_items = list()

    for item in collection:
        if not isinstance(item, Iterable):
            collection_with_opened_items.append(item)
            continue

        collection_with_opened_items.extend(item)

    return tuple(collection_with_opened_items)


def in_collection(value: ValueT) -> tuple[ValueT]:
    """Function to represent the input value as a single collection."""

    return (value, )


def documenting_by(documentation: str) -> dirty[reformer_of[ObjectT]]:
    """
    Function of getting other function that getting value with the input 
    documentation from this first function.
    """

    def document(object_: ObjectT) -> ObjectT:
        """
        Function created with `documenting_by` function that sets the __doc__
        attribute and returns the input object.
        """

        object_.__doc__ = documentation
        return object_

    return document
