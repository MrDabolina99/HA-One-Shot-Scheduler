from flask import Flask, render_template, request, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import requests
import json
import os
import uuid
from datetime import datetime

app = Flask(__name__)

# ----- Config -----
DATA_FILE = "/data/events.json"
HA_API    = "http://supervisor/core/api"
TOKEN     = os.environ.get("SUPERVISOR_TOKEN", "")

# ----- Scheduler -----
scheduler = BackgroundScheduler()
scheduler.start()

# ----- Helpers -----

def load_events():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_events(events):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(events, f, indent=2)

def call_ha_service(action, entity_id):
    """Calls a Home Assistant service like homeassistant.turn_on"""
    domain, service = action.split(".", 1)
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"entity_id": entity_id}
    try:
        r = requests.post(
            f"{HA_API}/services/{domain}/{service}",
            headers=headers,
            json=payload,
            timeout=10,
        )
        print(f"[Scheduler] Executed {action} on {entity_id} -> HTTP {r.status_code}")
    except Exception as e:
        print(f"[Scheduler] Error calling HA API: {e}")

def execute_event(event_id):
    """Called by APScheduler when the event fires."""
    events = load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if event:
        call_ha_service(event["action"], event["entity_id"])
        # Remove from list after execution
        events = [e for e in events if e["id"] != event_id]
        save_events(events)
        print(f"[Scheduler] Event '{event['description']}' completed and removed.")

def schedule_event(event):
    """Add an event to the APScheduler."""
    run_time = datetime.fromisoformat(f"{event['date']}T{event['time']}")
    if run_time <= datetime.now():
        print(f"[Scheduler] Skipping past event: {event['description']}")
        return
    scheduler.add_job(
        execute_event,
        trigger=DateTrigger(run_date=run_time),
        args=[event["id"]],
        id=event["id"],
        replace_existing=True,
    )
    print(f"[Scheduler] Scheduled '{event['description']}' for {run_time}")

# Restore scheduled jobs on startup
for ev in load_events():
    try:
        schedule_event(ev)
    except Exception as e:
        print(f"[Scheduler] Could not restore event {ev.get('id')}: {e}")

# ----- Routes -----

@app.route("/")
def index():
    events = sorted(load_events(), key=lambda e: f"{e['date']}T{e['time']}")
    return render_template("index.html", events=events)

@app.route("/add", methods=["POST"])
def add_event():
    event = {
        "id":          str(uuid.uuid4()),
        "description": request.form["description"],
        "entity_id":   request.form["entity_id"].strip(),
        "action":      request.form["action"],
        "date":        request.form["date"],
        "time":        request.form["time"],
    }
    events = load_events()
    events.append(event)
    save_events(events)
    schedule_event(event)
    return redirect(url_for("index"))

@app.route("/delete/<event_id>")
def delete_event(event_id):
    events = [e for e in load_events() if e["id"] != event_id]
    save_events(events)
    try:
        scheduler.remove_job(event_id)
    except Exception:
        pass
    return redirect(url_for("index"))

# ----- Run -----
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8099)
