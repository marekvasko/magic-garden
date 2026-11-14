import pytest

from magic_garden.engine.messages import CompostSweep, FlowerGrowth, OrderExpiry, Scheduled
from magic_garden.engine.queues import MainQueue


def test_events_go_to_their_own_queue() -> None:
    queue = MainQueue()
    queue.schedule(Scheduled(3, OrderExpiry("rose", "rose-1")))
    queue.schedule(Scheduled(3, FlowerGrowth("f1")))
    queue.repeat(CompostSweep(), period=10, first_due=10)

    assert (len(queue.market), len(queue.flowers), len(queue.periodic)) == (1, 1, 1)


def test_pop_due_merges_queues_by_tick_then_scheduling_order() -> None:
    queue = MainQueue()
    late_growth, expiry, growth = (
        FlowerGrowth("late"),
        OrderExpiry("rose", "rose-1"),
        FlowerGrowth("f"),
    )
    queue.schedule(Scheduled(2, late_growth))
    queue.schedule(Scheduled(1, expiry))
    queue.schedule(Scheduled(1, growth))
    queue.schedule(Scheduled(5, FlowerGrowth("not yet")))

    assert queue.pop_due(now=2) == [expiry, growth, late_growth]
    assert queue.pop_due(now=2) == []
    assert queue.next_due() == 5


def test_periodic_events_repeat() -> None:
    queue = MainQueue()
    queue.repeat(CompostSweep(), period=3, first_due=3)

    fired = [tick for tick in range(10) if queue.pop_due(tick)]

    assert fired == [3, 6, 9]


def test_period_must_be_positive() -> None:
    with pytest.raises(ValueError):
        MainQueue().repeat(CompostSweep(), period=0, first_due=0)


def test_next_due_of_empty_queue() -> None:
    assert MainQueue().next_due() is None
