"""
scheduler.py -- acionamento adaptativo do drift-detect por device.

Em vez de um cron fixo, mantem uma media movel exponencial (EWMA) da taxa
de hazard de drift por dispositivo e interpola o intervalo de verificacao
entre um maximo (sem evidencia de drift -- poupa queries) e um minimo
(dispositivo historicamente instavel -- verifica com mais frequencia).

Heuristica declarada como tal, nao uma politica otima: o ganho medido em
avaliacao e condicional a heterogeneidade real na taxa de drift entre
dispositivos -- ver docs/architecture.md.
"""
from typing import Dict


class AdaptiveHazardScheduler:
    def __init__(self, min_interval=5, max_interval=240, alpha=0.3, prior_hazard=0.02):
        self.min_interval, self.max_interval = min_interval, max_interval
        self.alpha, self.prior_hazard = alpha, prior_hazard
        self.hazard: Dict[str, float] = {}

    def record(self, device: str, drift_detected: bool) -> None:
        prev = self.hazard.get(device, self.prior_hazard)
        obs = 1.0 if drift_detected else 0.0
        self.hazard[device] = self.alpha * obs + (1 - self.alpha) * prev

    def next_interval(self, device: str) -> int:
        h = max(0.0, min(1.0, self.hazard.get(device, self.prior_hazard)))
        # interpolacao linear: h=0 -> max_interval, h=1 -> min_interval
        interval = self.min_interval + (self.max_interval - self.min_interval) * (1 - h)
        return int(round(interval))
