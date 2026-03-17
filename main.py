# =========================
# IMPORTS
# =========================
from tkinter import *
from tkinter import messagebox
import threading
from datetime import datetime, timezone
import requests
import serial
import time
from dateutil import parser  # at the top
# =========================
# CONFIG IMPORT
# =========================

from config import (
    SERIAL_PORT,
    BAUD_RATE,
    COOLDOWN_SECONDS,
    LOCATION,
    SCRIPT_URL,
    UI_UPDATE_DELAY
)

LAST_UI_UPDATE = 0

# =========================
# SCANNER STATE
# =========================

stop_scanning = False
scanner_thread = None
cloud_loaded = False
scanner_active = False
uploading = False

cloud_lock = {}  # {"UID|ROUTE|OUT": datetime, "UID|ROUTE|IN": datetime}
session_lock = {}  # same structure
last_seen_uids = {}  # cooldown

# =========================
# HELPERS
# =========================

def clean_uid(raw_uid):
    raw_uid = raw_uid.strip().upper()
    return "".join(c for c in raw_uid if c.isalnum())

def build_key(uid):
    route = route_entry.get().upper()
    transfer = "IN" if transfer_mode.get() == 1 else "OUT"
    return f"{uid}|{route}|{transfer}"

def has_existing_in(uid):

    route = route_entry.get().upper()
    in_key = f"{uid}|{route}|IN"

    # check cloud records
    if in_key in cloud_lock:
        return True

    # check current session
    if in_key in session_lock:
        return True

    return False

def get_active_out_route(uid):
    """
    Returns the route where this UID currently has an unfinished OUT.
    If no active OUT exists, returns None.
    """

    events = []

    # collect cloud events
    for key, ts in cloud_lock.items():
        k_uid, route, action = key.split("|")
        if k_uid == uid:
            events.append((ts, route, action))

    # collect session events
    for key, ts in session_lock.items():
        k_uid, route, action = key.split("|")
        if k_uid == uid:
            events.append((ts, route, action))

    if not events:
        return None

    # sort by time
    events.sort(key=lambda x: x[0])

    active_route = None

    for ts, route, action in events:

        if action == "OUT":
            active_route = route

        elif action == "IN":
            if active_route == route:
                active_route = None

    return active_route

def get_active_in_route(uid):

    route_balance = {}

    # Check cloud
    for key in cloud_lock:
        parts = key.split("|")
        if len(parts) == 3:

            k_uid, k_route, k_transfer = parts

            if k_uid == uid:

                route_balance.setdefault(k_route, 0)

                if k_transfer == "IN":
                    route_balance[k_route] += 1
                elif k_transfer == "OUT":
                    route_balance[k_route] -= 1

    # Check session
    for key in session_lock:
        parts = key.split("|")
        if len(parts) == 3:

            k_uid, k_route, k_transfer = parts

            if k_uid == uid:

                route_balance.setdefault(k_route, 0)

                if k_transfer == "IN":
                    route_balance[k_route] += 1
                elif k_transfer == "OUT":
                    route_balance[k_route] -= 1

    # Find which route still has unmatched IN
    for route, balance in route_balance.items():
        if balance > 0:
            return route

    return None

# =========================
# LOAD CLOUD DATA
# =========================



def load_today_scans():
    global cloud_loaded

    try:
        r = requests.get(SCRIPT_URL, timeout=10)
        if r.status_code == 200:
            data = r.json()
            cloud_lock.clear()
            for item in data:
                uid = clean_uid(item["uid"])
                route = item["route"].upper()
                out_time = item["out_time"]
                in_time = item["in_time"]

                if out_time:
                    try:
                        cloud_lock[f"{uid}|{route}|OUT"] = parser.isoparse(out_time)
                    except Exception as e:
                        print(f"Error parsing OUT timestamp for {uid}: {e}")

                if in_time:
                    try:
                        cloud_lock[f"{uid}|{route}|IN"] = parser.isoparse(in_time)
                    except Exception as e:
                        print(f"Error parsing IN timestamp for {uid}: {e}")

            cloud_loaded = True
            root.after(
                0,
                lambda: last_logged.set(f"Cloud synced ({len(cloud_lock)})")
            )

    except Exception as e:
        print("Load error:", e)

    # schedule next sync in 5 seconds without recursion
    root.after(5000, load_today_scans)

# =========================
# MAIN WINDOW
# =========================

root = Tk()
root.title("UHF Scanner")
root.geometry("350x600")
root.resizable(False, False)

def on_close():
    global stop_scanning
    stop_scanning = True
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)

# =========================
# HEADER
# =========================

Label(root, text="RFID Logger", font=("Arial", 16, "bold")).pack(pady=10)

# =========================
# ROUTE INPUT
# =========================

route_frame = Frame(root)
route_frame.pack()

def validate_route(v):

    if v == "":
        return True

    return v.isalnum() and len(v) <= 10

vcmd = root.register(validate_route)

route_var = StringVar()

def check_route(*args):

    value = route_var.get().upper()
    route_var.set(value)

    if value:
        start_button.config(state=NORMAL)
    else:
        start_button.config(state=DISABLED)

route_var.trace_add("write", check_route)

Label(route_frame, text="Route:").pack(side=LEFT)

route_entry = Entry(
    route_frame,
    textvariable=route_var,
    validate="key",
    validatecommand=(vcmd, "%P")
)
route_entry.pack(side=LEFT)

# =========================
# TRANSFER MODE
# =========================

transfer_mode = IntVar(value=1)

radio = Frame(root)
radio.pack(pady=5)

radio_in = Radiobutton(radio, text="IN", variable=transfer_mode, value=1)
radio_out = Radiobutton(radio, text="OUT", variable=transfer_mode, value=2)

radio_in.pack(side=LEFT, padx=15)
radio_out.pack(side=LEFT, padx=15)
# =========================
# STATUS
# =========================

scanned_items_number = IntVar(value=0)
last_logged = StringVar(value="")

Label(root, text="Scanned Items").pack()
Label(root, textvariable=scanned_items_number).pack()

Label(root, text="Last Log").pack()
Label(root, textvariable=last_logged).pack()

# =========================
# LISTBOX
# =========================

listbox = Listbox(root, width=40, height=15)
listbox.pack(pady=10)

# =========================
# RFID PROCESSOR
# =========================



def process_uid(uid):

    global LAST_UI_UPDATE

    if not scanner_active:
        return

    if not cloud_loaded:
        last_logged.set("Syncing cloud...")
        return

    uid = clean_uid(uid)

    if not uid:
        return

    now = datetime.now(timezone.utc)

    route = route_entry.get().upper()

    action = "IN" if transfer_mode.get() == 1 else "OUT"

    key = f"{uid}|{route}|{action}"

    active_route = get_active_out_route(uid)

    # =========================
    # VALIDATION
    # =========================

    if action == "OUT":

        if active_route is not None:
            last_logged.set(f"{uid} already OUT in {active_route}")
            return

    elif action == "IN":

        if active_route is None:
            last_logged.set(f"{uid} has no OUT record")
            return

        if active_route != route:
            last_logged.set(f"{uid} must IN in {active_route}")
            return


    # prevent duplicate scan in current session
    if key in session_lock:
        last_logged.set(f"Session duplicate: {uid}")
        return


    # cooldown protection (reader spam)
    if uid in last_seen_uids:

        sec = (now - last_seen_uids[uid]).total_seconds()

        if sec < COOLDOWN_SECONDS:
            last_logged.set(f"Ignored rapid scan: {uid}")
            return


    last_seen_uids[uid] = now

    session_lock[key] = now


    listbox.insert(
        END,
        f"{uid} | {route} | {action} | {now.strftime('%H:%M:%S')}"
    )

    scanned_items_number.set(listbox.size())

    last_logged.set(f"{uid} {action} accepted")

    LAST_UI_UPDATE = time.time()

# =========================
# SERIAL READER
# =========================

def read_rfid():

    global stop_scanning

    try:

        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:

            ser.reset_input_buffer()

            root.after(
                0,
                lambda: last_logged.set("Scanner connected")
            )

            while not stop_scanning:

                raw = ser.readline()

                line = raw.decode(errors="ignore").strip()

                if line:

                    # Remove ANY non-alphanumeric characters first
                    cleaned = "".join(c for c in line if c.isalnum())

                    # If purely numeric after cleaning, convert from decimal to HEX
                    if cleaned.isdigit():
                        try:
                            cleaned = format(int(cleaned), "X").upper()
                        except:
                            pass

                    root.after(0, process_uid, cleaned)

    except:
        root.after(0, lambda: last_logged.set("Scanner disconnected"))

# =========================
# START BUTTON
# =========================

def start_scanning():

    global scanner_thread, stop_scanning, scanner_active

    scanner_active = not scanner_active

    if scanner_active:

        start_button.config(text="Stop Scanning")
        last_logged.set("Scanning ACTIVE")

        # LOCK INPUTS
        route_entry.config(state="disabled")
        radio_in.config(state="disabled")
        radio_out.config(state="disabled")

        # flush reader buffer
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            ser.reset_input_buffer()
            ser.close()
        except:
            pass

    else:

        start_button.config(text="Start Scanning")
        last_logged.set("Scanning PAUSED")

        # KEEP INPUTS LOCKED
        route_entry.config(state="disabled")
        radio_in.config(state="disabled")
        radio_out.config(state="disabled")

    if not scanner_thread or not scanner_thread.is_alive():

        stop_scanning = False

        scanner_thread = threading.Thread(
            target=read_rfid,
            daemon=True
        )
        scanner_thread.start()

start_button = Button(
    root,
    text="Start Scanning",
    width=30,
    state=DISABLED,
    command=start_scanning
)
start_button.pack()

# =========================
# DELETE BUTTONS
# =========================

delete_frame = Frame(root)
delete_frame.pack(pady=5)

def delete_selected():
    selected = listbox.curselection()
    for i in reversed(selected):
        item = listbox.get(i)
        uid, route, action, _ = [p.strip() for p in item.split("|")]
        key = f"{uid}|{route}|{action}"

        session_lock.pop(key, None)  # fix here
        last_seen_uids.pop(uid, None)
        listbox.delete(i)

    scanned_items_number.set(listbox.size())

def delete_all():

    if listbox.size() == 0:
        return

    confirm = messagebox.askyesno(
        "Confirm",
        "Delete ALL scanned entries?"
    )

    if not confirm:
        return

    listbox.delete(0, END)

    session_lock.clear()
    last_seen_uids.clear()

    scanned_items_number.set(0)

Button(delete_frame, text="Delete", width=14, command=delete_selected).pack(side=LEFT, padx=5)
Button(delete_frame, text="Delete All", width=14, command=delete_all).pack(side=LEFT, padx=5)

# =========================
# SAVE TO GOOGLE
# =========================

def clear_session():

    global scanner_active

    listbox.delete(0, END)

    session_lock.clear()
    last_seen_uids.clear()

    scanned_items_number.set(0)

    route_var.set("")
    transfer_mode.set(1)

    # UNLOCK INPUTS
    route_entry.config(state="normal")
    radio_in.config(state="normal")
    radio_out.config(state="normal")

    # RESET START BUTTON
    scanner_active = False
    start_button.config(text="Start Scanning")

    last_logged.set("Session cancelled")

def save_all_to_google():
    """
    Upload all scanned items in the session listbox to Google Sheets.
    OUT/IN timestamps are preserved to enforce 24-hour lock on OUT.
    """
    global uploading

    if uploading:
        return

    uploading = True
    root.after(0, lambda: save_button.config(state=DISABLED))

    try:
        items = listbox.get(0, END)

        if not items:
            messagebox.showwarning("No Items", "Nothing to save")
            return

        success = 0

        for item in items:
            # Format: uid | route | action | time
            parts = [p.strip() for p in item.split("|")]
            if len(parts) < 3:
                continue

            uid, route, action = parts[:3]
            # Use the timestamp stored in session_lock, fallback to now
            ts = session_lock.get(f"{uid}|{route}|{action}", datetime.now())

            payload = {
                "action": action,
                "scanned_id": uid,
                "route": route,
                "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S")
            }

            try:
                r = requests.post(
                    SCRIPT_URL,
                    json=payload,
                    timeout=10
                )

                if r.status_code == 200:
                    # Update cloud_lock with timestamp
                    cloud_lock[f"{uid}|{route}|{action}"] = ts
                    success += 1

            except Exception as e:
                print(f"Failed to upload {uid}: {e}")
                continue

        # Clear UI and session after successful upload
        clear_session()

        messagebox.showinfo("Done", f"Uploaded {success} item(s)")

    finally:
        uploading = False
        root.after(0, lambda: save_button.config(state=NORMAL))

save_button = Button(
    root,
    text="Save",
    width=25,
    command=lambda:
    threading.Thread(
        target=save_all_to_google,
        daemon=True
    ).start()
)
save_button.pack(pady=5)

Button(
    root,
    text="Cancel",
    width=25,
    command=clear_session
).pack()

def start_scanning():

    global scanner_thread, stop_scanning, scanner_active

    scanner_active = not scanner_active

    if scanner_active:

        start_button.config(text="Stop Scanning")
        last_logged.set("Scanning ACTIVE")

        # LOCK INPUTS
        route_entry.config(state="disabled")
        radio_in.config(state="disabled")
        radio_out.config(state="disabled")

        # flush reader buffer
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            ser.reset_input_buffer()
            ser.close()
        except:
            pass

    else:

        start_button.config(text="Start Scanning")
        last_logged.set("Scanning PAUSED")

        # KEEP INPUTS LOCKED
        route_entry.config(state="disabled")
        radio_in.config(state="disabled")
        radio_out.config(state="disabled")

    if not scanner_thread or not scanner_thread.is_alive():

        stop_scanning = False

        scanner_thread = threading.Thread(
            target=read_rfid,
            daemon=True
        )
        scanner_thread.start()
# =========================
# START CLOUD SYNC
# =========================

threading.Thread(
    target=load_today_scans,
    daemon=True
).start()

root.mainloop()