from pyhandling.contexting import contextual
from pyhandling.testing import case_of
from pyhandling.structure_management import *


test_as_collection = case_of(
    (lambda: as_collection(42), (42, )),
    (lambda: as_collection(None), (None, )),
    (lambda: as_collection([1, 2, 3]), (1, 2, 3)),
    (lambda: as_collection(map(lambda x: x ** 2, [4, 8, 16])), (16, 64, 256)),
    (lambda: as_collection((3, 9, 12)), (3, 9, 12)),
    (lambda: as_collection(tuple()), tuple()),
    (lambda: as_collection('Hello'), ('H', 'e', 'l', 'l', 'o')),
)


test_tmap = case_of((
    lambda: tmap(lambda i: i + 1, range(9)), tuple(range(1, 10))
))


test_tfilter = case_of((
    lambda: tfilter(lambda i: i % 2 == 0, range(11)), tuple(range(0, 11, 2))
))

test_tzip = case_of((
    lambda: tzip(['a', 'b'], range(10)), (('a', 0), ('b', 1))
))


test_flat = case_of(
    (lambda: flat(1), (1, )),
    (lambda: flat([1, 2, 3]), (1, 2, 3)),
    (lambda: flat([1, 2, (3, 4)]), (1, 2, 3, 4)),
    (lambda: flat([1, 2, (3, (4, 5))]), (1, 2, 3, (4, 5))),
    (lambda: flat(tuple()), tuple()),
    (lambda: flat(str()), tuple()),
    (lambda: flat(item for item in [1, 2, 3]), (1, 2, 3)),
)


test_deep_flat = case_of(
    (lambda: deep_flat(1), (1, )),
    (lambda: deep_flat([1, 2, 3]), (1, 2, 3)),
    (lambda: deep_flat([(1, 2), 3, 4]), (1, 2, 3, 4)),
    (lambda: deep_flat([(1, [2, 3]), 4, 5]), (1, 2, 3, 4, 5)),
    (lambda: deep_flat([(1, [2, 3]), 4, 5]), (1, 2, 3, 4, 5)),
    (lambda: deep_flat(item for item in [1, 2, 3]), (1, 2, 3)),
)


test_append = case_of(
    (lambda: append(2)(1), (1, 2)),
    (lambda: append(3)([1, 2]), (1, 2, 3)),
    (lambda: append(3)(item for item in [1, 2]), (1, 2, 3)),
    (lambda: append(3)('ab'), ('a', 'b', 3)),
    (lambda: append([2, 3])(1), (1, [2, 3])),
    (lambda: append(None)(1), (1, None)),
    (lambda: append(2)(None), (None, 2)),
    (lambda: append(2, 3)(1), (1, 2, 3)),
)


test_without = case_of(
    (lambda: without(1)(1), tuple()),
    (lambda: without(1)((1, 2)), (2, )),
    (lambda: without(3)((1, 2)), (1, 2)),
    (lambda: without(1, 2)([1, 2]), tuple()),
    (lambda: without(1, 2)(item for item in [1, 2, 3]), (3, )),
    (lambda: without(1, 1, 1, 10)((1, 2, 1, 3, 1, 4, 1)), (2, 3, 4, 1)),
)


test_slice_from = case_of(
    (lambda: slice_from(range(10)), slice(0, 10, 1)),
    (lambda: slice_from(range(2, 10)), slice(2, 10, 1)),
    (lambda: slice_from(range(2, 10, 2)), slice(2, 10, 2)),
)


test_interval = case_of(
    (lambda: tuple(interval[:10]), (slice(None, 10, None), )),
    (lambda: tuple(interval[2:10:2]), (slice(2, 10, 2), )),
    (lambda: tuple(interval[:]), (slice(None, None, None), )),
    (
        lambda: tuple(interval[2:6][-10:-2][20:15:-1]),
        (slice(2, 6, None), slice(-10, -2, None), slice(20, 15, -1)),
    ),
)


test_range_from = case_of(
    (lambda: range_from(10), range(10)),
    (lambda: range_from(10, limit=3), range(3)),
    (lambda: range_from(10, limit=11), range(10)),
    (lambda: range_from(range(-1, -11, -1)), range(-1, -11, -1)),
    (lambda: range_from(range(-1, -11, -1), limit=20), range(-1, -11, -1)),
    (lambda: range_from(range(-1, -11, -1), limit=1), range(-1, -1, -1)),
)


test_marked_ranges_from = case_of(
    (lambda: marked_ranges_from([4]), (contextual(range(4, 5), filled), )),
    (lambda: marked_ranges_from((1, 2)), (contextual(range(1, 3), filled), )),
    (lambda: marked_ranges_from((1, 3)), (contextual(range(1, 4), empty), )),
    (lambda: marked_ranges_from((1, 3, 4)), (
        contextual(range(1, 4), empty), contextual(range(3, 5), filled),
    )),
    (lambda: marked_ranges_from((1, 3, 4, 9, 10, 11)), (
        contextual(range(1, 4), empty), contextual(range(3, 5), filled),
        contextual(range(4, 10), empty), contextual(range(9, 12), filled),
    )),
    (lambda: marked_ranges_from(range(600)), (contextual(range(600), filled), )),
)
