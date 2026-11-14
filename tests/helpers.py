"""Small builders shared by the tests."""

from magic_garden.engine.state import (
    Entity,
    EntityKind,
    Flower,
    Key,
    Kind,
    OrderBook,
    Position,
    State,
    Value,
)

HOME = Position(0, 0)


def actor(entity_id: str, position: Position = HOME, **inventory: int) -> Entity:
    return Entity(entity_id, EntityKind.ACTOR, position, inventory)


def world(*values: Value, tick: int = 0) -> State:
    return State(tick, {_key(value): value for value in values})


def _key(value: Value) -> Key:
    match value:
        case Entity():
            return (Kind.ENTITY, value.id)
        case Flower():
            return (Kind.FLOWER, value.id)
        case OrderBook():
            return (Kind.BOOK, value.item)


def entity(state: State, entity_id: str) -> Entity:
    value = state.get((Kind.ENTITY, entity_id))
    assert isinstance(value, Entity)
    return value


def flower(state: State, flower_id: str) -> Flower:
    value = state.get((Kind.FLOWER, flower_id))
    assert isinstance(value, Flower)
    return value


def book(state: State, item: str) -> OrderBook:
    value = state.get((Kind.BOOK, item))
    assert isinstance(value, OrderBook)
    return value
