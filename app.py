

import csv
import os
from datetime import datetime, date, time, timedelta
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.simpledialog import askstring


try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_OK = True
except Exception:
    MATPLOTLIB_OK = False


SCHEDULE_CSV = "med_schedule.csv"
LOG_CSV = "dose_log.csv"
SCHEDULE_HEADERS = ["med_id", "med_name", "dose", "times_csv", "days_mask", "active"]
LOG_HEADERS = ["log_id", "med_id", "scheduled_dt", "action", "actual_dt"]

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

BUCKETS = {
    "AM": range(5, 12),
    "Noon": range(12, 15),
    "PM": range(15, 20),
    "Bed": list(range(20, 24)) + list(range(0, 5)),
}

SNOOZE_OVERRIDES = {}


def ensure_csv(path: str, headers: list[str]) -> None:
    """Create CSV with headers if missing."""
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(headers)

def read_rows(path: str) -> list[dict]:
    """Read CSV into list of dicts (empty if missing)."""
    if not os.path.exists(path):
        return []
    with open(path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r)

def append_row(path: str, headers: list[str], row: dict) -> None:
    """Append a single row (auto-create file)."""
    ensure_csv(path, headers)
    file_exists = os.path.exists(path) and os.path.getsize(path) > 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        if not file_exists:
            w.writeheader()
        w.writerow(row)

def write_all(path: str, headers: list[str], rows: list[dict]) -> None:
    """Rewrite all rows (used if you add editing later)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def next_med_id(existing_rows: list[dict]) -> int:
    """Get next integer med_id."""
    max_id = 0
    for r in existing_rows:
        try:
            max_id = max(max_id, int(r["med_id"]))
        except Exception:
            pass
    return max_id + 1

def validate_days_mask(mask: str) -> bool:
    """
    Accept either 7 chars of 1/0 (e.g., '1111111') or exactly 7 letters like 'MTWTFSS'.
    For beginners, we’ll also accept 'Mon,Tue,...' and convert.
    """
    m = mask.strip()
    if len(m) == 7 and all(ch in "10" for ch in m):
        return True
    if len(m) == 7 and m.upper() in ["MTWTFSS"]:
        return True
    parts = [p.strip().capitalize()[:3] for p in m.split(",")]
    if all(p in DAYS for p in parts):
        # Build bitmask Mon..Sun
        bitmask = "".join("1" if d in parts else "0" for d in DAYS)
        return True if len(bitmask) == 7 else False
    return False

def coerce_days_mask(mask: str) -> str:
    """Return standardized 1111111 across Mon..Sun."""
    m = mask.strip()
    if len(m) == 7 and all(ch in "10" for ch in m):
        return m
    if m.upper() in ["MTWTFSS"] and len(m) == 7:
        # Map M T W T F S S → Mon..Sun
        # M T W T F S S  → indices 0..6
        # We need 1/0; here treat letters != '-' as 1
        return "".join("1" for _ in range(7))
    # Convert comma names
    parts = [p.strip().capitalize()[:3] for p in m.split(",")]
    bitmask = "".join("1" if d in parts else "0" for d in DAYS)
    if len(bitmask) == 7:
        return bitmask
    # default to all days if invalid (beginner-friendly fallback)
    return "1111111"

def parse_times_csv(times_csv: str) -> list[time]:
    """Parse '08:00,20:00' -> [time(8,0), time(20,0)]. Skip bad entries."""
    out: list[time] = []
    for part in times_csv.split(","):
        p = part.strip()
        if not p:
            continue
        try:
            hh, mm = p.split(":")
            out.append(time(int(hh), int(mm)))
        except Exception:
            pass
    return out

def is_day_active(mask_1111111: str, dt: date) -> bool:
    """Check if today's weekday is active in mask."""
    idx = dt.weekday()  # Monday=0
    if len(mask_1111111) != 7:
        return False
    return mask_1111111[idx] == "1"

def due_within_window(now: datetime, scheduled: datetime, window_seconds: int = 60) -> bool:
    """True if now within ±window_seconds of scheduled."""
    return abs((now - scheduled).total_seconds()) <= window_seconds

def bucket_for_hour(hh: int) -> str:
    for label, hours in BUCKETS.items():
        if hh in hours:
            return label
    return "AM"


def build_today_schedule() -> list[dict]:

    rows = read_rows(SCHEDULE_CSV)
    today = date.today()
    out = []
    for r in rows:
        if r.get("active", "1").strip() not in ["1", "true", "True", "yes", "YES"]:
            continue
        mask = coerce_days_mask(r.get("days_mask", "1111111"))
        if not is_day_active(mask, today):
            continue
        times_list = parse_times_csv(r.get("times_csv", ""))
        for t in times_list:
            sched = datetime.combine(today, t)
            scheduled_iso = sched.strftime("%Y-%m-%d %H:%M")
            # Snooze override?
            override = SNOOZE_OVERRIDES.get((r["med_id"], scheduled_iso))
            if override:
                sched = override
                scheduled_iso = sched.strftime("%Y-%m-%d %H:%M")
            out.append({
                "med_id": r["med_id"],
                "med_name": r["med_name"],
                "dose": r["dose"],
                "scheduled_dt": sched,
                "scheduled_iso": scheduled_iso,
                "active": "1"
            })
    return sorted(out, key=lambda d: d["scheduled_dt"])

def log_action(med_id: str, scheduled_dt: datetime, action: str, actual_dt: datetime | None = None) -> None:
    rows = read_rows(LOG_CSV)
    next_id = 1
    for r in rows:
        try:
            next_id = max(next_id, int(r["log_id"]) + 1)
        except Exception:
            pass
    row = {
        "log_id": str(next_id),
        "med_id": med_id,
        "scheduled_dt": scheduled_dt.strftime("%Y-%m-%d %H:%M"),
        "action": action,
        "actual_dt": (actual_dt or datetime.now()).strftime("%Y-%m-%d %H:%M"),
    }
    append_row(LOG_CSV, LOG_HEADERS, row)

def is_already_logged(med_id: str, scheduled_dt: datetime) -> bool:
    """Check if a taken/skipped/snoozed exists (we treat any action as 'handled' for v1)."""
    rows = read_rows(LOG_CSV)
    key = (med_id, scheduled_dt.strftime("%Y-%m-%d %H:%M"))
    for r in rows:
        if r.get("med_id") == key[0] and r.get("scheduled_dt") == key[1]:
            return True
    return False

# -------------------------
# Tkinter UI
# -------------------------
class PillBoxApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PillBox — Medicine Reminder (v1)")
        self.geometry("920x620")
        self.resizable(False, False)

        # Ensure CSVs exist
        ensure_csv(SCHEDULE_CSV, SCHEDULE_HEADERS)
        ensure_csv(LOG_CSV, LOG_HEADERS)

        # Tabs
        self.tabs = ttk.Notebook(self)
        self.tab_grid = ttk.Frame(self.tabs)
        self.tab_edit = ttk.Frame(self.tabs)
        self.tab_summary = ttk.Frame(self.tabs)
        self.tabs.add(self.tab_grid, text="Pillbox")
        self.tabs.add(self.tab_edit, text="Add/Edit")
        self.tabs.add(self.tab_summary, text="Summary")
        self.tabs.pack(fill="both", expand=True)

        # Build tab content
        self._build_grid_tab()
        self._build_edit_tab()
        self._build_summary_tab()

        # Kick off the scheduler loop
        self._update_grid_colors()
        self._scheduler_loop()

    # ---------- Pillbox tab ----------
    def _build_grid_tab(self):
        ttk.Label(self.tab_grid, text="Weekly Pillbox (Mon–Sun × AM/Noon/PM/Bed)", font=("Segoe UI", 12, "bold")).pack(pady=10)

        # Grid frame
        frame = ttk.Frame(self.tab_grid)
        frame.pack(pady=10)

        # Header row: days
        ttk.Label(frame, text="").grid(row=0, column=0, padx=6, pady=6)
        for j, day in enumerate(DAYS, start=1):
            ttk.Label(frame, text=day, font=("Segoe UI", 10, "bold")).grid(row=0, column=j, padx=6, pady=6)

        # 4 rows for AM/Noon/PM/Bed
        self.grid_labels = {}  # (bucket, day_idx) -> Label
        for i, bucket in enumerate(["AM", "Noon", "PM", "Bed"], start=1):
            ttk.Label(frame, text=bucket, font=("Segoe UI", 10, "bold")).grid(row=i, column=0, padx=6, pady=6, sticky="e")
            for j in range(1, 8):
                lbl = tk.Label(frame, text=" ", width=16, height=3, relief="groove", bg="#f2f2f2")
                lbl.grid(row=i, column=j, padx=4, pady=4)
                self.grid_labels[(bucket, j-1)] = lbl

        # Legend
        legend = ttk.Frame(self.tab_grid)
        legend.pack(pady=8)
        for color, text in [
            ("#90ee90", "Taken (today)"),
            ("#ffcccb", "Skipped (today)"),
            ("#fff59d", "Due soon"),
            ("#f2f2f2", "No scheduled / not due"),
        ]:
            box = tk.Label(legend, width=3, height=1, bg=color, relief="groove")
            box.pack(side="left", padx=6)
            ttk.Label(legend, text=text).pack(side="left", padx=10)

        ttk.Button(self.tab_grid, text="Refresh", command=self._refresh_ui).pack(pady=4)

    def _refresh_ui(self):
        self._update_grid_colors()
        self._draw_summary()
        self.update_idletasks()
    def _update_grid_colors(self):
    
    # Reset all
        for lbl in self.grid_labels.values():
            lbl.config(bg="#f2f2f2", text=" ")

        today_sched = build_today_schedule()
        logs = read_rows(LOG_CSV)

    # Map (med_id, scheduled) -> action for TODAY only
        today_str = date.today().strftime("%Y-%m-%d")
        action_map = {}
        for r in logs:
            if r.get("scheduled_dt", "").startswith(today_str):
                action_map[(r["med_id"], r["scheduled_dt"])] = r["action"]

    # Paint
        for item in today_sched:
            dt_sched = item["scheduled_dt"]
            bucket = bucket_for_hour(dt_sched.hour)
            col = dt_sched.weekday()  # Monday=0
            key = (item["med_id"], dt_sched.strftime("%Y-%m-%d %H:%M"))
            cell = self.grid_labels.get((bucket, col))
            if not cell:
                continue

            if key in action_map:
                act = action_map[key]
                if act == "taken":
                    cell.config(bg="#90ee90", text=f"{item['med_name']}\n{item['dose']}\n{dt_sched.strftime('%H:%M')}")
                elif act == "skipped":
                    cell.config(bg="#ffcccb", text=f"{item['med_name']}\n{item['dose']}\n{dt_sched.strftime('%H:%M')}")
                else:
                    cell.config(bg="#d0e0ff", text=f"{item['med_name']}\n(snoozed)\n{dt_sched.strftime('%H:%M')}")
        else:
            now = datetime.now()
            if due_within_window(now, dt_sched, 60 * 15):
                cell.config(bg="#fff59d", text=f"{item['med_name']}\n{item['dose']}\n{dt_sched.strftime('%H:%M')}")
            else:
                cell.config(text=f"{item['med_name']}\n{item['dose']}\n{dt_sched.strftime('%H:%M')}")

    
        self.update_idletasks()
    # ---------- Add/Edit tab ----------
    def _build_edit_tab(self):
        frm = ttk.Frame(self.tab_edit, padding=12)
        frm.pack(fill="x", pady=10)

        ttk.Label(frm, text="Add Medication", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0,8), sticky="w")

        ttk.Label(frm, text="Name:").grid(row=1, column=0, sticky="e", padx=6, pady=4)
        self.ent_name = ttk.Entry(frm, width=32)
        self.ent_name.grid(row=1, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(frm, text="Dose (e.g., 500 mg):").grid(row=2, column=0, sticky="e", padx=6, pady=4)
        self.ent_dose = ttk.Entry(frm, width=32)
        self.ent_dose.grid(row=2, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(frm, text="Times (24h, comma-separated: 08:00,20:00):").grid(row=3, column=0, sticky="e", padx=6, pady=4)
        self.ent_times = ttk.Entry(frm, width=32)
        self.ent_times.grid(row=3, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(frm, text="Days mask:").grid(row=4, column=0, sticky="e", padx=6, pady=4)
        self.ent_days = ttk.Entry(frm, width=32)
        self.ent_days.insert(0, "Mon,Tue,Wed,Thu,Fri,Sat,Sun")
        self.ent_days.grid(row=4, column=1, sticky="w", padx=6, pady=4)

        self.var_active = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm, text="Active", variable=self.var_active).grid(row=5, column=1, sticky="w", padx=6, pady=4)

        ttk.Button(frm, text="Save Medication", command=self._save_medication).grid(row=6, column=1, sticky="w", padx=6, pady=(10,4))

        # A tiny viewer (read-only) of what’s in schedule CSV
        self.tree = ttk.Treeview(self.tab_edit, columns=SCHEDULE_HEADERS, show="headings", height=8)
        for col in SCHEDULE_HEADERS:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=130, anchor="w")
        self.tree.pack(fill="x", padx=12, pady=10)
        ttk.Button(self.tab_edit, text="Reload list", command=self._reload_schedule_view).pack(pady=(0,10))

        self._reload_schedule_view()

    def _save_medication(self):
        name = self.ent_name.get().strip()
        dose = self.ent_dose.get().strip()
        times_csv = self.ent_times.get().strip()
        days_mask = self.ent_days.get().strip()
        active = "1" if self.var_active.get() else "0"

        if not name or not dose or not times_csv or not validate_days_mask(days_mask):
            messagebox.showerror("Missing/Invalid", "Please enter Name, Dose, valid Times, and Days.")
            return

        rows = read_rows(SCHEDULE_CSV)
        new_id = next_med_id(rows)

        row = {
            "med_id": str(new_id),
            "med_name": name,
            "dose": dose,
            "times_csv": times_csv,
            "days_mask": coerce_days_mask(days_mask),
            "active": active,
        }
        append_row(SCHEDULE_CSV, SCHEDULE_HEADERS, row)
        messagebox.showinfo("Saved", f"Medication '{name}' added (id={new_id}).")
        self._reload_schedule_view()
        self._update_grid_colors()

        # Clear fields
        self.ent_name.delete(0, tk.END)
        self.ent_dose.delete(0, tk.END)
        self.ent_times.delete(0, tk.END)
        self.update_idletasks()

    def _reload_schedule_view(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in read_rows(SCHEDULE_CSV):
            self.tree.insert("", tk.END, values=[r.get(h, "") for h in SCHEDULE_HEADERS])

    # ---------- Summary tab ----------
    def _build_summary_tab(self):
        self.summary_frame = ttk.Frame(self.tab_summary, padding=12)
        self.summary_frame.pack(fill="both", expand=True)
        ttk.Label(self.summary_frame, text="Weekly Summary (last 7 days)", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0,8))
        self.summary_container = ttk.Frame(self.summary_frame)
        self.summary_container.pack(fill="both", expand=True)
        self._draw_summary()

    def _draw_summary(self):
        # Clear
        for w in self.summary_container.winfo_children():
            w.destroy()

        if not MATPLOTLIB_OK:
            ttk.Label(self.summary_container, text="Matplotlib not available. Chart disabled for v1.").pack(pady=16)
            return

        logs = read_rows(LOG_CSV)
        cutoff = datetime.now() - timedelta(days=7)
        counts = {"taken": 0, "snoozed": 0, "skipped": 0}
        for r in logs:
            try:
                when = datetime.strptime(r.get("actual_dt", ""), "%Y-%m-%d %H:%M")
                if when >= cutoff:
                    a = r.get("action", "")
                    if a in counts:
                        counts[a] += 1
            except Exception:
                pass

        fig = Figure(figsize=(5.2, 3.4), dpi=120)
        ax = fig.add_subplot(111)
        ax.bar(list(counts.keys()), list(counts.values()))
        ax.set_title("Actions in last 7 days")
        ax.set_ylabel("Count")

        canvas = FigureCanvasTkAgg(fig, master=self.summary_container)
        canvas.draw()
        canvas.get_tk_widget().pack()
        self.update_idletasks()


    # ---------- Scheduler loop ----------
    def _scheduler_loop(self):
        """
        Every 10 seconds:
        - Build today's schedule
        - If something is due (±60 sec) and not logged, show popup
        """
        try:
            now = datetime.now()
            today_items = build_today_schedule()
            for item in today_items:
                sched = item["scheduled_dt"]
                if due_within_window(now, sched, window_seconds=60) and not is_already_logged(item["med_id"], sched):
                    self._show_due_popup(item)
                    # Only show one popup at a time to keep v1 simple
                    break
        except Exception as e:
            # Minimal error guard in v1; add proper logging in v2.
            print("Scheduler error:", e)

        self._update_grid_colors()
        self.after(10_000, self._scheduler_loop)  # 10 seconds

    def _show_due_popup(self, item: dict):
        """Blocking modal dialog with Take / Snooze / Skip."""
        med_label = f"{item['med_name']} — {item['dose']} (due {item['scheduled_dt'].strftime('%H:%M')})"
        top = tk.Toplevel(self)
        top.title("Dose Due")
        top.grab_set()  # modal
        top.update()
        ttk.Label(top, text="Medication due now:", font=("Segoe UI", 10, "bold")).pack(padx=16, pady=(16,8))
        ttk.Label(top, text=med_label).pack(padx=16, pady=(0,12))

        btn_frame = ttk.Frame(top)
        btn_frame.pack(pady=10)

        def do_take():
            log_action(item["med_id"], item["scheduled_dt"], "taken", datetime.now())
            top.destroy()
            self._update_grid_colors()
            self.update_idletasks()
            messagebox.showinfo("Logged", "Marked as TAKEN.")

        def do_snooze():
            # Push this specific occurrence by +10 minutes (session only)
            new_dt = item["scheduled_dt"] + timedelta(minutes=10)
            SNOOZE_OVERRIDES[(item["med_id"], item["scheduled_iso"])] = new_dt
            log_action(item["med_id"], item["scheduled_dt"], "snoozed", datetime.now())
            top.destroy()
            self._update_grid_colors()
            self.update_idletasks()
            messagebox.showinfo("Snoozed", "Snoozed for 10 minutes.")

        def do_skip():
            log_action(item["med_id"], item["scheduled_dt"], "skipped", datetime.now())
            top.destroy()
            self._update_grid_colors()
            self.update_idletasks()
            messagebox.showinfo("Logged", "Marked as SKIPPED.")

        ttk.Button(btn_frame, text="Take", command=do_take).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Snooze 10 min", command=do_snooze).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Skip", command=do_skip).pack(side="left", padx=6)

        ttk.Button(top, text="Close", command=top.destroy).pack(pady=(0,12))

# ---------------
# main
# ---------------
if __name__ == "__main__":
    app = PillBoxApp()
    app.mainloop()
