from enum import Enum, auto
from functools import reduce, wraps, partial
from math import inf
from typing import Callable, Iterable, Self, Optional

from pyhandling.annotations import Handler, checker_of, Event, handler_of, factory_of, event_for

from pyhandling.tools import DelegatingProperty, ArgumentPack, Clock


class HandlerKeeper:
    """
    Mixin class for conveniently getting handlers from an input collection and
    unlimited input arguments.
    """

    handlers = DelegatingProperty('_handlers')

    def __init__(self, handler_resource: Handler | Iterable[Handler], *handlers: Handler):
        self._handlers = (
            tuple(handler_resource)
            if isinstance(handler_resource, Iterable)
            else (handler_resource, )
        ) + handlers


class ReturnFlag(Enum):
    """
    Enum return method flags class.
    
    Describe the returned result from something (MultipleHandler).
    """

    first_received = auto()
    last_thing = auto()
    everything = auto()
    nothing = auto()


class MultipleHandler(HandlerKeeper):
    """
    Handler proxy class for representing multiple handlers as a single
    interface.

    Applies its handlers to a single resource.

    Return data is described using the ReturnFlag of the return_flag attribute.
    """

    def __init__(
        self,
        handler_resource: Handler | Iterable[Handler],
        *handlers: Handler,
        return_flag: ReturnFlag = ReturnFlag.first_received
    ):
        super().__init__(handler_resource, *handlers)
        self.return_flag = return_flag

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(map(str, self.handlers))})"

    def __call__(self, resource: any) -> any:
        result_of_all_handlers = list()

        for handler in self.handlers:
            handler_result = handler(resource)

            if self.return_flag == ReturnFlag.everything:
                result_of_all_handlers.append(handler_result)

            if self.return_flag == ReturnFlag.first_received and handler_result is not None:
                return handler_result

        if self.return_flag == ReturnFlag.everything:
            return result_of_all_handlers

        if self.return_flag == ReturnFlag.last_thing:
            return handler_result


class ActionChain:
    """
    Class that implements handling as a chain of actions of handlers.

    In the presence of basic chains (strictly instances of the ActionChain class)
    in the rows of handlers, takes their handlers instead of them.

    Each next handler gets the output of the previous one.
    Data returned when called is data exited from the last handler.

    The first handler is not bound to the standard handler interface and can be
    any callable object.

    Accordingly, delegates the call to that first handler, so it emulates its
    interface.

    If there are no handlers, spits out the input as output.

    Can be connected to another chain or handler using | between them with
    maintaining the position of the call.

    Also can be used >> to expand handlers starting from the end respectively.
    """

    handlers = DelegatingProperty('_handlers')

    def __init__(self, opening_handler_resource: Callable | Iterable[Callable], *handlers: Handler):
        self._handlers = self.get_with_aligned_chains(
            (
                tuple(opening_handler_resource)
                if isinstance(opening_handler_resource, Iterable)
                else (opening_handler_resource, )
            )
            + handlers
        )

    def __call__(self, *args, **kwargs) -> any:
        return reduce(
            lambda resource, handler: handler(resource),
            (self.handlers[0](*args, **kwargs), *self.handlers[1:])
        ) if self.handlers else resource

    def __rshift__(self, action_node: Handler) -> Self:
        return self.clone_with(action_node)

    def __or__(self, action_node: Handler) -> Self:
        return self.clone_with(action_node)

    def __ror__(self, action_node: Handler) -> Self:
        return self.clone_with(action_node, is_other_handlers_on_the_left=True)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({' -> '.join(map(str, self.handlers))})"

    def clone_with(self, *handlers: Handler, is_other_handlers_on_the_left: bool = False) -> Self:
        """
        Method for cloning the current chain instance with additional handlers
        from unlimited arguments.

        Additional handlers can be added to the beginning of the chain if
        `is_other_handlers_on_the_left = True`.
        """

        handler_groph = [self.handlers, handlers]

        if is_other_handlers_on_the_left:
            handler_groph.reverse()

        return self.__class__(
            *handler_groph[0],
            *handler_groph[1],
        )

    def clone_with_intermediate(
        self,
        intermediate_handler: Handler,
        *,
        is_on_input: bool = False,
        is_on_output: bool = False
    ) -> Self:
        """
        Method for cloning the current chain with an additional handler between
        the current chain handlers.

        Also, the intermediate handler can add to the end and/or to the beginning
        of the chain with is_on_input and/or is_on_output = True.
        """

        if not self.handlers:
            return self

        return ActionChain(
            ((intermediate_handler, ) if is_on_input else tuple())
            + ((
                self.handlers[0] |then>> ActionChain(
                    post_partial(get_collection_with_reduced_nesting, 1)(
                        intermediate_handler |then>> handler
                        for handler in self.handlers[1:]
                    )
                )
            ), )
            + ((intermediate_handler, ) if is_on_output else tuple())
        )

    @staticmethod
    def get_with_aligned_chains(handlers: Iterable[Handler]) -> tuple[Handler]:
        """
        Function for getting homogeneous handlers without unnecessary chain
        instances.
        """

        return post_partial(get_collection_with_reduced_nesting, 1)(
            handler.handlers if type(handler) is ActionChain else (handler, )
            for handler in handlers
        )


def on_condition(checker: Callable[..., bool], func: Callable, *, else_: Optional[Callable] = None) -> Callable:
    """
    Function that implements branching of something according to a
    certain condition.

    Selects the appropriate handler based on the results of the
    condition_resource_checker.

    In case of a negative case and the absence of a negative case handler (else_),
    returns None.
    """

    if else_ is None:
        else_ = eventually(partial(return_, None))

    @wraps(func)
    def wrapper(*args, **kwargs) -> any:
        return (func if checker(*args, **kwargs) else else_)(*args, **kwargs)

    return wrapper


def eventually(func: Event) -> any:
    """
    Decorator function for constructing a function to which no input attributes
    will be passed.
    """

    return wraps(func)(lambda *args, **kwargs: func())


def handle_context_by(context_factory: Event, context_handler: Handler):
    """
    Function for emulating the "with as" context manager.

    Creates a context using the context_factory and returns the results of
    handling this context by context_handler.
    """

    with context_factory() as context:
        return context_handler(context)


def rollbackable(func: Callable, rollbacker: handler_of[Exception]) -> Callable:
    """
    Decorator function providing handling of possible errors.
    Delegates error handling to rollbacker.
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> any:
        try:
            return func(*args, **kwargs)
        except Exception as error:
            return rollbacker(error)

    return wrapper


def get_collection_from(*collections: Iterable) -> tuple:
    """Function to get a collection with elements from input collections."""

    return get_collection_with_reduced_nesting(collections, 1)


def recursively(resource_handler: Handler, condition_checker: checker_of[any]) -> any:
    """
    Function to recursively handle input resource.

    If the result of handling for recursion is correct, it feeds the results
    of recursive_resource_handler to it, until the negative results of the
    recursion condition.

    Checks the condition of execution of the recursion by the correctness of the
    input resource or the result of the execution of the handler of the recursion
    resource.
    """

    def recursively_handle(resource: any) -> any:
        """
        Function emulating recursion that was created as a result of calling
        recursively.
        """

        while condition_checker(resource):
            resource = resource_handler(resource)

        return resource

    return recursively_handle


def post_partial(func: Callable, *args, **kwargs) -> Callable:
    """
    Function equivalent to functools.partial but with the difference that
    additional arguments are added not before the incoming ones from the final
    call, but after.
    """

    @wraps(func)
    def wrapper(*wrapper_args, **wrapper_kwargs) -> any:
        return func(*wrapper_args, *args, **wrapper_kwargs, **kwargs)

    return wrapper


def mirror_partial(func: Callable, *args, **kwargs) -> Callable:
    """
    Function equivalent to pyhandling.handlers.rigth_partial but with the
    difference that additional arguments from this function call are unfolded.
    """

    return rigth_partial(func, *args[::-1], **kwargs)


def mergely(
    merge_function_factory: factory_of[Callable],
    *parallel_functions: factory_of[any],
    **keyword_parallel_functions: factory_of[any]
):
    """
    Decorator function that allows to initially separate several operations on
    input arguments and then combine these results in final operation.

    Gets the final merging function of the first input function by calling it
    with all the input arguments of the resulting (as a result of calling this
    particular function) function.

    Passes to the final merge function the results of calls to unbounded input
    functions (with the same arguments that were passed to the factory of this
    final merge function).

    When specifying parallel functions using keyword arguments, sets them to the
    final merging function through the same argument name through which they
    were specified.
    """

    @wraps(merge_function_factory)
    def wrapper(*args, **kwargs):
        return merge_function_factory(*args, **kwargs)(
            *(
                parallel_function(*args, **kwargs)
                for parallel_function in parallel_functions
            ),
            **{
                kwarg: keyword_parallel_function(*args, **kwargs)
                for kwarg, keyword_parallel_function in keyword_parallel_functions.items()
            }
        )

    return wrapper


def bind(func: Callable, argument_name: str, argument_value: any) -> Callable:
    """
    Atomic partial function for a single keyword argument whose name and value
    are separate input arguments.
    """

    return wraps(func)(partial(func, **{argument_name: argument_value}))


def dynamically_bind(
    func: Callable[[any, ...], any],
    argument_name: str,
    argument_handler: Handler,
) -> Callable[[any, ...], any]:
    """
    Atomic partial function allowing to calculate the value of the input
    argument of the input function depending on the first input argument of the
    input function.

    Aimed mostly to bring the function to the Handler interface.
    """

    @wraps(func)
    def wrapper(resource: any) -> any:
        return func(resource, **{argument_name: argument_handler(resource)})

    return wrapper


def unpackly(func: Callable) -> handler_of[ArgumentPack | Iterable]:
    """
    Decorator function that allows to bring an ordinary function to the Handler
    interface by unpacking the input resource into the input function.

    Specifies the type of unpacking depending on the type of the input resource
    into the resulting function.

    When ArgumentPack delegates unpacking to it (Preferred Format).

    When a dict or otherwise a homogeneous collection unpacks * or **
    respectively.

    Also unpacks a collection of the form [collection, dict] as * and ** from
    this collection.
    """

    @wraps(func)
    def wrapper(argument_collection: ArgumentPack | Iterable) -> any:
        if isinstance(argument_collection, ArgumentPack):
            return argument_collection.call(func)
        elif isinstance(argument_collection, dict):
            return func(**argument_collection)
        elif isinstance(argument_collection, Iterable):
            return func(*argument_collection[0], **argument_collection[1]) if (
                len(argument_collection) == 2
                and isinstance(argument_collection[0], Iterable)
                and isinstance(argument_collection[1], dict)
            ) else func(*argument_collection)

    return wrapper


def return_(resource: any) -> any:
    """
    Wrapper function for handling emulation through the functional use of the
    return statement.
    """

    return resource


def raise_(error: Exception) -> None:
    """Wrapper function for functional use of raise statement."""

    raise error


def call(caller: Callable, *args, **kwargs) -> any:
    """Function to call an input object and return the results of that call."""

    return caller(*args, **kwargs)


def call_method(object_: object, method_name: str, *args, **kwargs) -> any:
    """Shortcut function to call a method on an input object."""

    return getattr(object_, method_name)(*args, **kwargs)


def getattr_of(object_: object, attribute_name: str) -> any:
    """
    Synonym function for getattr.

    Unlike original getattr arguments can be keyword.
    """

    return getattr(object_, attribute_name)


def setattr_of(object_: object, attribute_name: str, attribute_value: any) -> any:
    """
    Synonym function for setattr.

    Unlike original setattr arguments can be keyword.
    """

    return setattr(object_, attribute_name, attribute_value)


def getitem_of(object_: object, item_key: any) -> any:
    """Function for functional use of [] getting."""

    return object_[item_key]


def setitem_of(object_: object, item_key: any, item_value: any) -> None:
    """Function for functional use of [] setting."""

    object_[item_key] = item_value


def execute_operation(first_operand: any, operator: str, second_operand: any) -> any:
    """
    Function to use python operators in a functional way.

    Since this function uses eval, do not pass operator and unchecked standard
    type operands from the global input to it.
    """

    return eval(
        f"first_operand {operator} second_operand",
        {'then': then},
        {'first_operand': first_operand, 'second_operand': second_operand}
    )


def get_collection_with_reduced_nesting(collection: Iterable, number_of_reductions: int = inf) -> tuple:
    """Function that allows to get a collection with a reduced nesting level."""

    reduced_collection = list()

    for item in collection:
        if not isinstance(item, Iterable):
            reduced_collection.append(item)
            continue

        reduced_collection.extend(
            get_collection_with_reduced_nesting(item, number_of_reductions - 1)
            if number_of_reductions > 1
            else item
        )

    return tuple(reduced_collection)


def additionally(action: Handler) -> Handler:
    """
    Function that allows to handle a resource but not return the results of its
    handling.
    """

    @wraps(action)
    def wrapper(resource: any) -> any:
        action(resource)
        return resource

    return wrapper


def close(resource: any, *, closer: Callable[[any, ...], any] = partial) -> Callable:
    """
    Function to create a closure for the input resource.

    Wraps the input resource in a container function that can be \"opened\" when
    that function is called.

    The input resource type depends on the chosen closer function.

    With a default closer function, ***it requires a Callable resource***.

    When \"opened\" the default container function returns an input resource with
    the bined input arguments from the function container.
    """

    return partial(closer, resource)


def showly(handler: Handler, *, writer: handler_of[str] = print) -> ActionChain:
    """
    Decorator function for visualizing the outcomes of intermediate stages of a
    chain of actions, or simply the input and output results of a regular handler.
    """

    writer = additionally(str |then>> writer)

    return (
        handler.clone_with_intermediate(writer, is_on_input=True, is_on_output=True)
        if isinstance(handler, ActionChain)
        else wraps(handler)(writer |then>> handler |then>> writer)
    )


then = ActionChain(tuple())
then.__doc__ = (
    """
    ActionChain class instance with no handlers.

    Used as an operator emulator for convenient construction of ActionChains.
    Assumes usage like \"first_handler |then>> second_handler\".

    See ActionChain for more info.
    """
)


as_collection: Callable[[any], tuple] = on_condition(
    post_partial(isinstance, Iterable),
    tuple,
    else_=lambda resource: (resource, )
)
as_collection.__doc__ = (
    """
    Function to convert an input resource into a tuple collection.
    With a non-iterable resource, wraps it in a tuple.
    """
)


as_argument_pack: Callable[[any], ArgumentPack] = on_condition(
    post_partial(isinstance, ArgumentPack),
    return_,
    else_=ArgumentPack.create_via_call
)
as_argument_pack.__doc__ = (
    """
    Function to optionally convert an input resource into an ArgumentPack with
    one argument (the input resource).

    When input resource is ArgumentPack, function returns it unchanged.
    """
)

with_doc = close(partial(bind, bind(setattr_of, 'argument_name', '__doc__'), 'argument_value'), closer=partial)


from_argument_pack: Callable[[Callable], Callable[[ArgumentPack | Iterable], any]] = (
    unpackly
    |then>> close(partial(call_method, ActionChain(as_argument_pack), 'clone_with')),
)


times: Callable[[int], event_for[bool]] = (
    (lambda number: number + 1)
    |then>> Clock
    |then>> close(
        additionally(dynamically_bind(
            bind(setattr_of, 'attribute_name', 'ticks_to_disability'),
            'attribute_value',
            on_condition(
                return_,
                (lambda clock: clock.ticks_to_disability - 1),
                else_=(lambda clock: clock.initial_ticks_to_disability - 1)
            )
        ))
        |then>> bool
    )
)
times.__doc__ = (
    """
    Function to create a dirty function that will return True the input value
    (for this function) number of times, then False once after the input count
    has passed, True again n times, and so on.
    """
)
