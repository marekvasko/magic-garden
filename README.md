# Magic Garden

A flower growing and trading game. This repository currently holds its **engine**
(`magic_garden.engine`); the other parts of the game will live beside it as
further subpackages.

## The engine

The engine advances the world one tick at a time, strictly as

    s_{t+1} = evaluate(s_t, commands, events)

```
 user / AI / NPC                market queue   flower queue   periodic queue
       │ ingest                        └────────────┬──────────────┘
       ▼                                            ▼
  command batch                                 main queue
       └───────────────┬────────────────────────────┘ due events
                       ▼
        ┌─ evaluate(state, commands, events) ───────────────┐
        │  dispatch: each message → its handler             │
        │  handler:  → Transaction(reads, writes, modify)   │◄─┐ deferred messages,
        │  resolver: validate → deconflict → atomic commit  │──┘ immediate events
        └──────────────────────┬────────────────────────────┘
                               ▼
        new state · immediate events · future events (→ queues) · rejections
```

| Module           | Role                                                                    |
|------------------|-------------------------------------------------------------------------|
| `engine.py`      | `Engine`: ingests and batches commands, owns the queues, runs ticks     |
| `queues.py`      | market, flower and periodic queues behind one `MainQueue`               |
| `evaluator.py`   | the pure `evaluate` function and the message → handler dispatch         |
| `transaction.py` | `Transaction`: keys read, keys written, `modify(inputs) -> outputs`     |
| `resolver.py`    | validates, deconflicts and atomically commits transactions              |
| `state.py`       | the state (an immutable key-value store) and the objects in it          |
| `messages.py`    | all commands and events                                                 |
| `market.py`      | limit order books with price-time priority matching                     |
| `flowers.py`     | planting, growth, cutting, dying                                        |
| `entities.py`    | actors and carriers (truck, sled, wheelbarrow): use slot, move, transfer |

### How a tick is resolved

Handlers build their transactions from a snapshot of the state. The resolver
walks them in order; a transaction touching a key already claimed by an earlier
one in the same round is *deferred* - its message is dispatched again, on fresh
state, in the next round. So the result is always the same as running the
messages one after another, due events first, then commands in ingest order.
A transaction whose `modify` raises `Rejected` is reported and changes nothing.

### Game rules in short

- **Market** - placing an order escrows its cost (coins for a buy, items for a
  sell). Crossing orders trade at the resting order's price, best price first,
  oldest first. Orders can be cancelled or given a time to live.
- **Flowers** - a seed grows to a sprout and then a bloom. Cutting a bloom puts
  one flower in the owner's inventory; the plant regrows, but survives only a
  limited number of cuts and then dies. A periodic compost sweep removes the dead.
- **Entities** - actors and carriers have a position and an inventory. A carrier
  has one use slot; the actor holding it can drive it (riding along) and unload it.

## Usage

```python
from magic_garden.engine import Engine, State
from magic_garden.engine.messages import CompostSweep, PlaceOrder
from magic_garden.engine.state import Entity, EntityKind, Position, Side, entity_key

ann = Entity("ann", EntityKind.ACTOR, Position(0, 0), {"coin": 100})
engine = Engine(State(values={entity_key("ann"): ann}))
engine.every(20, CompostSweep())

engine.ingest(PlaceOrder("ann", "rose", Side.BUY, price=5, quantity=2))
evaluation = engine.tick()  # .state, .immediate, .future, .rejections
```

## Development

```sh
uv sync
uv run pytest
uv run pyright        # strict
uv run ruff check && uv run ruff format --check
```
