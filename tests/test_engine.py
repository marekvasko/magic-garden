from magic_garden.engine import Engine, evaluate
from magic_garden.engine.messages import FlowerGrowth, PlaceOrder, Scheduled, TransferItems
from magic_garden.engine.state import Flower, Position, Side, Stage, flower_key

from helpers import actor, entity, world


def test_tick_advances_time_and_drains_the_batch() -> None:
    engine = Engine(world(actor("ann", coin=3), actor("bob")))
    engine.ingest(TransferItems("ann", "ann", "bob", "coin", 1))

    engine.tick()
    engine.tick()

    assert engine.state.tick == 2
    assert entity(engine.state, "bob").inventory == {"coin": 1}


def test_evaluate_is_pure() -> None:
    state = world(actor("ann", coin=3), actor("bob"))
    commands = [TransferItems("ann", "ann", "bob", "coin", 1)]

    first, second = evaluate(state, commands, []), evaluate(state, commands, [])

    assert first == second
    assert entity(state, "ann").inventory == {"coin": 3}
    assert first.state.tick == state.tick + 1


def test_commands_on_the_same_keys_apply_in_ingest_order() -> None:
    state = world(actor("ann", coin=1), actor("bob"), actor("cid"))
    commands = [
        TransferItems("ann", "ann", "bob", "coin", 1),
        TransferItems("bob", "bob", "cid", "coin", 1),
        TransferItems("cid", "cid", "ann", "coin", 1),
    ]

    result = evaluate(state, commands, [])

    assert result.rejections == ()
    assert entity(result.state, "ann").inventory == {"coin": 1}


def test_due_events_run_before_commands() -> None:
    rose = Flower("f1", "rose", "ann", Position(0, 0), Stage.SPROUT)
    engine = Engine(world(actor("ann"), rose))
    engine.schedule(Scheduled(0, FlowerGrowth("f1")))

    engine.tick()

    assert engine.state.get(flower_key("f1")) == Flower(
        "f1", "rose", "ann", Position(0, 0), Stage.BLOOM
    )


def test_many_orders_on_one_book_settle_within_a_tick() -> None:
    engine = Engine(world(actor("ann", coin=1000), actor("bob", rose=50)))
    for _ in range(50):
        engine.ingest(PlaceOrder("bob", "rose", Side.SELL, 3, 1))
        engine.ingest(PlaceOrder("ann", "rose", Side.BUY, 3, 1))

    result = engine.tick()

    assert len(result.immediate) == 50
    assert entity(engine.state, "ann").inventory == {"coin": 850, "rose": 50}
    assert entity(engine.state, "bob").inventory == {"coin": 150}
