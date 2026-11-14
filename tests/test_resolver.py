from collections.abc import Sequence

from magic_garden.engine.messages import FlowerDied, FlowerGrowth, Scheduled, TransferItems
from magic_garden.engine.resolver import resolve
from magic_garden.engine.state import Entity, Rejected, Value, entity_key, expect
from magic_garden.engine.transaction import Transaction

from helpers import actor, entity, world


def give_coin(source: str, target: str, amount: int = 1) -> Transaction:
    """A transaction moving coins, tagged with a command naming its parties."""
    keys = (entity_key(source), entity_key(target))

    def modify(inputs: Sequence[Value | None]) -> Sequence[Value | None]:
        giver, taker = expect(inputs[0], Entity), expect(inputs[1], Entity)
        return [giver.add("coin", -amount), taker.add("coin", amount)]

    cause = TransferItems(source, source, target, "coin", amount)
    return Transaction(cause, keys, keys, modify)


def test_commits_writes_and_collects_events() -> None:
    state = world(actor("ann", coin=5), actor("bob"))
    transaction = give_coin("ann", "bob")
    died, growth = FlowerDied("f"), Scheduled(9, FlowerGrowth("f"))
    transaction = Transaction(
        transaction.cause,
        transaction.reads,
        transaction.writes,
        transaction.modify,
        immediate=(died,),
        future=(growth,),
    )

    resolution = resolve(state, [transaction])

    assert entity(resolution.state, "ann").inventory == {"coin": 4}
    assert entity(resolution.state, "bob").inventory == {"coin": 1}
    assert resolution.immediate == (died,)
    assert resolution.future == (growth,)
    assert entity(state, "ann").inventory == {"coin": 5}, "the input state is untouched"


def test_rejected_transaction_changes_nothing() -> None:
    state = world(actor("ann"), actor("bob"))

    resolution = resolve(state, [give_coin("ann", "bob")])

    assert resolution.state == state
    assert [rejection.reason for rejection in resolution.rejections] == [
        "ann does not have enough coin"
    ]


def test_conflicting_transaction_is_deferred() -> None:
    state = world(actor("ann", coin=5), actor("bob"), actor("cid"))
    first, second = give_coin("ann", "bob"), give_coin("bob", "cid")

    resolution = resolve(state, [first, second])

    assert entity(resolution.state, "bob").inventory == {"coin": 1}
    assert resolution.deferred == (second.cause,)
    assert resolution.rejections == ()


def test_independent_transactions_commit_together() -> None:
    state = world(actor("ann", coin=1), actor("bob"), actor("cid", coin=1), actor("dan"))

    resolution = resolve(state, [give_coin("ann", "bob"), give_coin("cid", "dan")])

    assert resolution.deferred == ()
    assert entity(resolution.state, "bob").inventory == {"coin": 1}
    assert entity(resolution.state, "dan").inventory == {"coin": 1}


def test_later_transaction_cannot_overtake_a_deferred_one() -> None:
    state = world(actor("ann", coin=5), actor("bob"), actor("cid", coin=5), actor("dan"))
    first, second, third = give_coin("ann", "bob"), give_coin("bob", "cid"), give_coin("cid", "dan")

    resolution = resolve(state, [first, second, third])

    assert resolution.deferred == (second.cause, third.cause)


def test_rejected_transaction_does_not_block_later_ones() -> None:
    state = world(actor("ann"), actor("bob", coin=1), actor("cid"))
    broke, fine = give_coin("ann", "bob"), give_coin("bob", "cid")

    resolution = resolve(state, [broke, fine])

    assert resolution.deferred == ()
    assert entity(resolution.state, "cid").inventory == {"coin": 1}


def test_output_none_deletes_the_key() -> None:
    state = world(actor("ann"))
    key = entity_key("ann")

    def remove(inputs: Sequence[Value | None]) -> Sequence[Value | None]:
        return [None]

    resolution = resolve(state, [Transaction(FlowerDied("x"), (key,), (key,), remove)])

    assert resolution.state.values == {}


def test_modify_may_reject() -> None:
    def refuse(inputs: Sequence[Value | None]) -> Sequence[Value | None]:
        raise Rejected("no")

    resolution = resolve(world(), [Transaction(FlowerDied("x"), (), (), refuse)])

    assert [rejection.reason for rejection in resolution.rejections] == ["no"]
