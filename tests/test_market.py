from magic_garden.engine import Engine, Evaluation, evaluate
from magic_garden.engine.messages import CancelOrder, PlaceOrder, TradeExecuted
from magic_garden.engine.state import Side, State

from helpers import actor, book, entity, world


def buy(who: str, price: int, quantity: int, ttl: int | None = None) -> PlaceOrder:
    return PlaceOrder(who, "rose", Side.BUY, price, quantity, ttl)


def sell(who: str, price: int, quantity: int, ttl: int | None = None) -> PlaceOrder:
    return PlaceOrder(who, "rose", Side.SELL, price, quantity, ttl)


def trades(result: Evaluation) -> list[TradeExecuted]:
    return [event for event in result.immediate if isinstance(event, TradeExecuted)]


def traders() -> State:
    return world(
        actor("ann", coin=100), actor("bob", rose=10), actor("cid", rose=10), actor("dan", coin=100)
    )


def test_resting_order_escrows_its_cost() -> None:
    result = evaluate(traders(), [buy("ann", 7, 2), sell("bob", 9, 3)], [])

    assert entity(result.state, "ann").inventory == {"coin": 86}
    assert entity(result.state, "bob").inventory == {"rose": 7}
    rose = book(result.state, "rose")
    assert [(order.owner, order.price, order.quantity) for order in rose.bids] == [("ann", 7, 2)]
    assert [(order.owner, order.price, order.quantity) for order in rose.asks] == [("bob", 9, 3)]
    assert result.immediate == ()


def test_crossing_orders_trade_at_the_resting_price() -> None:
    result = evaluate(traders(), [sell("bob", 5, 3), buy("ann", 8, 2)], [])

    assert result.immediate == (TradeExecuted("rose", 5, 2, buyer="ann", seller="bob"),)
    assert entity(result.state, "ann").inventory == {"coin": 90, "rose": 2}
    assert entity(result.state, "bob").inventory == {"rose": 7, "coin": 10}
    assert [order.quantity for order in book(result.state, "rose").asks] == [1]


def test_best_price_first_then_oldest() -> None:
    orders = [sell("bob", 6, 1), sell("cid", 5, 1), sell("bob", 5, 1), buy("ann", 6, 3)]

    result = evaluate(traders(), orders, [])

    assert [(trade.seller, trade.price) for trade in trades(result)] == [
        ("cid", 5),
        ("bob", 5),
        ("bob", 6),
    ]


def test_bids_are_matched_highest_first_then_oldest() -> None:
    orders = [buy("ann", 5, 1), buy("dan", 6, 1), buy("ann", 6, 1), sell("bob", 5, 3)]

    result = evaluate(traders(), orders, [])

    assert [(trade.buyer, trade.price) for trade in trades(result)] == [
        ("dan", 6),
        ("ann", 6),
        ("ann", 5),
    ]


def test_unfilled_remainder_rests_in_the_book() -> None:
    result = evaluate(traders(), [sell("bob", 5, 1), buy("ann", 5, 4)], [])

    rose = book(result.state, "rose")
    assert rose.asks == ()
    assert [order.quantity for order in rose.bids] == [3]
    assert entity(result.state, "ann").inventory == {"coin": 80, "rose": 1}


def test_order_without_funds_is_rejected() -> None:
    result = evaluate(traders(), [buy("bob", 5, 1), sell("ann", 5, 1), buy("ann", 0, 1)], [])

    assert [rejection.reason for rejection in result.rejections] == [
        "price and quantity must be positive",
        "bob does not have enough coin",
        "ann does not have enough rose",
    ]
    assert entity(result.state, "bob").inventory == {"rose": 10}


def test_cancel_returns_the_escrow() -> None:
    placed = evaluate(traders(), [buy("ann", 7, 2)], [])
    order_id = book(placed.state, "rose").bids[0].id

    result = evaluate(placed.state, [CancelOrder("ann", "rose", order_id)], [])

    assert entity(result.state, "ann").inventory == {"coin": 100}
    assert book(result.state, "rose").bids == ()


def test_only_the_owner_may_cancel() -> None:
    placed = evaluate(traders(), [buy("ann", 7, 2)], [])
    order_id = book(placed.state, "rose").bids[0].id

    commands = [CancelOrder("bob", "rose", order_id), CancelOrder("ann", "rose", "nope")]
    result = evaluate(placed.state, commands, [])

    assert sorted(rejection.reason for rejection in result.rejections) == [
        "not your order",
        "order not found",
    ]
    assert len(book(result.state, "rose").bids) == 1


def test_order_expires_after_its_ttl() -> None:
    engine = Engine(traders())
    engine.ingest(sell("bob", 9, 4, ttl=2))

    engine.tick()
    assert len(engine.queue.market) == 1
    assert entity(engine.state, "bob").inventory == {"rose": 6}
    engine.tick()
    assert len(book(engine.state, "rose").asks) == 1
    engine.tick()

    assert book(engine.state, "rose").asks == ()
    assert entity(engine.state, "bob").inventory == {"rose": 10}


def test_expiry_of_a_filled_order_does_nothing() -> None:
    engine = Engine(traders())
    engine.ingest(sell("bob", 5, 2, ttl=1))
    engine.ingest(buy("ann", 5, 2))
    engine.tick()

    result = engine.tick()

    assert len(engine.queue.market) == 0
    assert result.rejections == ()
    assert entity(engine.state, "bob").inventory == {"rose": 8, "coin": 10}
