from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Weights
from app.optimization.baseline import BASELINES
from app.optimization.params import GAParams

Method = Literal["ga", "greedy", "greedy_cost_aware", "randomized_greedy", "random_feasible"]
assert set(BASELINES) | {"ga"} == set(Method.__args__)  # keep the API list in sync with the engine


class GAParamsIn(BaseModel):
    """GA parameters; defaults are the PRD's recommended values."""

    population_size: int = Field(default=100, ge=2, le=1000)
    generations: int = Field(default=300, ge=0, le=5000)
    crossover_rate: float = Field(default=0.80, ge=0, le=1)
    mutation_rate: float = Field(default=0.10, ge=0, le=1)
    elite_count: int = Field(default=5, ge=0)
    tournament_size: int = Field(default=3, ge=1)
    seed: int = 42
    mutation_ops: int | None = Field(default=None, ge=1)
    crossover_type: Literal["uniform", "two_point"] = "uniform"
    repair: bool = True
    repair_attempts: int = Field(default=100, ge=0)
    repair_mode: Literal["best", "random"] = "best"
    early_stopping: bool = True
    patience: int = Field(default=50, ge=1)
    target_penalty: float | None = None

    def to_params(self) -> GAParams:
        params = GAParams(**self.model_dump())
        params.validate()
        return params


class WeightsIn(BaseModel):
    hard: float = Field(default=Weights.hard, ge=0)
    consecutive: float = Field(default=Weights.consecutive, ge=0)
    gap: float = Field(default=Weights.gap, ge=0)
    distribution: float = Field(default=Weights.distribution, ge=0)
    slot_pref: float = Field(default=Weights.slot_pref, ge=0)
    room_util: float = Field(default=Weights.room_util, ge=0)


class RunRequest(BaseModel):
    session_id: int
    method: Method = "ga"
    params: GAParamsIn = GAParamsIn()
    weights: WeightsIn = WeightsIn()


class BaselineRequest(BaseModel):
    session_id: int
    method: Literal["greedy", "greedy_cost_aware", "randomized_greedy", "random_feasible"] = "greedy"
    seed: int = 42
    weights: WeightsIn = WeightsIn()


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    method: str
    status: str
    seed: int | None
    params: dict
    weights: dict
    dataset_hash: str
    current_generation: int
    total_generations: int
    initial_penalty: float | None
    best_penalty: float | None
    best_fitness: float | None
    hard_violations: int | None
    generations_run: int | None
    stopped_by: str | None
    runtime_seconds: float | None
    timetable_id: int | None
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class ProgressOut(BaseModel):
    run_id: int
    status: str
    current_generation: int
    total_generations: int
    best_penalty: float | None
    best_fitness: float | None
    timetable_id: int | None
    error: str | None
    history: list[dict]
