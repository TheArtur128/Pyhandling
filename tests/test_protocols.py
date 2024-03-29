from dataclasses import dataclass, field

from act.objects import obj
from act.protocols import *
from act.testing import case_of


test_protocol_of = case_of(
    lambda: not isinstance(obj(a=1), protocol_of(obj(a=..., b=...))),
    lambda: isinstance(obj(a=1, b=2), protocol_of(obj(a=..., b=...))),
    lambda: isinstance(obj(a=1, b=2, c=3), protocol_of(obj(a=..., b=...))),
)


def test_proto_classes():
    class A:
        a = 1

    class B(A):
        b = 2

    assert isinstance(B(), Proto[B])

    assert not isinstance(obj(a=1), Proto[B])
    assert isinstance(obj(a=1, b=2), Proto[B])
    assert isinstance(obj(a=1, b=2, c=3), Proto[B])


def test_proto_dataclasses():
    @dataclass(frozen=True)
    class A:
        a: int

    @dataclass(frozen=True)
    class B(A):
        b: int = field(default_factory=lambda: 4)

    assert isinstance(B(a=1, b=2), Proto[B])

    assert not isinstance(obj(a=1), Proto[B])
    assert isinstance(obj(a=1, b=2), Proto[B])
    assert isinstance(obj(a=1, b=2, c=3), Proto[B])
