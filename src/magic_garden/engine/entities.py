"""Entities: actors, and the carriers (truck, sled, wheelbarrow) they use to move things."""

from collections.abc import Sequence
from dataclasses import replace

from magic_garden.engine.messages import MoveEntity, ReleaseEntity, TransferItems, UseEntity
from magic_garden.engine.state import Entity, EntityKind, Rejected, State, Value, entity_key, expect
from magic_garden.engine.transaction import Transaction


def use(state: State, command: UseEntity) -> Transaction:
    """Take the use slot of a free carrier standing at the actor's position."""
    keys = (entity_key(command.actor), entity_key(command.entity_id))

    def modify(inputs: Sequence[Value | None]) -> Sequence[Value | None]:
        actor = expect(inputs[0], Entity)
        carrier = expect(inputs[1], Entity)
        if carrier.kind is EntityKind.ACTOR:
            raise Rejected("only carriers can be used")
        if carrier.used_by is not None:
            raise Rejected(f"{carrier.id} is already in use")
        if carrier.position != actor.position:
            raise Rejected(f"{carrier.id} is too far away")
        return [replace(carrier, used_by=actor.id)]

    return Transaction(command, keys, keys[1:], modify)


def release(state: State, command: ReleaseEntity) -> Transaction:
    """Free the use slot of a carrier."""
    keys = (entity_key(command.entity_id),)

    def modify(inputs: Sequence[Value | None]) -> Sequence[Value | None]:
        carrier = expect(inputs[0], Entity)
        if carrier.used_by != command.actor:
            raise Rejected(f"{command.actor} is not using {carrier.id}")
        return [replace(carrier, used_by=None)]

    return Transaction(command, keys, keys, modify)


def move(state: State, command: MoveEntity) -> Transaction:
    """Move the actor, together with the carrier it is using if one is named."""
    keys = (entity_key(command.actor),)
    if command.entity_id != command.actor:
        keys += (entity_key(command.entity_id),)

    def modify(inputs: Sequence[Value | None]) -> Sequence[Value | None]:
        actor, *carriers = [expect(value, Entity) for value in inputs]
        for carrier in carriers:
            if carrier.used_by != actor.id:
                raise Rejected(f"{actor.id} is not using {carrier.id}")
            if carrier.position != actor.position:
                raise Rejected(f"{carrier.id} is too far away")
        return [replace(entity, position=command.to) for entity in (actor, *carriers)]

    return Transaction(command, keys, keys, modify)


def transfer(state: State, command: TransferItems) -> Transaction:
    """Move items between two entities at the same position.

    The actor must control the source: be it, or be using it.
    """
    if command.quantity < 1:
        raise Rejected("quantity must be positive")
    if command.source == command.target:
        raise Rejected("source and target must differ")
    keys = (entity_key(command.source), entity_key(command.target))

    def modify(inputs: Sequence[Value | None]) -> Sequence[Value | None]:
        source = expect(inputs[0], Entity)
        target = expect(inputs[1], Entity)
        if command.actor not in (source.id, source.used_by):
            raise Rejected(f"{command.actor} does not control {source.id}")
        if source.position != target.position:
            raise Rejected(f"{target.id} is too far away")
        return [
            source.add(command.item, -command.quantity),
            target.add(command.item, command.quantity),
        ]

    return Transaction(command, keys, keys, modify)
