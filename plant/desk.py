"""Operator desk rules (DPM-12): request -> approval -> command.

Separation of duties:
  * only a requester can request; only an approver can approve
  * the approver must be a different person from the requester
  * execution needs a matching, unexpired approval (request ID, target,
    equipment, chemical and value must all match)
Request, approval and command are recorded as separate source events from
'operator-desk'. Refusals are recorded in a local audit log.
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from plant.desk_users import DeskUser

EQUIPMENT_ID = "dosing-pump-1"
CHEMICAL = "sodium-hypochlorite"
TARGET = "chlorine_feed_rate"
MIN_FEED_MG_S = 0.0
MAX_FEED_MG_S = 40.0  # teaching limit only
APPROVAL_VALID_MINUTES = 10


class DeskError(Exception):
    """A refused desk action. The message is safe to show to the user."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class DoseRequest:
    request_id: str
    change_id: str
    actor_id: str
    equipment_id: str
    chemical: str
    target: str
    requested_feed_mg_s: float
    created_at: datetime
    status: str = "requested"  # requested -> approved -> executed / refused
    approval: dict | None = None
    command: dict | None = None
    acknowledgement: dict | None = None
    history: list = field(default_factory=list)


class Desk:
    def __init__(self, emit: Callable[..., dict], execute: Callable[[str, str, float, datetime], None],
                 audit_path: Path, clock: Callable[[], datetime] = _now, *, lab_mode: bool = False) -> None:
        """emit(event_type, payload, change_id) publishes a source event.
        execute(command_id, change_id, feed, expires_at) writes through the private controller path."""
        self._emit = emit
        self._execute = execute
        self._clock = clock
        self._lock = threading.RLock()
        self.lab_mode = lab_mode
        self._in_flight = 0
        self.requests: dict[str, DoseRequest] = {}
        self.audit_path = audit_path
        audit_path.parent.mkdir(parents=True, exist_ok=True)

    # --- helpers -----------------------------------------------------------------
    def _audit(self, user: DeskUser, action: str, outcome: str, detail: str, request_id=None) -> None:
        record = {"time_utc": _iso(self._clock()), "actor_id": user.user_id, "role": user.role,
                  "action": action, "request_id": request_id, "outcome": outcome, "detail": detail}
        with self.audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def _refuse(self, user: DeskUser, action: str, detail: str, request_id=None):
        self._audit(user, action, "refused", detail, request_id)
        raise DeskError(detail)

    def _get(self, user, action, request_id) -> DoseRequest:
        req = self.requests.get(request_id)
        if req is None:
            self._refuse(user, action, "Unknown request ID.", request_id)
        return req

    def _validated_feed(self, user, action, requested_feed_mg_s) -> float:
        try:
            value = float(requested_feed_mg_s)
        except (TypeError, ValueError, OverflowError):
            self._refuse(user, action, "Requested feed must be a number.")
        rounded_feed = round(value, 2)
        if not (MIN_FEED_MG_S < value <= MAX_FEED_MG_S) or rounded_feed <= MIN_FEED_MG_S:
            self._refuse(user, action, f"Requested feed must be positive at 0.01 mg/s resolution and at most {MAX_FEED_MG_S:g} mg/s.")
        return rounded_feed

    # --- 1. request ------------------------------------------------------------------
    def create_request(self, user: DeskUser, requested_feed_mg_s: float) -> DoseRequest:
        with self._lock:
            if user.role != "requester":
                self._refuse(user, "request", "Only a requester can create a dose request.")
            value = self._validated_feed(user, "request", requested_feed_mg_s)
            req = DoseRequest(
                request_id=f"req-{uuid.uuid4().hex[:12]}", change_id=f"chg-{uuid.uuid4().hex[:12]}",
                actor_id=user.user_id, equipment_id=EQUIPMENT_ID, chemical=CHEMICAL, target=TARGET,
                requested_feed_mg_s=value, created_at=self._clock(),
            )
            self.requests[req.request_id] = req
            self._emit("dose_request", {
                "request_id": req.request_id, "actor_id": req.actor_id, "equipment_id": req.equipment_id,
                "chemical": req.chemical, "target": req.target, "requested_feed_mg_s": req.requested_feed_mg_s,
            }, req.change_id)
            self._audit(user, "request", "recorded", f"{value} mg/s", req.request_id)
            return req

    # --- 2. approval ---------------------------------------------------------------------
    def approve(self, user: DeskUser, request_id: str) -> DoseRequest:
        with self._lock:
            req = self._get(user, "approve", request_id)
            if user.role != "approver":
                self._refuse(user, "approve", "Only an approver can approve a request.", request_id)
            if user.user_id == req.actor_id:
                self._refuse(user, "approve", "Self-approval is not allowed.", request_id)
            if req.status != "requested":
                self._refuse(user, "approve", f"Request is already {req.status}.", request_id)
            expires = self._clock() + timedelta(minutes=APPROVAL_VALID_MINUTES)
            approval = {
                "approval_id": f"apr-{uuid.uuid4().hex[:12]}", "request_id": req.request_id,
                "approver_id": user.user_id, "equipment_id": req.equipment_id, "chemical": req.chemical,
                "target": req.target, "approved_feed_mg_s": req.requested_feed_mg_s,
                "expires_at_utc": _iso(expires),
            }
            self._emit("dose_approval", dict(approval), req.change_id)
            req.approval = approval
            req.status = "approved"
            self._audit(user, "approve", "recorded", f"valid until {approval['expires_at_utc']}", request_id)
            return req

    # --- 3. execute ----------------------------------------------------------------------
    def execute(self, user: DeskUser, request_id: str) -> DoseRequest:
        with self._lock:
            req = self._get(user, "execute", request_id)
            if user.role not in ("requester", "operator"):
                self._refuse(user, "execute", "Only the requester or the operator can execute.", request_id)
            if req.status != "approved" or req.approval is None:
                self._refuse(user, "execute", f"Request is {req.status}; an approval is required.", request_id)
            a = req.approval
            checks = {
                "request ID": a["request_id"] == req.request_id,
                "target": a["target"] == req.target,
                "equipment": a["equipment_id"] == req.equipment_id,
                "chemical": a["chemical"] == req.chemical,
                "value": a["approved_feed_mg_s"] == req.requested_feed_mg_s,
                "approver is not requester": a["approver_id"] != req.actor_id,
            }
            failed = [name for name, ok in checks.items() if not ok]
            if failed:
                self._refuse(user, "execute", "Approval does not match: " + ", ".join(failed) + ".", request_id)
            expires = datetime.fromisoformat(a["expires_at_utc"].replace("Z", "+00:00"))
            if self._clock() >= expires:
                req.status = "expired"
                self._refuse(user, "execute", "Approval has expired; request a new approval.", request_id)
            req.command = {
                "command_id": f"cmd-{uuid.uuid4().hex[:12]}", "request_id": req.request_id,
                "approval_id": a["approval_id"], "actor_id": user.user_id,
                "equipment_id": req.equipment_id, "requested_feed_mg_s": req.requested_feed_mg_s,
            }
            req.status = "sent"
            self._emit("command", dict(req.command), req.change_id)
            self._audit(user, "execute", "sent", f"{req.requested_feed_mg_s} mg/s", request_id)
            self._in_flight += 1
        # write outside the lock: the controller's acknowledgement calls back into the desk
        try:
            self._execute(req.command["command_id"], req.change_id, req.requested_feed_mg_s, expires)
        except Exception as exc:  # controller refused or unreachable
            with self._lock:
                req.status = "not acknowledged"
            self._audit(user, "execute", "failed", f"controller write failed: {exc}", request_id)
            raise DeskError("The controller did not accept the command. See the plant log.") from exc
        finally:
            with self._lock:
                self._in_flight -= 1
        return req

    def execute_lab(self, user: DeskUser, requested_feed_mg_s, reason: str) -> str:
        action = "lab_unapproved_change"
        with self._lock:
            if not self.lab_mode or user.role != "operator":
                self._refuse(user, action, "Lab-unapproved changes require an operator and enabled lab mode.")
            if self._in_flight:
                self._refuse(user, action, "Wait for the current command to finish.")
            reason = reason.strip()
            if not 1 <= len(reason) <= 1000:
                self._refuse(user, action, "Enter a lab reason of 1–1000 characters.")
            value = self._validated_feed(user, action, requested_feed_mg_s)
            command_id = f"cmd-{uuid.uuid4().hex[:12]}"
            change_id = f"chg-{uuid.uuid4().hex[:12]}"
            self._emit("lab_action", {
                "actor_id": user.user_id, "equipment_id": EQUIPMENT_ID, "action": action,
                "reason": reason, "approved": False, "command_id": command_id,
                "requested_feed_mg_s": value,
            }, change_id)
            self._emit("command", {
                "actor_id": user.user_id, "equipment_id": EQUIPMENT_ID, "command_id": command_id,
                "request_id": None, "approval_id": None, "requested_feed_mg_s": value,
                "lab_unapproved": True,
            }, change_id)
            self._audit(user, action, "sent", f"{command_id}: {reason}")
            self._in_flight += 1
            expires = self._clock() + timedelta(seconds=10)
        try:
            self._execute(command_id, change_id, value, expires)
        except Exception as exc:
            self._audit(user, action, "failed", f"{command_id}: {exc}")
            raise DeskError("The lab command outcome could not be confirmed. See the plant log.") from exc
        finally:
            with self._lock:
                self._in_flight -= 1
        return command_id

    # --- 4. acknowledgement (called by the controller side) ---------------------------------
    def record_acknowledgement(self, command_id: str, ack: dict) -> None:
        with self._lock:
            for req in self.requests.values():
                if req.command and req.command["command_id"] == command_id:
                    req.acknowledgement = ack
                    req.status = "acknowledged" if ack["accepted"] else "rejected by controller"
                    return
