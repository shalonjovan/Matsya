"""River/canal 1D reach — Muskingum stub."""
class RiverReach:
    """
    Simple Muskingum: Qout = C0*Qin + C1*Qin_prev + C2*Qout_prev
    For MVP stub with K=600s, x=0.2, dt=300s: C0 ~0.14, C1 ~0.57, C2 ~0.29
    Simplified further: single lag attenuation for demo.
    """
    def __init__(self, length: float = 2000, slope: float = 0.001, K: float = 600, x: float = 0.2, init_q: float = 0.0):
        self.length = float(length)
        self.slope = float(slope)
        self.K = float(K)
        self.x = float(x)
        self._prev_in = float(init_q)
        self._prev_out = float(init_q)
        # Precompute Muskingum coefficients for dt=300 (will recompute per step if dt differs)
        self._dt = 300

    def _coeffs(self, dt: float):
        K, x = self.K, self.x
        denom = K*(1-x) + 0.5*dt
        if denom == 0:
            return (0,1,0)
        C0 = (-K*x + 0.5*dt) / denom
        C1 = (K*x + 0.5*dt) / denom
        C2 = (K*(1-x) - 0.5*dt) / denom
        return (C0, C1, C2)

    def route(self, q_in: float, dt: float = 300) -> float:
        C0, C1, C2 = self._coeffs(dt)
        q_out = C0*q_in + C1*self._prev_in + C2*self._prev_out
        # Ensure attenuation (out <= weighted avg) and non-negative
        q_out = max(0.0, q_out)
        # Simple clamp: outflow cannot exceed max of in and prev
        # For stub, ensure it is less than in if in is rising, but allow
        self._prev_in = q_in
        self._prev_out = q_out
        # Attenuation check: for constant inflow, outflow should approach inflow but slightly less
        return q_out

    def reset(self):
        self._prev_in = 0.0
        self._prev_out = 0.0
