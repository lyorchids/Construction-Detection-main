from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

VIOLATION_MIN_FRAMES = 10
RECOVER_FRAMES = 15
COOLDOWN_SECONDS = 30


class ViolationState:
    """State machine for a single violation type of one person."""

    SAFE = 'safe'
    WARN = 'warn'
    ACTIVE = 'active'
    COOLDOWN = 'cooldown'

    def __init__(self) -> None:
        self.state = self.SAFE
        self.consecutive_violation_frames = 0
        self.consecutive_safe_frames = 0
        self.last_trigger_time = 0.0
        self.trigger_count = 0
        self.best_bbox: list[float] = [0, 0, 0, 0]
        self.best_conf: float = 0.0

    def update(
        self,
        is_violating: bool,
        bbox: list[float] | None = None,
        confidence: float = 0.0,
        timestamp: float = 0.0,
    ) -> bool:
        """Update state and return True if a NEW violation should be emitted."""
        triggered = False

        if is_violating:
            self.consecutive_violation_frames += 1
            self.consecutive_safe_frames = 0

            if bbox is not None:
                if confidence > self.best_conf:
                    self.best_bbox = bbox
                    self.best_conf = confidence

            if self.state == self.SAFE:
                if self.consecutive_violation_frames >= VIOLATION_MIN_FRAMES:
                    self.state = self.WARN
                    self.consecutive_violation_frames = 0

            elif self.state == self.WARN:
                self.state = self.ACTIVE
                self.last_trigger_time = timestamp
                self.trigger_count += 1
                triggered = True

            elif self.state == self.COOLDOWN:
                if timestamp - self.last_trigger_time > COOLDOWN_SECONDS:
                    self.state = self.ACTIVE
                    self.last_trigger_time = timestamp
                    self.trigger_count += 1
                    triggered = True

        else:
            self.consecutive_safe_frames += 1
            self.consecutive_violation_frames = 0

            if self.state in (self.WARN, self.ACTIVE):
                if self.consecutive_safe_frames >= RECOVER_FRAMES:
                    self.state = self.COOLDOWN
                    self.consecutive_safe_frames = 0
                    self.best_bbox = [0, 0, 0, 0]
                    self.best_conf = 0.0

            elif self.state == self.COOLDOWN:
                if timestamp - self.last_trigger_time > COOLDOWN_SECONDS:
                    self.state = self.SAFE
                    self.consecutive_safe_frames = 0

        return triggered


class PersonStateManager:
    """Manages violation state machines for all tracked persons."""

    def __init__(self) -> None:
        self._persons: dict[int, dict[str, ViolationState]] = {}
        self._person_safe_frames: dict[int, int] = {}

    def get_or_create(self, track_id: int) -> dict[str, ViolationState]:
        if track_id not in self._persons:
            self._persons[track_id] = {}
        return self._persons[track_id]

    def update_violation(
        self,
        track_id: int,
        violation_type: str,
        is_violating: bool,
        bbox: list[float] | None = None,
        confidence: float = 0.0,
        timestamp: float = 0.0,
    ) -> bool:
        states = self.get_or_create(track_id)
        if violation_type not in states:
            states[violation_type] = ViolationState()
        return states[violation_type].update(
            is_violating, bbox, confidence, timestamp,
        )

    def get_active_violations(
        self,
        timestamp: float,
    ) -> list[dict[str, Any]]:
        result = []
        for track_id, states in self._persons.items():
            for vtype, vs in states.items():
                if vs.state in (ViolationState.ACTIVE, ViolationState.WARN):
                    result.append({
                        'track_id': track_id,
                        'type': vtype,
                        'state': vs.state,
                        'bbox': vs.best_bbox,
                        'confidence': vs.best_conf,
                    })
        return result

    def clean_stale(self, active_track_ids: set[int]) -> None:
        stale = set(self._persons.keys()) - active_track_ids
        for tid in stale:
            del self._persons[tid]

    def get_active_violation_counts(self, timestamp: float) -> dict[str, int]:
        """Return {violation_type: unique_person_count} for currently active violations."""
        counts: dict[str, int] = {}
        for track_id, states in self._persons.items():
            for vtype, vs in states.items():
                if vs.state in (ViolationState.ACTIVE, ViolationState.WARN):
                    counts[vtype] = counts.get(vtype, 0) + 1
        return counts

    def mark_absent_violations(
        self,
        active_track_ids: set[int],
        present_vtypes: set[str],
        timestamp: float,
    ) -> None:
        for tid in active_track_ids:
            states = self._persons.get(tid, {})
            for stored_vtype in list(states.keys()):
                if stored_vtype not in present_vtypes:
                    self.update_violation(tid, stored_vtype, False, timestamp=timestamp)

    def reset(self) -> None:
        self._persons.clear()
        self._person_safe_frames.clear()
