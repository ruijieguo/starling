"""AffectVector + salience formula (M0.1).

salience(formula) here is a *helper*; the Statement.salience field is the
materialized value computed and written by Bus at write time (M0.2+).
This method exposes the §3.9 formula in pure form for tests and offline
scoring."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class AffectVector:
    valence: float        # -1..+1
    arousal: float        #  0..1
    dominance: float      # -1..+1
    novelty: float        #  0..1
    stakes: float         #  0..1

    def salience(self, surprise_decay: float = 1.0) -> float:
        return (
            (0.4 + 0.6 * abs(self.valence))
            * (0.4 + 0.6 * self.arousal)
            * (0.3 + 0.7 * self.novelty)
            * (0.3 + 0.7 * self.stakes)
            * (0.6 + 0.4 * surprise_decay)
        )
