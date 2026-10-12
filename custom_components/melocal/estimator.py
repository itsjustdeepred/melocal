"""Electrical power estimate from the Ecodan energy counter."""

from __future__ import annotations

from collections import deque

COUNTER_STEP_KWH = 0.1
# Average over the counter steps of the last minutes. A single 0.1 kWh step
# seen at 30 s polling granularity swings the estimate by a factor of 2-4.
WINDOW_S = 600


class EnergyRateEstimator:
    """Average electrical power from a cumulative 0.1 kWh counter.

    Power is the mean over the counter steps seen in the last WINDOW_S seconds
    (at least the last two steps). While the counter stands still the power can
    be at most one step over the elapsed time, so the estimate decays towards
    zero instead of freezing.
    """

    def __init__(self) -> None:
        # (time, value) at each observed counter step; the first is the sync point.
        self._steps: deque[tuple[float, float]] = deque()
        self._synced = False
        self.power: float | None = None

    def update(self, value: float, now: float) -> float | None:
        last = self._steps[-1] if self._steps else None
        if last is None or value < last[1]:
            self._steps.clear()
            self._steps.append((now, value))
            self._synced = False
            self.power = None
            return None
        if value > last[1]:
            if not self._synced:
                # The first step only tells us where inside a step we started.
                self._steps.clear()
                self._synced = True
            self._steps.append((now, value))
            while len(self._steps) > 2 and self._steps[1][0] <= now - WINDOW_S:
                self._steps.popleft()
            if len(self._steps) >= 2:
                (t0, v0), (t1, v1) = self._steps[0], self._steps[-1]
                if t1 > t0:
                    self.power = round(round(v1 - v0, 3) * 3_600_000 / (t1 - t0))
        elif self._synced and self.power is not None and now > last[0]:
            self.power = min(self.power, round(COUNTER_STEP_KWH * 3_600_000 / (now - last[0])))
        return self.power
