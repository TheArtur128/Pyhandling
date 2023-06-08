from abc import ABC
from operator import not_
from typing import (
    Generic, Any, Iterator, Callable, Iterable, GenericAlias, Optional, Self
)

from pyannotating import Special

from pyhandling.annotations import (
    ActionT, ErrorT, P, Pm, checker_of, A, B, C, V, R, W, D, S
)
from pyhandling.atoming import atomically
from pyhandling.branching import then
from pyhandling.flags import nothing, Flag, pointed
from pyhandling.immutability import property_to
from pyhandling.objects import NotInitializable
from pyhandling.partials import partially, will, rpartial
from pyhandling.signature_assignmenting import call_signature_of
from pyhandling.synonyms import repeating, returned, on
from pyhandling.tools import documenting_by, LeftCallable, action_repr_of


__all__ = (
    "contextual_like",
    "ContextRoot",
    "contextual",
    "contextually",
    "ContextualError",
    "context_oriented",
    "contexted",
    "saving_context",
    "to_context",
    "to_write",
    "to_read",
    "with_context_that",
    "to_metacontextual",
    "is_metacontextual",
    "with_reduced_metacontext",
    "without_metacontext",
)


class contextual_like(NotInitializable):
    """
    Annotation class of objects that can be cast to `ContextRoot`.

    Such objects are iterable objects consisting a main value as first item and
    a context describing the main value as second item.

    Checks using the `isinstance` function.

    The `[]` callback can be used to create an appropriate annotation with a
    description of values in the corresponding places.

    When passing an annotation of only a main value, a context will be of `Any`
    type.
    """

    def __class_getitem__(
        cls,
        value_or_value_and_context: Any | tuple[Any, Any],
    ) -> GenericAlias:
        value_and_context = (
            value_or_value_and_context
            if isinstance(value_or_value_and_context, Iterable)
            else (value_or_value_and_context, Any)
        )

        value, context = value_and_context

        return tuple[value, context]

    @classmethod
    def __instancecheck__(cls, instance: Any) -> bool:
        return isinstance(instance, Iterable) and len(tuple(instance)) == 2


class ContextRoot(ABC, Generic[V, C]):
    """
    Abstract value form class, for holding an additional value, describing the
    main value.

    Comparable by form implementation and stored values.

    Iterable over stored values for unpacking capability, where the first value
    is the main value and the second is the context describing the main value.

    Attributes for stored values are defined in concrete forms.
    """

    _value: V
    _context: C

    def __repr__(self) -> str:
        return f"{self._repr_of(self._value)} when {self._repr_of(self._context)}"

    def __eq__(self, other: Any) -> bool:
        if type(self) is not type(other):
            return False

        value, context = other

        return self._value == value and self._context == context

    def __iter__(self) -> Iterator:
        return iter((self._value, self._context))

    def _repr_of(self, value: Special["contextual"]) -> str:
        return (
            f"({action_repr_of(value)})"
            if (
                type(value) in (contextual, ContextualError)
                and type(self) is type(value)
            )
            else action_repr_of(value)
        )


class _BinaryContextRoot(ContextRoot, Generic[V, C]):
    """`ContextRoot` class with nested creation."""

    def __init__(self, value: V | Self, *contexts: C):
        if len(contexts) > 1:
            value = type(self)(value, *contexts[:-1])

        self._reset(value, nothing if len(contexts) == 0 else contexts[-1])

    def _reset(self, value: V, context: C) -> None:
        self._value = value
        self._context = context


class contextual(_BinaryContextRoot, Generic[V, C]):
    """Basic `ContextRoot` form representing values with no additional effect."""

    value = property_to("_value")
    context = property_to("_context")


class contextually(_BinaryContextRoot, Generic[ActionT, C]):
    """`ContextRoot` form for annotating actions with saving their call."""

    action = property_to("_value")
    context = property_to("_context")

    def __init__(self, action: Callable[Pm, R], *contexts: C):
        super().__init__(action, *contexts)
        self.__signature__ = call_signature_of(self._value)

    def __repr__(self) -> str:
        return f"contextually({super().__repr__()})"

    def __call__(self, *args: Pm.args, **kwargs: Pm.kwargs) -> R:
        return self._value(*args, **kwargs)


class ContextualError(Exception, _BinaryContextRoot, Generic[ErrorT, C]):
    """
    `ContextRoot` form for annotating an error with a context while retaining
    the ability to `raise` the call.
    """

    error = property_to("_value")
    context = property_to("_context")

    def __init__(self, error: ErrorT, *contexts: C):
        _BinaryContextRoot.__init__(self, error, *contexts)
        super().__init__(repr(self))

    def __repr__(self) -> str:
        return f"ContextualError({ContextRoot.__repr__(self)})"


def context_oriented(root_values: contextual_like[V, C]) -> contextual[C, V]:
    """
    Function to replace the main value of a `contextual_like` object with its
    context, and its context with its main value.
    """

    return contextual(*reversed(tuple(root_values)))


def contexted(
    value: V | ContextRoot[V, D],
    when: Optional[C | Callable[D, C]] = None,
) -> ContextRoot[V, D | C]:
    """
    Function to represent an input value in `contextual` form if it is not
    already present.

    Forces a context, when passed, as the result of caaling the forced context
    if it is a callable, or as the forced context itself if not a callable.
    """

    value, context = (
        value if isinstance(value, ContextRoot) else contextual(value)
    )

    if callable(when):
        context = when(context)
    elif when is not None:
        context = when

    return contextual(value, context)


@partially
def saving_context(
    action: Callable[A, B],
    value_and_context: contextual_like[A, C] | A,
) -> contextual[B, C]:
    """
    Function to perform an input action on a `contextual_like` value while
    saving its context.
    """

    value, context = contexted(value_and_context)

    return contextual(action(value), context)


@partially
def to_context(
    action: Callable[A, B],
    value_and_context: contextual_like[V, A],
) -> contextual[V, B]:
    """
    Function to perform an input action on a context of `contextual_like` value
    while saving its value.
    """

    return context_oriented(saving_context(
        action,
        context_oriented(contexted(value_and_context)),
    ))


@partially
def to_write(
    action: Callable[[V, C], R],
    value: contextual_like[V, C],
) -> contextual[V, R]:
    """
    Function to perform an input action on a `contextual_like` context, with
    passing its main value.
    """

    stored_value, context = value

    return contextual(stored_value, action(stored_value, context))


@partially
def to_read(
    action: Callable[[V, C], R],
    value: contextual_like[V, C],
) -> contextual[R, V]:
    """
    Function to perform an input action on a `contextual_like` main value, with
    passing its context.
    """

    return context_oriented(to_write(action, context_oriented(value)))


@partially
def with_context_that(
    that: checker_of[P],
    value: V | ContextRoot[V, P | Flag[P]],
) -> contextual[V, P | nothing]:
    """
    Function for transform `ContextRoot` with context filtered by input
    checker.

    When a context is `Flag`, the resulting context will be filtered by any of
    its values.

    Returns `nothing` if a context is invalid for an input checker`.
    """

    return pointed(contexted(value).context).that(that).point


def to_metacontextual(
    value_action: Callable[V, W] = returned,
    context_action: Callable[C, D] = returned,
    /,
    *,
    summed: Callable[contextual[W, D] | S, S] = returned,
) -> LeftCallable[contextual_like[V, C] | V, S]:
    """
    Reduce function for values of nested `ContextRoots`.

    Calculates from `value_action` and `context_action` corresponding leaf
    values.

    Calculates a form with calculated values by `summed`.
    """

    value_action, context_action = tuple(map(
        will(on)(
            rpartial(isinstance, ContextRoot) |then>> not_,
            else_=lambda v: to_metacontextual(
                value_action,
                context_action,
                summed=summed,
            )(v),
        ),
        (value_action, context_action),
    ))

    return atomically(
        contexted
        |then>> saving_context(value_action)
        |then>> to_context(context_action)
        |then>> summed
    )


def is_metacontextual(value: Special[ContextRoot[ContextRoot, Any], Any]) -> bool:
    """
    Function to check `ContextRoot`'s' describing another `ContextRoot` if it is
    at all `ContextRoot`.
    """

    return isinstance(value, ContextRoot) and isinstance(value.value, ContextRoot)


def with_reduced_metacontext(
    value: ContextRoot[ContextRoot[V, Any], Any]
) -> contextual[V, Flag]:
    """
    Function to remove nesting of two `ContextRoot`s.
    The resulting context is a flag sum from the top and bottom `ContextRoot`.
    """

    meta_root = contextual(*value)
    root = meta_root.value

    return contexted(root, +pointed(meta_root.context))


without_metacontext: Callable[[ContextRoot], contextual]
without_metacontext = documenting_by(
    """
    Function to fully glue nested `ContextRoot`s.
    The resulting context is a flag sum from all nested `ContextRoot`s.
    """
)(
    repeating(with_reduced_metacontext, while_=is_metacontextual)
)