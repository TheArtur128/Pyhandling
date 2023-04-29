from operator import attrgetter, call
from typing import Callable, Any, Tuple, Optional

from pyannotating import many_or_one, Special

from pyhandling.annotations import (
    dirty, V, C, R,
    checker_of, event_for, A, B, V, FlagT, C
)
from pyhandling.branching import (
    discretely, ActionChain, binding_by, branching, then
)
from pyhandling.contexting import (
    contextual, contextually, contexted, ContextRoot, saving_context
)
from pyhandling.data_flow import returnly, eventually, by, to
from pyhandling.flags import flag, nothing, Flag, pointed
from pyhandling.partials import will, partially
from pyhandling.structure_management import tmap
from pyhandling.synonyms import raise_
from pyhandling.tools import documenting_by, to_check


__all__ = (
    "bad",
    "maybe",
    "until_error",
    "showly",
    "right",
    "left",
    "either",
    "future",
    "in_future",
    "future_from",
)


bad = flag('bad', sign=False)


@documenting_by(
    """
    Execution context that stops a thread of execution when a value is None
    or returned in the `bad` context.
    """
)
@discretely
@will
def maybe(
    action: Callable[[A], B],
    value: contextual[Optional[V], Special[bad, FlagT]],
) -> contextual[B | Optional[V], Special[bad, FlagT]]:
    stored_value, context = value

    return (
        value
        if stored_value is None or context == bad
        else saving_context(action, value)
    )


@documenting_by(
    """
    Execution context that stops the thread of execution when an error occurs.

    When skipping, it saves the last validly calculated value and a pointed
    occurred error as context.
    """
)
@discretely
@will
def until_error(
    action: Callable[[A], B],
    value: A | ContextRoot[A, Special[Exception | Flag[Exception] | C]],
) -> contextual[A | B, Flag[Exception] | C]:
    value = contexted(value)

    if pointed(value.context).that(isinstance |by| Exception) != nothing:
        return value

    try:
        return saving_context(action)
    except Exception as error:
        return contexted(value, +pointed(error))


@dirty
def showly(
    action_or_actions: many_or_one[Callable[[A], B]],
    *,
    show: dirty[Callable[[B], Any]] = print,
) -> dirty[ActionChain[Callable[[A], B]]]:
    """
    Executing context with the effect of writing results.
    Prints results by default.
    """

    return discretely(binding_by(... |then>> returnly(show)))(
        action_or_actions
    )


right = flag("right")
left = flag('left', sign=False)


def either(
    *determinants_and_ways: tuple[
        Special[checker_of[C]],
        Callable[[contextual[V, C]], R] | R,
    ],
    else_: Callable[[contextual[V, C]], R] = eventually(
        raise_, ValueError("No condition is met")
    ),
) -> Callable[[contextual[V, C]], R]:
    """
    Function for using action branching like `if`, `elif` and `else` statements
    over value in `ContextRoot` form.

    Accepts branches as tuples, where in the first place is the action of
    checking by a context of an input value and in the second place is the
    action that implements the logic of this condition over the value with its
    context.

    When condition checkers are not called, compares an input context with these
    check values.

    With non-callable implementations of the conditional logic, returns those
    non-callable values.

    With default `else_` throws an error about a failed comparison if none of
    the conditions are met.
    """

    return branching(
        *(
            (attrgetter("context") |then>> to_check(determinant), way)
            for determinant, way in determinants_and_ways
        ),
        else_=else_
    )


future = flag("future")


@partially
def in_future(
    action: Callable[[V], R],
    value: V | ContextRoot[V, Flag[C] | C],
) -> contextual[V, Flag[C | contextually[event_for[R], future]]]:
    """
    Decorator to delay the execution of an input action.

    When calling the resulting action on a value, contextualizes the input value
    by the sum of the flags with a partially applied version of the resulting
    action by that value in `future` context.

    This decorator can be called the resulting action on a value, by passing
    the value as the second argument.

    For safe calling of such "future" actions from context see `future_from`.
    """

    return contexted(value, +pointed(contextually(action |to| value, when=future)))


def future_from(
    value: Special[
        contextually[event_for[R], future]
        | Flag[contextually[event_for[R], future]]
    ],
) -> Tuple[R]:
    """
    Function for safe execution of actions in `future` context.

    Calls from both the normal "future" action and the sum of the flags pointing
    the "future" actions.

    Returns a tuple of the results of found actions.
    """

    return tmap(
        call,
        pointed(value).that(lambda value: (
            isinstance(value, contextually)
            and value.context == future
        )).points,
    )
