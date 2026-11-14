"""Flowers: planted from seed, growing in stages, cut for blooms until they die."""

from collections.abc import Sequence
from dataclasses import replace
from typing import Final

from magic_garden.engine.messages import (
    CompostSweep,
    CutFlower,
    FlowerDied,
    FlowerGrowth,
    PlantFlower,
    Scheduled,
)
from magic_garden.engine.state import (
    Entity,
    Flower,
    Rejected,
    Stage,
    State,
    Value,
    entity_key,
    expect,
    flower_key,
)
from magic_garden.engine.transaction import Transaction

GROWTH_TICKS: Final = 5
"""Ticks a flower spends in each growing stage."""

NEXT_STAGE: Final = {Stage.SEED: Stage.SPROUT, Stage.SPROUT: Stage.BLOOM}


def seed_of(species: str) -> str:
    """The inventory item that grows into `species`."""
    return f"{species} seed"


def plant(state: State, command: PlantFlower) -> Transaction:
    """Spend one seed to plant a flower where the actor stands."""
    keys = (entity_key(command.actor), flower_key(command.flower_id))

    def modify(inputs: Sequence[Value | None]) -> Sequence[Value | None]:
        actor = expect(inputs[0], Entity)
        if inputs[1] is not None:
            raise Rejected("flower id is already taken")
        flower = Flower(command.flower_id, command.species, actor.id, actor.position)
        return [actor.add(seed_of(command.species), -1), flower]

    growth = Scheduled(state.tick + GROWTH_TICKS, FlowerGrowth(command.flower_id))
    return Transaction(command, keys, keys, modify, future=(growth,))


def grow(state: State, event: FlowerGrowth) -> Transaction | None:
    """Advance a flower one stage: seed -> sprout -> bloom."""
    key = flower_key(event.flower_id)
    flower = state.get(key)
    if not isinstance(flower, Flower) or flower.stage not in NEXT_STAGE:
        return None

    def modify(inputs: Sequence[Value | None]) -> Sequence[Value | None]:
        flower = expect(inputs[0], Flower)
        return [replace(flower, stage=NEXT_STAGE[flower.stage])]

    still_growing = flower.stage is Stage.SEED
    growth = Scheduled(state.tick + GROWTH_TICKS, event)
    return Transaction(event, (key,), (key,), modify, future=(growth,) if still_growing else ())


def cut(state: State, command: CutFlower) -> Transaction:
    """Cut a bloom into the actor's inventory. The flower regrows, or dies on its last cut."""
    key = flower_key(command.flower_id)
    keys = (key, entity_key(command.actor))
    dies = expect(state.get(key), Flower).cuts_left <= 1

    def modify(inputs: Sequence[Value | None]) -> Sequence[Value | None]:
        flower = expect(inputs[0], Flower)
        actor = expect(inputs[1], Entity)
        if flower.owner != actor.id:
            raise Rejected("not your flower")
        if flower.position != actor.position:
            raise Rejected("flower is too far away")
        if flower.stage is not Stage.BLOOM:
            raise Rejected("flower is not in bloom")
        cuts_left = flower.cuts_left - 1
        stage = Stage.SPROUT if cuts_left > 0 else Stage.DEAD
        return [replace(flower, stage=stage, cuts_left=cuts_left), actor.add(flower.species, 1)]

    if dies:
        return Transaction(command, keys, keys, modify, immediate=(FlowerDied(command.flower_id),))
    regrowth = Scheduled(state.tick + GROWTH_TICKS, FlowerGrowth(command.flower_id))
    return Transaction(command, keys, keys, modify, future=(regrowth,))


def sweep(state: State, event: CompostSweep) -> Transaction | None:
    """Remove every dead flower from the world."""
    dead = tuple(
        key
        for key, value in state.values.items()
        if isinstance(value, Flower) and value.stage is Stage.DEAD
    )
    if not dead:
        return None

    def modify(inputs: Sequence[Value | None]) -> Sequence[Value | None]:
        return [None] * len(inputs)

    return Transaction(event, dead, dead, modify)
