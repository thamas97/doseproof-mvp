"""Operator desk web page (DPM-12) on 127.0.0.1:5000. Educational simulation only.

Security basics used here:
  * named login checked against salted hashes (plant/desk_users.py)
  * random session secret per start (never committed)
  * CSRF token on every form post
  * session cookie HttpOnly + SameSite=Strict; bound to loopback only
"""

from __future__ import annotations

import secrets
from typing import Callable

from flask import Flask, abort, redirect, render_template_string, request, session, url_for

from plant.desk import Desk, DeskError
from plant.desk_users import USERS, authenticate

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>DoseProof operator desk</title>
<style>
 body{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:24px;max-width:1100px;color:#1d2733}
 .banner{background:#fff4d6;border:1px solid #e0b84f;padding:8px 12px;margin-bottom:16px}
 table{border-collapse:collapse;width:100%;margin:12px 0} td,th{border:1px solid #ccd3db;padding:6px 8px;text-align:left;font-size:14px}
 th{background:#eef2f6} .msg{padding:8px 12px;margin:10px 0}.ok{background:#e3f4e6}.err{background:#fde4e4}
 form.inline{display:inline} button{padding:4px 10px} .muted{color:#5d6b7a;font-size:13px}
</style></head><body>
<div class="banner"><b>Educational simulation only.</b> Not drinking-water operating guidance.</div>
{% if user %}
 <p>Signed in as <b>{{ user.display_name }}</b> ({{ user.role }})
 <form class="inline" method="post" action="{{ url_for('logout') }}"><input type="hidden" name="csrf" value="{{ csrf }}"><button>Sign out</button></form></p>
{% endif %}
{% if message %}<div class="msg {{ 'err' if error else 'ok' }}">{{ message }}</div>{% endif %}
{{ body|safe }}
</body></html>"""

LOGIN = """<h2>Operator desk sign-in</h2>
<form method="post"><input type="hidden" name="csrf" value="{{ csrf }}">
<p><label>User <select name="user_id">{% for u in users %}<option value="{{ u.user_id }}">{{ u.display_name }} ({{ u.role }})</option>{% endfor %}</select></label></p>
<p><label>Password <input type="password" name="password" autocomplete="current-password"></label></p>
<button>Sign in</button></form>"""

HOME = """<h3>Plant now (step {{ s.sim_step }})</h3>
{% if run %}<p>{{ run[0] }} · {{ 'Paused' if run[1] else 'Running' }}</p>{% endif %}
{% if run and user.role == 'operator' %}
<form method="post" action="{{ url_for('control_run') }}">
 <input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="run_id" value="{{ run[0] }}">
 <button name="action" value="pause">Pause</button><button name="action" value="resume">Resume</button>
 <button name="action" value="reset">Reset to new paused run</button>
 {% if lab_mode %}
 <button name="action" value="stop-pump">Lab: stop pump</button>
 <button name="action" value="suppress-a">Lab: suppress Sensor A</button>
 {% endif %}
</form>
{% endif %}
<table><tr><th>Flow L/s</th><th>Requested feed mg/s</th><th>Accepted feed mg/s</th><th>Actual delivery mg/s</th><th>Pump</th><th>Modeled residual mg/L</th></tr>
<tr><td>{{ '%.2f'|format(s.flow_l_s) }}</td><td>{{ '%.2f'|format(s.requested_feed_mg_s) }}</td><td>{{ '%.2f'|format(s.accepted_feed_mg_s) }}</td>
<td>{{ '%.2f'|format(s.actual_delivery_mg_s) }}</td><td>{{ 'running' if s.pump_running else 'stopped' }}</td><td>{{ '%.4f'|format(s.modeled_residual_mg_l) }}</td></tr></table>
<p class="muted">Accepted feed is the controller setting; actual delivery is what the pump delivers; the residual responds after a delay.</p>
{% if user.role == 'operator' %}
{% if lab_mode %}
<h3>Lab only · Unapproved change</h3>
<form method="post" action="{{ url_for('execute_lab') }}"><input type="hidden" name="csrf" value="{{ csrf }}">
 <label>Feed (mg/s) <input name="requested_feed_mg_s" size="6" value="20" required></label>
 <label>Reason <input name="reason" maxlength="1000" required></label>
 <button>Execute labelled lab-unapproved change</button>
</form>
{% else %}<p>Lab-unapproved path is disabled.</p>{% endif %}
{% endif %}
{% if user.role == 'requester' %}
<h3>New dose request</h3>
<form method="post" action="{{ url_for('create_request') }}"><input type="hidden" name="csrf" value="{{ csrf }}">
 Equipment <b>dosing-pump-1</b>, chemical <b>sodium-hypochlorite</b>, feed
 <input name="requested_feed_mg_s" size="6" value="20"> mg/s <button>Submit request</button></form>
{% endif %}
<h3>Requests</h3>
<table><tr><th>Request</th><th>Requested by</th><th>Feed mg/s</th><th>Status</th><th>Approval</th><th>Command / acknowledgement</th><th>Action</th></tr>
{% for r in reqs %}<tr>
<td>{{ r.request_id }}<br><span class="muted">{{ r.change_id }}</span></td><td>{{ r.actor_id }}</td><td>{{ r.requested_feed_mg_s }}</td><td><b>{{ r.status }}</b></td>
<td>{% if r.approval %}{{ r.approval.approver_id }}<br><span class="muted">until {{ r.approval.expires_at_utc }}</span>{% endif %}</td>
<td>{% if r.command %}{{ r.command.command_id }} by {{ r.command.actor_id }}{% endif %}
    {% if r.acknowledgement %}<br>ack: accepted={{ r.acknowledgement.accepted }}, accepted feed {{ r.acknowledgement.accepted_feed_mg_s }}{% endif %}</td>
<td>{% if r.status == 'requested' and user.role == 'approver' %}
  <form class="inline" method="post" action="{{ url_for('approve', request_id=r.request_id) }}"><input type="hidden" name="csrf" value="{{ csrf }}"><button>Approve</button></form>
{% elif r.status == 'approved' and user.role in ('requester','operator') %}
  <form class="inline" method="post" action="{{ url_for('execute', request_id=r.request_id) }}"><input type="hidden" name="csrf" value="{{ csrf }}"><button>Execute</button></form>
{% endif %}</td></tr>{% else %}<tr><td colspan="7" class="muted">No requests yet.</td></tr>{% endfor %}
</table>"""


def create_desk_app(desk: Desk, plant_state: Callable[[], object], *, control=None, run_state=None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secrets.token_hex(32),  # new random key every start; never stored
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
    )

    def csrf_token() -> str:
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]

    @app.before_request
    def check_csrf():
        if request.method == "POST":
            sent = request.form.get("csrf", "")
            if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
                abort(400, "Missing or invalid form token.")

    def current_user():
        return USERS.get(session.get("user_id", ""))

    def render(body_template: str, message=None, error=False, **ctx):
        body = render_template_string(body_template, csrf=csrf_token(), user=current_user(), **ctx)
        return render_template_string(PAGE, body=body, user=current_user(), csrf=csrf_token(),
                                      message=message, error=error)

    def home_page(message=None, error=False):
        with desk._lock:
            reqs = sorted(desk.requests.values(), key=lambda r: r.created_at, reverse=True)
        return render(HOME, message, error, s=plant_state(), reqs=reqs,
                      run=run_state() if run_state else None, lab_mode=desk.lab_mode)

    @app.route("/", methods=["GET"])
    def index():
        if not current_user():
            return redirect(url_for("login"))
        return home_page(session.pop("flash", None), session.pop("flash_error", False))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            user = authenticate(request.form.get("user_id", ""), request.form.get("password", ""))
            if user is None:
                return render(LOGIN, "Sign-in failed.", True, users=USERS.values()), 401
            session.clear()
            session["user_id"] = user.user_id
            return redirect(url_for("index"))
        return render(LOGIN, users=USERS.values())

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("login"))

    def act(action):
        user = current_user()
        if user is None:
            return redirect(url_for("login"))
        try:
            session["flash"] = action(user)
            session["flash_error"] = False
        except DeskError as exc:
            session["flash"] = str(exc)
            session["flash_error"] = True
        return redirect(url_for("index"))

    @app.route("/requests", methods=["POST"])
    def create_request():
        return act(lambda u: f"Request {desk.create_request(u, request.form.get('requested_feed_mg_s')).request_id} recorded.")

    @app.route("/requests/<request_id>/approve", methods=["POST"])
    def approve(request_id):
        return act(lambda u: f"Request {desk.approve(u, request_id).request_id} approved.")

    @app.route("/requests/<request_id>/execute", methods=["POST"])
    def execute(request_id):
        return act(lambda u: f"Command sent; status: {desk.execute(u, request_id).status}.")

    @app.post('/simulation/control')
    def control_run():
        if control is None:
            abort(404)
        return act(lambda u: control(u, request.form.get('action', ''), request.form.get('run_id')))

    @app.post('/simulation/lab-unapproved')
    def execute_lab():
        return act(lambda u: f"Lab command {desk.execute_lab(u, request.form.get('requested_feed_mg_s'), request.form.get('reason', ''))} recorded.")

    return app
