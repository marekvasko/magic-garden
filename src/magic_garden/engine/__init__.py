"""The Magic Garden game engine.

engine = Engine(initial_state)
engine.ingest(command)        # any number of times
evaluation = engine.tick()    # s_{t+1} = evaluate(s_t, commands, events)
"""

from magic_garden.engine.engine import Engine
from magic_garden.engine.evaluator import Evaluation, evaluate
from magic_garden.engine.resolver import Rejection
from magic_garden.engine.state import State

__all__ = ["Engine", "Evaluation", "Rejection", "State", "evaluate"]
