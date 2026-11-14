from magic_garden.engine import evaluate
from magic_garden.engine.messages import MoveEntity, ReleaseEntity, TransferItems, UseEntity
from magic_garden.engine.state import Entity, EntityKind, Position, State

from helpers import HOME, actor, entity, world

FIELD = Position(5, 2)


def yard() -> State:
    return world(
        actor("ann", rose=3),
        actor("bob"),
        Entity("truck", EntityKind.TRUCK, HOME),
        Entity("sled", EntityKind.SLED, FIELD),
    )


def test_use_slot_holds_one_actor() -> None:
    result = evaluate(yard(), [UseEntity("ann", "truck"), UseEntity("bob", "truck")], [])

    assert entity(result.state, "truck").used_by == "ann"
    assert [rejection.reason for rejection in result.rejections] == ["truck is already in use"]


def test_release_frees_the_slot() -> None:
    commands = [
        UseEntity("ann", "truck"),
        ReleaseEntity("bob", "truck"),
        ReleaseEntity("ann", "truck"),
        UseEntity("bob", "truck"),
    ]

    result = evaluate(yard(), commands, [])

    assert entity(result.state, "truck").used_by == "bob"
    assert [rejection.reason for rejection in result.rejections] == ["bob is not using truck"]


def test_use_rules() -> None:
    result = evaluate(yard(), [UseEntity("ann", "sled"), UseEntity("ann", "bob")], [])

    assert sorted(rejection.reason for rejection in result.rejections) == [
        "only carriers can be used",
        "sled is too far away",
    ]


def test_carrier_moves_goods_with_its_user() -> None:
    commands = [
        UseEntity("ann", "truck"),
        TransferItems("ann", "ann", "truck", "rose", 2),
        MoveEntity("ann", "truck", FIELD),
        TransferItems("ann", "truck", "sled", "rose", 2),
    ]

    result = evaluate(yard(), commands, [])

    assert result.rejections == ()
    assert entity(result.state, "ann").position == FIELD
    assert entity(result.state, "truck").position == FIELD
    assert entity(result.state, "truck").inventory == {}
    assert entity(result.state, "sled").inventory == {"rose": 2}
    assert entity(result.state, "ann").inventory == {"rose": 1}


def test_moving_a_carrier_needs_its_use_slot() -> None:
    result = evaluate(yard(), [MoveEntity("ann", "truck", FIELD)], [])

    assert [rejection.reason for rejection in result.rejections] == ["ann is not using truck"]
    assert entity(result.state, "truck").position == HOME


def test_transfer_rules() -> None:
    commands = [
        TransferItems("bob", "ann", "bob", "rose", 1),
        TransferItems("ann", "ann", "sled", "rose", 1),
        TransferItems("ann", "ann", "bob", "rose", 9),
        TransferItems("ann", "ann", "bob", "rose", 0),
        TransferItems("ann", "ann", "ann", "rose", 1),
    ]

    result = evaluate(yard(), commands, [])

    assert sorted(rejection.reason for rejection in result.rejections) == [
        "ann does not have enough rose",
        "bob does not control ann",
        "quantity must be positive",
        "sled is too far away",
        "source and target must differ",
    ]
    assert entity(result.state, "ann").inventory == {"rose": 3}
