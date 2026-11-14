"""The world state: an immutable key-value store of game objects.

Every object lives under one key. Transactions name the keys they read and
write, which is what lets the resolver detect conflicts between them.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Final

COIN: Final = "coin"
"""The inventory item used as money."""


class Rejected(Exception):
    """A command or event broke a game rule; it changes nothing."""


# --- entities ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Position:
    x: int
    y: int


class EntityKind(StrEnum):
    ACTOR = "actor"  # a player, AI or NPC
    TRUCK = "truck"
    SLED = "sled"
    WHEELBARROW = "wheelbarrow"


type Inventory = Mapping[str, int]
"""Item name -> quantity. Only positive quantities are stored."""


@dataclass(frozen=True, slots=True)
class Entity:
    """Anything with a position and an inventory.

    Carriers (truck, sled, wheelbarrow) also have a use slot: the one actor
    currently operating them.
    """

    id: str
    kind: EntityKind
    position: Position
    inventory: Inventory = field(default_factory=dict[str, int])
    used_by: str | None = None

    def add(self, item: str, amount: int) -> Entity:
        """Return a copy holding `amount` more (or, if negative, fewer) of `item`."""
        quantity = self.inventory.get(item, 0) + amount
        if quantity < 0:
            raise Rejected(f"{self.id} does not have enough {item}")
        inventory = {**self.inventory, item: quantity}
        if quantity == 0:
            del inventory[item]
        return replace(self, inventory=inventory)


# --- flowers ----------------------------------------------------------------


class Stage(StrEnum):
    SEED = "seed"
    SPROUT = "sprout"
    BLOOM = "bloom"
    DEAD = "dead"


@dataclass(frozen=True, slots=True)
class Flower:
    id: str
    species: str
    owner: str
    position: Position
    stage: Stage = Stage.SEED
    cuts_left: int = 3
    """How many more times the flower survives being cut."""


# --- market -----------------------------------------------------------------


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class Order:
    id: str
    owner: str
    side: Side
    price: int
    quantity: int


@dataclass(frozen=True, slots=True)
class OrderBook:
    """Resting limit orders for one item, each side sorted best first.

    Within one price the oldest order comes first (price-time priority).
    """

    item: str
    bids: tuple[Order, ...] = ()
    asks: tuple[Order, ...] = ()
    next_order_number: int = 1


# --- the store --------------------------------------------------------------


class Kind(StrEnum):
    ENTITY = "entity"
    FLOWER = "flower"
    BOOK = "book"


type Key = tuple[Kind, str]
type Value = Entity | Flower | OrderBook


def entity_key(entity_id: str) -> Key:
    return (Kind.ENTITY, entity_id)


def flower_key(flower_id: str) -> Key:
    return (Kind.FLOWER, flower_id)


def book_key(item: str) -> Key:
    return (Kind.BOOK, item)


@dataclass(frozen=True, slots=True)
class State:
    """The whole world at the start of one tick."""

    tick: int = 0
    values: Mapping[Key, Value] = field(default_factory=dict[Key, Value])

    def get(self, key: Key) -> Value | None:
        return self.values.get(key)


def expect[T](value: object, kind: type[T]) -> T:
    """Return `value` as a `kind`, rejecting the transaction if it is missing."""
    if not isinstance(value, kind):
        raise Rejected(f"{kind.__name__.lower()} not found")
    return value
