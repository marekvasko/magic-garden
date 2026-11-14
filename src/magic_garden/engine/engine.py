"""The engine: collects commands, keeps the event queues, and advances the world tick by tick."""

from magic_garden.engine.evaluator import Evaluation, evaluate
from magic_garden.engine.messages import Command, PeriodicEvent, Scheduled
from magic_garden.engine.queues import MainQueue
from magic_garden.engine.state import State


class Engine:
    def __init__(self, state: State | None = None) -> None:
        self.state = State() if state is None else state
        self.queue = MainQueue()
        self._batch: list[Command] = []

    def ingest(self, command: Command) -> None:
        """Accept a command from a user, AI or NPC; it runs in the next tick."""
        self._batch.append(command)

    def schedule(self, scheduled: Scheduled) -> None:
        """Plan a one-off event."""
        self.queue.schedule(scheduled)

    def every(self, period: int, event: PeriodicEvent) -> None:
        """Fire `event` every `period` ticks, counting from now."""
        self.queue.repeat(event, period, first_due=self.state.tick + period)

    def tick(self) -> Evaluation:
        """Run one tick: s_{t+1} = evaluate(s_t, batched commands, due events)."""
        commands, self._batch = self._batch, []
        events = self.queue.pop_due(self.state.tick)

        evaluation = evaluate(self.state, commands, events)

        self.state = evaluation.state
        for scheduled in evaluation.future:
            self.queue.schedule(scheduled)
        return evaluation
