"""WaterBody storage with broad-crested weir outflow."""
import math

class WaterBody:
    """
    Prismatic storage: volume = area * max(0, stage - bed)
    outflow = C * L * (stage - crest)^(3/2) if stage > crest else 0
    bed = crest - depth (default depth 2m, so bed = crest-2)
    """
    def __init__(self, area_m2: float, crest: float, stage: float = None, crest_width: float = 10.0, C: float = 1.7, depth: float = 2.0):
        self.area_m2 = float(area_m2)
        self.crest = float(crest)
        self.crest_width = float(crest_width)
        self.C = float(C)
        self.bed = self.crest - depth
        # initial stage defaults to crest (empty: stage = bed, but we start at crest for dry? Use bed if not given)
        if stage is None:
            self.stage = self.bed
        else:
            self.stage = float(stage)
        self.volume = max(0.0, self.area_m2 * max(0.0, self.stage - self.bed))
        self._inflow_buffer = 0.0

    def inflow(self, q_m3s: float):
        """Add inflow to buffer (m3/s), will be added on step."""
        self._inflow_buffer += float(q_m3s)

    def step(self, dt: float) -> float:
        """Advance dt seconds, return outflow (m3/s)."""
        # add inflow volume
        inflow_vol = self._inflow_buffer * dt
        self._inflow_buffer = 0.0
        self.volume += inflow_vol
        # update stage from volume
        if self.volume <= 0:
            self.stage = self.bed
            self.volume = 0
            return 0.0
        self.stage = self.bed + self.volume / self.area_m2
        # compute outflow if above crest
        if self.stage <= self.crest:
            return 0.0
        head = self.stage - self.crest
        outflow = self.C * self.crest_width * (head ** 1.5)
        # limit outflow to not drain more than available above crest in this dt?
        # simple: outflow volume = outflow * dt, but don't drain below crest
        outflow_vol = outflow * dt
        max_drain_vol = self.area_m2 * head
        if outflow_vol > max_drain_vol:
            outflow_vol = max_drain_vol
            outflow = outflow_vol / dt
        self.volume -= outflow_vol
        self.stage = self.bed + self.volume / self.area_m2
        return outflow

    def get_state(self):
        return {"area_m2": self.area_m2, "crest": self.crest, "stage": self.stage, "volume": self.volume, "bed": self.bed}
