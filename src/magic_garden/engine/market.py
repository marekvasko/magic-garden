"""The market: one limit order book per item, matched by price-time priority.

Placing an order puts its full cost in escrow: coins for a buy, the items for
a sell. Trades happen at the price of the order that was resting in the book.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from magic_garden.engine.messages import (
    CancelOrder,
    OrderExpiry,
    PlaceOrder,
    Scheduled,
    TradeExecuted,
)
from magic_garden.engine.state import (
    COIN,
    Entity,
    Order,
    OrderBook,
    Rejected,
    Side,
    State,
    Value,
    book_key,
    entity_key,
    expect,
)
from magic_garden.engine.transaction import Transaction

# --- matching: pure functions on an order book ---------------------------------


@dataclass(frozen=True, slots=True)
class Fill:
    """Part of an incoming order traded against one resting order."""

    maker: str
    price: int
    quantity: int


def match_order(book: OrderBook, taker: Order) -> tuple[OrderBook, tuple[Fill, ...]]:
    """Trade `taker` against the opposite side, then rest whatever is left of it."""
    buying = taker.side is Side.BUY
    opposite = list(book.asks if buying else book.bids)
    fills: list[Fill] = []
    remaining = taker.quantity

    while remaining and opposite and _crosses(taker, opposite[0]):
        maker = opposite[0]
        quantity = min(remaining, maker.quantity)
        fills.append(Fill(maker.owner, maker.price, quantity))
        remaining -= quantity
        if quantity == maker.quantity:
            del opposite[0]
        else:
            opposite[0] = replace(maker, quantity=maker.quantity - quantity)

    own = book.bids if buying else book.asks
    if remaining:
        own = _rest(own, replace(taker, quantity=remaining))
    bids, asks = (own, tuple(opposite)) if buying else (tuple(opposite), own)
    return replace(book, bids=bids, asks=asks), tuple(fills)


def _crosses(taker: Order, maker: Order) -> bool:
    if taker.side is Side.BUY:
        return taker.price >= maker.price
    return taker.price <= maker.price


def _rest(queue: tuple[Order, ...], order: Order) -> tuple[Order, ...]:
    """Insert behind every order with a price at least as good: price, then time."""

    def is_worse(resting: Order) -> bool:
        if order.side is Side.BUY:
            return resting.price < order.price
        return resting.price > order.price

    index = next((i for i, resting in enumerate(queue) if is_worse(resting)), len(queue))
    return (*queue[:index], order, *queue[index:])


def _find(book: OrderBook, order_id: str) -> Order | None:
    return next((order for order in (*book.bids, *book.asks) if order.id == order_id), None)


# --- handlers ------------------------------------------------------------------


def place_order(state: State, command: PlaceOrder) -> Transaction:
    """Escrow the order's cost, trade what crosses, rest the remainder."""
    if command.price < 1 or command.quantity < 1:
        raise Rejected("price and quantity must be positive")
    item, actor = command.item, command.actor

    def new_order(book: OrderBook) -> tuple[OrderBook, Order]:
        order_id = f"{item}-{book.next_order_number}"
        order = Order(order_id, actor, command.side, command.price, command.quantity)
        return replace(book, next_order_number=book.next_order_number + 1), order

    # Look at the book to learn whose inventories the trades will touch.
    seen_book = state.get(book_key(item)) or OrderBook(item)
    book, order = new_order(expect(seen_book, OrderBook))
    book, fills = match_order(book, order)
    owners = dict.fromkeys([actor, *(fill.maker for fill in fills)])
    keys = (book_key(item), *(entity_key(owner) for owner in owners))

    def modify(inputs: Sequence[Value | None]) -> Sequence[Value | None]:
        book, order = new_order(expect(inputs[0] or OrderBook(item), OrderBook))
        entities = {entity.id: entity for entity in (expect(v, Entity) for v in inputs[1:])}
        book, fills = match_order(book, order)
        _settle(entities, item, order, fills)
        return [book, *entities.values()]

    buying = command.side is Side.BUY
    trades = tuple(
        TradeExecuted(
            item,
            fill.price,
            fill.quantity,
            buyer=actor if buying else fill.maker,
            seller=fill.maker if buying else actor,
        )
        for fill in fills
    )
    rests = _find(book, order.id) is not None
    expiry = (
        (Scheduled(state.tick + command.ttl, OrderExpiry(item, order.id)),)
        if rests and command.ttl is not None
        else ()
    )
    return Transaction(command, keys, keys, modify, immediate=trades, future=expiry)


def _settle(entities: dict[str, Entity], item: str, taker: Order, fills: Sequence[Fill]) -> None:
    """Escrow the taker's whole order, then pay out each fill to both parties."""

    def give(owner: str, what: str, amount: int) -> None:
        entities[owner] = entities[owner].add(what, amount)

    if taker.side is Side.BUY:
        give(taker.owner, COIN, -taker.price * taker.quantity)
        for fill in fills:
            give(taker.owner, item, fill.quantity)
            give(taker.owner, COIN, (taker.price - fill.price) * fill.quantity)  # price improvement
            give(fill.maker, COIN, fill.price * fill.quantity)
    else:
        give(taker.owner, item, -taker.quantity)
        for fill in fills:
            give(taker.owner, COIN, fill.price * fill.quantity)
            give(fill.maker, item, fill.quantity)


def cancel_order(state: State, command: CancelOrder) -> Transaction:
    """Take the actor's own order out of the book and return its escrow."""
    transaction = _remove_order(state, command, command.item, command.order_id)
    if transaction is None:
        raise Rejected("order not found")
    return transaction


def expire_order(state: State, event: OrderExpiry) -> Transaction | None:
    """Like a cancel, unless the order was already filled or cancelled."""
    return _remove_order(state, event, event.item, event.order_id)


def _remove_order(
    state: State, cause: CancelOrder | OrderExpiry, item: str, order_id: str
) -> Transaction | None:
    seen_book = state.get(book_key(item))
    seen_order = _find(seen_book, order_id) if isinstance(seen_book, OrderBook) else None
    if seen_order is None:
        return None
    keys = (book_key(item), entity_key(seen_order.owner))

    def modify(inputs: Sequence[Value | None]) -> Sequence[Value | None]:
        book = expect(inputs[0], OrderBook)
        owner = expect(inputs[1], Entity)
        order = expect(_find(book, order_id), Order)
        if isinstance(cause, CancelOrder) and cause.actor != owner.id:
            raise Rejected("not your order")
        book = replace(
            book,
            bids=tuple(bid for bid in book.bids if bid.id != order_id),
            asks=tuple(ask for ask in book.asks if ask.id != order_id),
        )
        if order.side is Side.BUY:
            return [book, owner.add(COIN, order.price * order.quantity)]
        return [book, owner.add(item, order.quantity)]

    return Transaction(cause, keys, keys, modify)
