"""A transaction: one atomic change of state, proposed by an event handler."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from magic_garden.engine.messages import Event, Message, Scheduled
from magic_garden.engine.state import Key, Value

type Modify = Callable[[Sequence[Value | None]], Sequence[Value | None]]
"""Maps the values under `reads` to the new values for `writes`.

None stands for "no value": a missing input, or an output to delete.
Raise `Rejected` to refuse the change.
"""


@dataclass(frozen=True, slots=True)
class Transaction:
    cause: Message
    reads: tuple[Key, ...]
    writes: tuple[Key, ...]
    modify: Modify
    immediate: tuple[Event, ...] = ()
    """Events that happen, in this same tick, once the transaction commits."""
    future: tuple[Scheduled, ...] = ()
    """Events to schedule once the transaction commits."""
