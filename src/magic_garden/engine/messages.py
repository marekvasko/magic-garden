"""Everything the engine reacts to: commands from actors and events from the world."""

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from magic_garden.engine.state import Position, Side

# --- commands: requests from a user, AI or NPC --------------------------------


@dataclass(frozen=True, slots=True)
class PlaceOrder:
    actor: str
    item: str
    side: Side
    price: int
    quantity: int
    ttl: int | None = None
    """Ticks an unfilled order stays in the book; None means until cancelled."""


@dataclass(frozen=True, slots=True)
class CancelOrder:
    actor: str
    item: str
    order_id: str


@dataclass(frozen=True, slots=True)
class PlantFlower:
    actor: str
    flower_id: str
    species: str


@dataclass(frozen=True, slots=True)
class CutFlower:
    actor: str
    flower_id: str


@dataclass(frozen=True, slots=True)
class UseEntity:
    actor: str
    entity_id: str


@dataclass(frozen=True, slots=True)
class ReleaseEntity:
    actor: str
    entity_id: str


@dataclass(frozen=True, slots=True)
class MoveEntity:
    """Move the actor itself, or a carrier it is using (the actor rides along)."""

    actor: str
    entity_id: str
    to: Position


@dataclass(frozen=True, slots=True)
class TransferItems:
    actor: str
    source: str
    target: str
    item: str
    quantity: int


type Command = (
    PlaceOrder
    | CancelOrder
    | PlantFlower
    | CutFlower
    | UseEntity
    | ReleaseEntity
    | MoveEntity
    | TransferItems
)

# --- timed events: wait in the market or flower queue until their tick --------


class QueueName(StrEnum):
    MARKET = "market"
    FLOWERS = "flowers"


@dataclass(frozen=True, slots=True)
class OrderExpiry:
    """A resting order ran out of time."""

    queue: ClassVar[QueueName] = QueueName.MARKET
    item: str
    order_id: str


@dataclass(frozen=True, slots=True)
class FlowerGrowth:
    """A flower is ready for its next stage."""

    queue: ClassVar[QueueName] = QueueName.FLOWERS
    flower_id: str


type TimedEvent = OrderExpiry | FlowerGrowth

# --- periodic events: repeat forever in the periodic queue --------------------


@dataclass(frozen=True, slots=True)
class CompostSweep:
    """Dead flowers are cleared away."""


type PeriodicEvent = CompostSweep

# --- notifications: facts reported to the outside, nothing reacts to them -----


@dataclass(frozen=True, slots=True)
class TradeExecuted:
    item: str
    price: int
    quantity: int
    buyer: str
    seller: str


@dataclass(frozen=True, slots=True)
class FlowerDied:
    flower_id: str


type Event = TimedEvent | PeriodicEvent | TradeExecuted | FlowerDied
type Message = Command | Event


@dataclass(frozen=True, slots=True)
class Scheduled:
    """An event planned for a future tick."""

    due: int
    event: TimedEvent
