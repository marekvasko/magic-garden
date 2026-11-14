"""Event queues: independent market, flower and periodic queues behind one main queue."""

import heapq
from dataclasses import dataclass
from itertools import count

from magic_garden.engine.messages import Event, PeriodicEvent, QueueName, Scheduled, TimedEvent

type Entry[T] = tuple[int, int, T]
"""(due tick, insertion number, item) - the first two give a total firing order."""


class EventQueue[T]:
    """Items waiting for their due tick."""

    def __init__(self) -> None:
        self._heap: list[Entry[T]] = []

    def __len__(self) -> int:
        return len(self._heap)

    def push(self, due: int, number: int, item: T) -> None:
        heapq.heappush(self._heap, (due, number, item))

    def peek_due(self) -> int:
        """The due tick of the earliest entry; the queue must not be empty."""
        return self._heap[0][0]

    def pop_due(self, now: int) -> list[Entry[T]]:
        """Remove and return every entry due at or before `now`."""
        due: list[Entry[T]] = []
        while self._heap and self._heap[0][0] <= now:
            due.append(heapq.heappop(self._heap))
        return due


@dataclass(frozen=True, slots=True)
class Repeating:
    event: PeriodicEvent
    period: int


class MainQueue:
    """The engine's single source of due events, fed by three independent queues."""

    def __init__(self) -> None:
        self.market = EventQueue[TimedEvent]()
        self.flowers = EventQueue[TimedEvent]()
        self.periodic = EventQueue[Repeating]()
        self._numbers = count()

    def schedule(self, scheduled: Scheduled) -> None:
        """Plan a one-off event; it goes to the queue its type belongs to."""
        match scheduled.event.queue:
            case QueueName.MARKET:
                queue = self.market
            case QueueName.FLOWERS:
                queue = self.flowers
        queue.push(scheduled.due, next(self._numbers), scheduled.event)

    def repeat(self, event: PeriodicEvent, period: int, first_due: int) -> None:
        """Fire `event` at `first_due` and then every `period` ticks."""
        if period < 1:
            raise ValueError("period must be at least one tick")
        self.periodic.push(first_due, next(self._numbers), Repeating(event, period))

    def pop_due(self, now: int) -> list[Event]:
        """Remove and return all events due at or before `now`, in firing order."""
        due: list[Entry[Event]] = [*self.market.pop_due(now), *self.flowers.pop_due(now)]
        for at, number, repeating in self.periodic.pop_due(now):
            due.append((at, number, repeating.event))
            self.periodic.push(at + repeating.period, next(self._numbers), repeating)
        due.sort(key=lambda entry: entry[:2])
        return [event for _, _, event in due]

    def next_due(self) -> int | None:
        """The tick of the earliest waiting event, if any."""
        queues = (self.market, self.flowers, self.periodic)
        return min((queue.peek_due() for queue in queues if queue), default=None)
