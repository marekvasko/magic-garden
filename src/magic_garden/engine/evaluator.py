"""The state evaluator: s_{t+1} = evaluate(s_t, commands, events).

A pure function. Each round it dispatches the pending messages to their
handlers, which answer with transactions, and hands those to the resolver.
Deferred messages and immediate events form the next round; the tick is over
when nothing is pending.
"""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Final, assert_never

from magic_garden.engine import entities, flowers, market
from magic_garden.engine.messages import (
    CancelOrder,
    Command,
    CompostSweep,
    CutFlower,
    Event,
    FlowerDied,
    FlowerGrowth,
    Message,
    MoveEntity,
    OrderExpiry,
    PlaceOrder,
    PlantFlower,
    ReleaseEntity,
    Scheduled,
    TradeExecuted,
    TransferItems,
    UseEntity,
)
from magic_garden.engine.resolver import Rejection, resolve
from magic_garden.engine.state import Rejected, State
from magic_garden.engine.transaction import Transaction

MAX_ROUNDS: Final = 10_000
"""Far more rounds than a sane tick needs; guards against events that trigger each other forever."""


@dataclass(frozen=True, slots=True)
class Evaluation:
    state: State
    """The state at the start of the next tick."""
    immediate: tuple[Event, ...]
    """Events that happened during this tick, in order."""
    future: tuple[Scheduled, ...]
    """Events to put on the queues."""
    rejections: tuple[Rejection, ...]
    """Commands and events that broke a rule, and why."""


def dispatch(state: State, message: Message) -> Transaction | None:
    """Ask the handler of `message` for its transaction.

    A handler may look at `state` to decide what to do, but only at keys it
    then lists in the transaction's reads or writes - that is what lets the
    resolver notice when what it saw has gone stale. It returns None when
    there is nothing to do and raises `Rejected` when a rule is broken.
    """
    match message:
        case PlaceOrder():
            return market.place_order(state, message)
        case CancelOrder():
            return market.cancel_order(state, message)
        case OrderExpiry():
            return market.expire_order(state, message)
        case PlantFlower():
            return flowers.plant(state, message)
        case CutFlower():
            return flowers.cut(state, message)
        case FlowerGrowth():
            return flowers.grow(state, message)
        case CompostSweep():
            return flowers.sweep(state, message)
        case UseEntity():
            return entities.use(state, message)
        case ReleaseEntity():
            return entities.release(state, message)
        case MoveEntity():
            return entities.move(state, message)
        case TransferItems():
            return entities.transfer(state, message)
        case TradeExecuted() | FlowerDied():
            return None  # notifications
        case _:
            assert_never(message)


def evaluate(state: State, commands: Iterable[Command], events: Iterable[Event]) -> Evaluation:
    """Apply one tick's due events, then its commands, each in the order given."""
    immediate: list[Event] = []
    future: list[Scheduled] = []
    rejections: list[Rejection] = []

    pending: tuple[Message, ...] = (*events, *commands)
    for _ in range(MAX_ROUNDS):
        if not pending:
            return Evaluation(
                replace(state, tick=state.tick + 1),
                tuple(immediate),
                tuple(future),
                tuple(rejections),
            )

        transactions: list[Transaction] = []
        for message in pending:
            try:
                transaction = dispatch(state, message)
            except Rejected as rejected:
                rejections.append(Rejection(message, str(rejected)))
            else:
                if transaction is not None:
                    transactions.append(transaction)

        resolution = resolve(state, transactions)
        state = resolution.state
        immediate += resolution.immediate
        future += resolution.future
        rejections += resolution.rejections
        pending = (*resolution.deferred, *resolution.immediate)

    raise RuntimeError(f"tick {state.tick} did not settle within {MAX_ROUNDS} rounds")
