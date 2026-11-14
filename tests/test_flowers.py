from magic_garden.engine import Engine
from magic_garden.engine.flowers import GROWTH_TICKS
from magic_garden.engine.messages import (
    CompostSweep,
    CutFlower,
    FlowerDied,
    MoveEntity,
    PlantFlower,
)
from magic_garden.engine.state import Entity, EntityKind, Flower, Position, Stage, flower_key

from helpers import actor, entity, flower, world


def run(engine: Engine, ticks: int) -> None:
    for _ in range(ticks):
        engine.tick()


def garden(**flower_fields: int) -> Engine:
    """Ann standing next to her blooming rose."""
    rose = Flower("f1", "rose", "ann", Position(0, 0), Stage.BLOOM, **flower_fields)
    return Engine(world(actor("ann"), actor("bob"), rose))


def test_planted_seed_grows_into_a_bloom() -> None:
    engine = Engine(world(Entity("ann", EntityKind.ACTOR, Position(0, 0), {"rose seed": 1})))
    engine.ingest(PlantFlower("ann", "f1", "rose"))

    engine.tick()
    assert flower(engine.state, "f1").stage is Stage.SEED
    assert entity(engine.state, "ann").inventory == {}
    assert len(engine.queue.flowers) == 1

    run(engine, GROWTH_TICKS)
    assert flower(engine.state, "f1").stage is Stage.SPROUT
    run(engine, GROWTH_TICKS)
    assert flower(engine.state, "f1").stage is Stage.BLOOM
    assert len(engine.queue.flowers) == 0


def test_planting_needs_a_seed_and_a_fresh_id() -> None:
    engine = garden()
    engine.ingest(PlantFlower("ann", "f2", "rose"))
    engine.ingest(PlantFlower("bob", "f1", "rose"))

    result = engine.tick()

    assert [rejection.reason for rejection in result.rejections] == [
        "ann does not have enough rose seed",
        "flower id is already taken",
    ]


def test_cut_flower_gives_a_bloom_and_regrows() -> None:
    engine = garden()
    engine.ingest(CutFlower("ann", "f1"))

    engine.tick()
    assert entity(engine.state, "ann").inventory == {"rose": 1}
    assert flower(engine.state, "f1") == Flower(
        "f1", "rose", "ann", Position(0, 0), Stage.SPROUT, cuts_left=2
    )

    run(engine, GROWTH_TICKS)
    assert flower(engine.state, "f1").stage is Stage.BLOOM


def test_flower_dies_on_its_last_cut_and_is_composted() -> None:
    engine = garden(cuts_left=1)
    engine.every(3, CompostSweep())
    engine.ingest(CutFlower("ann", "f1"))

    result = engine.tick()
    assert result.immediate == (FlowerDied("f1"),)
    assert flower(engine.state, "f1").stage is Stage.DEAD
    assert entity(engine.state, "ann").inventory == {"rose": 1}

    run(engine, 3)
    assert engine.state.get(flower_key("f1")) is None


def test_cut_rules() -> None:
    engine = garden()
    engine.ingest(CutFlower("bob", "f1"))
    engine.ingest(CutFlower("ann", "missing"))
    engine.ingest(CutFlower("ann", "f1"))
    engine.ingest(CutFlower("ann", "f1"))

    result = engine.tick()

    assert [rejection.reason for rejection in result.rejections] == [
        "flower not found",
        "not your flower",
        "flower is not in bloom",
    ]
    assert entity(engine.state, "ann").inventory == {"rose": 1}


def test_cutting_needs_to_be_next_to_the_flower() -> None:
    engine = garden()
    engine.ingest(MoveEntity("ann", "ann", Position(4, 4)))
    engine.ingest(CutFlower("ann", "f1"))

    result = engine.tick()

    assert [rejection.reason for rejection in result.rejections] == ["flower is too far away"]
