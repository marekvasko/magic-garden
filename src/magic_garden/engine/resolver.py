"""The transaction resolver: validate, deconflict, commit atomically.

All transactions of one round were built from the same snapshot of the state.
The resolver walks them in order:

* validate   - `modify` may raise `Rejected`; the transaction is then dropped
               and reported, having changed nothing.
* deconflict - a transaction touching a key that an earlier transaction of
               this round already claimed was built from stale data. It is
               deferred: its cause is handed back to be dispatched again, on
               fresh state, in the next round. First come, first served.
* commit     - all writes of a transaction are applied together or not at all.
"""

from collections.abc import Iterable
from dataclasses import dataclass, replace

from magic_garden.engine.messages import Event, Message, Scheduled
from magic_garden.engine.state import Key, Rejected, State
from magic_garden.engine.transaction import Transaction


@dataclass(frozen=True, slots=True)
class Rejection:
    cause: Message
    reason: str


@dataclass(frozen=True, slots=True)
class Resolution:
    state: State
    immediate: tuple[Event, ...]
    future: tuple[Scheduled, ...]
    deferred: tuple[Message, ...]
    rejections: tuple[Rejection, ...]


def resolve(state: State, transactions: Iterable[Transaction]) -> Resolution:
    values = dict(state.values)
    claimed = set[Key]()
    immediate: list[Event] = []
    future: list[Scheduled] = []
    deferred: list[Message] = []
    rejections: list[Rejection] = []

    for transaction in transactions:
        keys = {*transaction.reads, *transaction.writes}
        if not claimed.isdisjoint(keys):
            # Claim the keys anyway, so that no later transaction overtakes this one.
            claimed |= keys
            deferred.append(transaction.cause)
            continue

        try:
            outputs = transaction.modify([values.get(key) for key in transaction.reads])
        except Rejected as rejected:
            rejections.append(Rejection(transaction.cause, str(rejected)))
            continue

        # Pairing up front means a malformed transaction fails before any write.
        changes = dict(zip(transaction.writes, outputs, strict=True))
        for key, value in changes.items():
            if value is None:
                values.pop(key, None)
            else:
                values[key] = value

        claimed |= keys
        immediate += transaction.immediate
        future += transaction.future

    return Resolution(
        replace(state, values=values),
        tuple(immediate),
        tuple(future),
        tuple(deferred),
        tuple(rejections),
    )
