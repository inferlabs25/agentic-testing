"""
SessionBuilder — groups raw events from the database into a clean,
structured session object ready for AI analysis.
"""

from typing import List, Optional
from sqlalchemy.orm import Session as DBSession
from models import RecordingSession, Event
from schemas import SessionStep, SessionDetail


class SessionBuilder:
    """Converts raw captured events into structured session steps."""

    # Event types that represent user actions (as opposed to metadata events)
    ACTION_TYPES = {"click", "fill", "input", "change", "submit", "navigate", "select"}

    def __init__(self, db: DBSession):
        self.db = db

    def build(self, session_id: str) -> Optional[SessionDetail]:
        """
        Build a structured session from raw events.
        Groups navigation + action events into numbered steps,
        attaching the most recent DOM snapshot and screenshot to each step.
        """
        recording = (
            self.db.query(RecordingSession)
            .filter(RecordingSession.session_id == session_id)
            .first()
        )
        if not recording:
            return None

        events = (
            self.db.query(Event)
            .filter(Event.session_id == session_id)
            .order_by(Event.timestamp.asc())
            .all()
        )

        if not events:
            return SessionDetail(
                session_id=session_id,
                name=recording.name,
                url=recording.url,
                status=recording.status,
                steps=[],
                created_at=recording.created_at,
            )

        steps = self._group_into_steps(events)

        return SessionDetail(
            session_id=session_id,
            name=recording.name,
            url=recording.url or (events[0].url if events else None),
            status=recording.status,
            steps=steps,
            created_at=recording.created_at,
        )

    def _group_into_steps(self, events: List[Event]) -> List[SessionStep]:
        """
        Walk through events chronologically.
        Each user action becomes a step, inheriting the latest
        DOM snapshot, screenshot, and network calls seen so far.
        """
        steps: List[SessionStep] = []
        step_index = 0

        current_dom: Optional[str] = None
        current_screenshot: Optional[str] = None
        current_url: Optional[str] = None
        network_buffer: List[dict] = []

        for event in events:
            # Track latest contextual data
            if event.dom_snapshot:
                current_dom = event.dom_snapshot
            if event.screenshot_b64:
                current_screenshot = event.screenshot_b64
            if event.url:
                current_url = event.url
            if event.event_type == "network" and event.network_data:
                network_buffer.append(event.network_data)

            # Only create a step for user actions
            if event.event_type in self.ACTION_TYPES:
                step_index += 1
                steps.append(
                    SessionStep(
                        step_index=step_index,
                        url=current_url,
                        action=event.event_type,
                        selector=event.selector,
                        value=event.value,
                        dom_snapshot=current_dom,
                        screenshot_b64=current_screenshot,
                        network_calls=list(network_buffer),
                    )
                )
                # Reset network buffer after attaching to a step
                network_buffer = []

        return steps

    def get_latest_screenshot(self, session_id: str) -> Optional[str]:
        """Return the most recent screenshot for a session."""
        event = (
            self.db.query(Event)
            .filter(
                Event.session_id == session_id,
                Event.screenshot_b64.isnot(None),
            )
            .order_by(Event.timestamp.desc())
            .first()
        )
        return event.screenshot_b64 if event else None

    def get_all_network_calls(self, session_id: str) -> List[dict]:
        """Return all network calls captured during a session."""
        events = (
            self.db.query(Event)
            .filter(
                Event.session_id == session_id,
                Event.event_type == "network",
            )
            .order_by(Event.timestamp.asc())
            .all()
        )
        return [e.network_data for e in events if e.network_data]
