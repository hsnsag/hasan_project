# run_app.py — PillBox v2 (Version 2 progress, edit & delete)
# --------------------------------------------------------------------
# - Weekly grid (Mon–Sun × AM/Noon/PM/Bed)
# - Add/Edit medications with time dropdowns and day checkboxes
# - Current Medications table with readable day names
# - Snooze manager with CSV persistence
# - Summary chart (if matplotlib is installed)
# - NEW: Edit selected medication, Delete (mark inactive)

import csv
import os
from datetime import datetime, date, time, timedelta
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_OK = True
except Exception:
    MATPLOTLIB_OK = False

try:
    import pandas as pd
    PANDAS_OK = True
except Exception:
    PANDAS_OK = False

# ---------------- Files / headers ----------------
SCHEDULE_CSV = "med_schedule.csv"
LOG_CSV = "dose_log.csv"
SNOOZE_CSV = "snoozes.csv"

SCHEDULE_HEADERS = ["med_id", "med_name", "dose", "times_csv", "days_mask", "active"]
LOG_HEADERS = ["log_id", "med_id", "scheduled_dt", "action", "actual_dt"]
SNOOZE_HEADERS = ["med_id", "scheduled_dt", "new_dt"]

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DATE_FMT = "%Y-%m-%d %H:%M"

# Grid buckets by hour
BUCKETS = {
    "AM": range(5, 12),
    "Noon": range(12, 15),
    "PM": range(15, 20),
    "Bed": list(range(20, 24)) + list(range(0, 5)),
}

# ---------------- CSV helpers ----------------
def ensure_csv(path, headers):
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(headers)

def read_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def append_row(path, headers, row):
    ensure_csv(path, headers)
    file_exists = os.path.exists(path) and os.path.getsize(path) > 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        if not file_exists:
            w.writeheader()
        w.writerow(row)

def write_all(path, headers, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow(r)

def days_mask_to_names(mask):
    """Convert '1010100' → 'Mon Wed Fri'."""
    DAYS_LOCAL = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    if len(mask) != 7:
        return mask
    return " ".join(DAYS_LOCAL[i] for i, ch in enumerate(mask) if ch == "1") or "(none)"

# ---------------- SnoozeManager ----------------
class SnoozeManager:
    def __init__(self, path=SNOOZE_CSV):
        self.path = path
        ensure_csv(self.path, SNOOZE_HEADERS)

    def add(self, med_id, scheduled_dt, new_dt):
        row = {
            "med_id": str(med_id),
            "scheduled_dt": scheduled_dt.strftime(DATE_FMT),
            "new_dt": new_dt.strftime(DATE_FMT),
        }
        if PANDAS_OK:
            try:
                df = pd.read_csv(self.path)
                df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
                df.to_csv(self.path, index=False)
                return
            except Exception:
                pass
        append_row(self.path, SNOOZE_HEADERS, row)

    def get_today(self):
        """Return {(med_id, scheduled_iso): new_dt} for today only."""
        today = datetime.now().strftime("%Y-%m-%d")
        out = {}
        if PANDAS_OK:
            try:
                df = pd.read_csv(self.path)
                df = df[df["new_dt"].astype(str).str.startswith(today)]
                for _, r in df.iterrows():
                    try:
                        out[(str(r["med_id"]), str(r["scheduled_dt"]))] = datetime.strptime(
                            str(r["new_dt"]), DATE_FMT
                        )
                    except Exception:
                        pass
                return out
            except Exception:
                pass
        for r in read_rows(self.path):
            nd = str(r.get("new_dt", ""))
            if nd.startswith(today):
                try:
                    out[(str(r.get("med_id", "")), str(r.get("scheduled_dt", "")))] = datetime.strptime(
                        nd, DATE_FMT
                    )
                except Exception:
                    pass
        return out

    def cleanup_old(self, keep_days=1):
        cutoff = datetime.now() - timedelta(days=keep_days)
        kept = []
        if PANDAS_OK:
            try:
                df = pd.read_csv(self.path)
                if df.empty:
                    return
                df["__nd"] = pd.to_datetime(df["new_dt"], errors="coerce", format=DATE_FMT)
                df = df[df["__nd"] > cutoff]
                df.drop(columns=["__nd"], inplace=True, errors="ignore")
                df.to_csv(self.path, index=False)
                return
            except Exception:
                pass
        for r in read_rows(self.path):
            try:
                if datetime.strptime(r.get("new_dt", ""), DATE_FMT) > cutoff:
                    kept.append(r)
            except Exception:
                pass
        write_all(self.path, SNOOZE_HEADERS, kept)

# ---------------- helpers ----------------
def coerce_days_mask_from_bools(day_bools):
    # Monday=0 .. Sunday=6
    return "".join("1" if b else "0" for b in day_bools)

def is_day_active(mask, d):
    return len(mask) == 7 and mask[d.weekday()] == "1"

def bucket_for_hour(h):
    for label, hours in BUCKETS.items():
        if h in hours:
            return label
    return "AM"

def next_med_id(rows):
    max_id = 0
    for r in rows:
        try:
            max_id = max(max_id, int(r["med_id"]))
        except Exception:
            pass
    return max_id + 1

def log_action(med_id, sched_dt, action, actual_dt=None):
    rows = read_rows(LOG_CSV)
    next_id = 1
    for r in rows:
        try:
            next_id = max(next_id, int(r["log_id"]) + 1)
        except Exception:
            pass
    row = {
        "log_id": str(next_id),
        "med_id": str(med_id),
        "scheduled_dt": sched_dt.strftime(DATE_FMT),
        "action": action,
        "actual_dt": (actual_dt or datetime.now()).strftime(DATE_FMT),
    }
    append_row(LOG_CSV, LOG_HEADERS, row)

def is_already_logged(med_id, sched_dt):
    key = (str(med_id), sched_dt.strftime(DATE_FMT))
    for r in read_rows(LOG_CSV):
        if r.get("med_id") == key[0] and r.get("scheduled_dt") == key[1]:
            return True
    return False

# ---------------- Tkinter app ----------------
class PillBoxApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PillBox — Version 2 (Progress)")
        # wider window to show all 7 days and table columns
        self.geometry("1200x720")
        self.resizable(False, False)

        # current med being edited (None = new)
        self.current_edit_med_id = None
        
        # Testing override: allow user to set a specific day/time
        self.override_datetime = None

        # Style
        try:
            style = ttk.Style(self)
            style.theme_use("clam")
            style.configure("Title.TLabel", font=("Segoe UI", 13, "bold"))
            style.configure("Label.TLabel", font=("Segoe UI", 10))
            style.configure("Bold.TLabel", font=("Segoe UI", 10, "bold"))
            style.configure("TButton", padding=6)
        except Exception:
            pass

        # CSVs
        ensure_csv(SCHEDULE_CSV, SCHEDULE_HEADERS)
        ensure_csv(LOG_CSV, LOG_HEADERS)
        ensure_csv(SNOOZE_CSV, SNOOZE_HEADERS)

        self.snooze_mgr = SnoozeManager()
        self.snooze_mgr.cleanup_old(keep_days=2)

        # Tabs
        self.tabs = ttk.Notebook(self)
        self.tab_grid = ttk.Frame(self.tabs, padding=12)
        self.tab_edit = ttk.Frame(self.tabs, padding=12)
        self.tab_summary = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(self.tab_grid, text="Pillbox")
        self.tabs.add(self.tab_edit, text="Add/Edit")
        self.tabs.add(self.tab_summary, text="Summary")
        self.tabs.pack(fill="both", expand=True)

        self._build_grid_tab()
        self._build_edit_tab()
        self._build_summary_tab()

        ttk.Label(self, text="PillBox v2 — Version 2 progress", anchor="center").pack(
            side="bottom", fill="x", pady=6
        )
        self._update_grid_colors()
        self._scheduler_loop()

    # ---------- week schedule (Mon..Sun) ----------
    def _build_week_schedule(self):
        rows = read_rows(SCHEDULE_CSV)
        # Use override datetime if set, otherwise use real time
        if self.override_datetime:
            today = self.override_datetime.date()
        else:
            today = date.today()
        monday = today - timedelta(days=today.weekday())
        today_snoozes = self.snooze_mgr.get_today()
        out = []
        for d_off in range(7):
            d = monday + timedelta(days=d_off)
            for r in rows:
                if str(r.get("active", "1")).strip().lower() not in ["1", "true", "yes"]:
                    continue
                if not is_day_active(r.get("days_mask", "1111111"), d):
                    continue
                for part in (r.get("times_csv", "") or "").split(","):
                    p = part.strip()
                    if len(p) == 5 and p[2] == ":":
                        try:
                            hh, mm = map(int, p.split(":"))
                            sched = datetime.combine(d, time(hh, mm))
                            iso = sched.strftime(DATE_FMT)
                            # apply snoozes to TODAY only
                            if d == today and (str(r["med_id"]), iso) in today_snoozes:
                                sched = today_snoozes[(str(r["med_id"]), iso)]
                                iso = sched.strftime(DATE_FMT)
                            out.append(
                                {
                                    "med_id": str(r["med_id"]),
                                    "med_name": r["med_name"],
                                    "dose": r["dose"],
                                    "scheduled_dt": sched,
                                    "scheduled_iso": iso,
                                }
                            )
                        except Exception:
                            pass
        return sorted(out, key=lambda d: d["scheduled_dt"])

    # ---------- grid tab ----------
    def _build_grid_tab(self):
        ttk.Label(
            self.tab_grid,
            text="Weekly Pillbox (Mon–Sun × AM/Noon/PM/Bed)",
            style="Title.TLabel",
        ).pack(pady=(0, 10))
        
        # Testing override controls
        override_frame = ttk.LabelFrame(self.tab_grid, text="Testing Override", padding=8)
        override_frame.pack(pady=(0, 10), fill="x")
        
        controls_row = ttk.Frame(override_frame)
        controls_row.pack()
        
        ttk.Label(controls_row, text="Test Day:").pack(side="left", padx=(0, 4))
        self.override_day_var = tk.StringVar(value=DAYS[date.today().weekday()])
        self.cb_override_day = ttk.Combobox(
            controls_row, 
            values=DAYS, 
            width=6, 
            textvariable=self.override_day_var,
            state="readonly"
        )
        self.cb_override_day.pack(side="left", padx=4)
        
        ttk.Label(controls_row, text="Time:").pack(side="left", padx=(12, 4))
        
        test_hours = [f"{h:02d}" for h in range(24)]
        test_minutes = [f"{m:02d}" for m in range(0, 60, 5)]
        
        self.override_hour_var = tk.StringVar(value=datetime.now().strftime("%H"))
        self.cb_override_hour = ttk.Combobox(
            controls_row,
            values=test_hours,
            width=4,
            textvariable=self.override_hour_var,
            state="readonly"
        )
        self.cb_override_hour.pack(side="left")
        
        ttk.Label(controls_row, text=":", style="Bold.TLabel").pack(side="left", padx=2)
        
        self.override_minute_var = tk.StringVar(value=datetime.now().strftime("%M"))
        self.cb_override_minute = ttk.Combobox(
            controls_row,
            values=test_minutes,
            width=4,
            textvariable=self.override_minute_var,
            state="readonly"
        )
        self.cb_override_minute.pack(side="left", padx=(0, 12))
        
        ttk.Button(
            controls_row, 
            text="Apply Override", 
            command=self._apply_override
        ).pack(side="left", padx=4)
        
        ttk.Button(
            controls_row, 
            text="Clear (Use Real Time)", 
            command=self._clear_override
        ).pack(side="left", padx=4)
        
        self.override_status_label = ttk.Label(
            override_frame, 
            text="Using real time", 
            foreground="gray"
        )
        self.override_status_label.pack(pady=(4, 0))
        frame = ttk.Frame(self.tab_grid)
        frame.pack(pady=10)

        ttk.Label(frame, text="", style="Bold.TLabel").grid(row=0, column=0, padx=6, pady=6)
        for j, day in enumerate(DAYS, start=1):
            ttk.Label(frame, text=day, style="Bold.TLabel").grid(row=0, column=j, padx=6, pady=6)

        self.grid_labels = {}
        for i, bucket in enumerate(["AM", "Noon", "PM", "Bed"], start=1):
            ttk.Label(frame, text=bucket, style="Bold.TLabel").grid(
                row=i, column=0, padx=6, pady=6, sticky="e"
            )
            for j in range(1, 8):
                lbl = tk.Label(frame, text=" ", width=16, height=3, relief="groove", bg="#f2f2f2")
                lbl.grid(row=i, column=j, padx=3, pady=3)
                self.grid_labels[(bucket, j - 1)] = lbl

        legend = ttk.Frame(self.tab_grid)
        legend.pack(pady=8)
        for color, text in [
            ("#90ee90", "Taken"),
            ("#ffcccb", "Skipped"),
            ("#d0e0ff", "Snoozed"),
            ("#fff59d", "Due soon (today)"),
            ("#f2f2f2", "Idle"),
        ]:
            box = tk.Label(legend, width=3, height=1, bg=color, relief="groove")
            box.pack(side="left", padx=6)
            ttk.Label(legend, text=text).pack(side="left", padx=8)

        btns = ttk.Frame(self.tab_grid)
        btns.pack(pady=6)
        ttk.Button(btns, text="Refresh", command=self._refresh_ui).pack(side="left", padx=4)
        ttk.Button(btns, text="Clear old snoozes", command=lambda: self._clear_old_snoozes(1)).pack(
            side="left", padx=4
        )

    def _apply_override(self):
        """Apply the day/time override for testing."""
        try:
            # Get selected day index
            day_name = self.override_day_var.get()
            day_idx = DAYS.index(day_name)
            
            # Get selected time
            hour = int(self.override_hour_var.get())
            minute = int(self.override_minute_var.get())
            
            # Calculate the date for that day in current week
            today = date.today()
            current_day_idx = today.weekday()
            days_diff = day_idx - current_day_idx
            target_date = today + timedelta(days=days_diff)
            
            # Create override datetime
            self.override_datetime = datetime.combine(target_date, time(hour, minute))
            
            # Update status
            self.override_status_label.config(
                text=f"Testing at: {self.override_datetime.strftime('%A, %Y-%m-%d %H:%M')}",
                foreground="#0066cc"
            )
            
            # Refresh the UI
            self._refresh_ui()
            
        except Exception as e:
            messagebox.showerror("Override Error", f"Failed to apply override: {e}")
    
    def _clear_override(self):
        """Clear the override and return to real time."""
        self.override_datetime = None
        self.override_status_label.config(
            text="Using real time",
            foreground="gray"
        )
        # Reset to current time
        now = datetime.now()
        self.override_day_var.set(DAYS[now.weekday()])
        self.override_hour_var.set(now.strftime("%H"))
        self.override_minute_var.set(now.strftime("%M"))
        self._refresh_ui()
    
    def _clear_old_snoozes(self, keep_days):
        self.snooze_mgr.cleanup_old(keep_days)
        messagebox.showinfo("Snoozes", f"Old snoozes cleared (> {keep_days} day).")

    def _refresh_ui(self):
        self._update_grid_colors()
        self._draw_summary()
        self.update_idletasks()

    def _update_grid_colors(self):
        # reset
        for lbl in self.grid_labels.values():
            lbl.config(bg="#f2f2f2", text=" ")

        week = self._build_week_schedule()
        logs = read_rows(LOG_CSV)
        # {(med_id, scheduled_iso): action}
        act_map = {
            (r.get("med_id", ""), r.get("scheduled_dt", "")): (r.get("action", "") or "")
            for r in logs
        }

        # Use override datetime if set
        if self.override_datetime:
            today = self.override_datetime.date()
            now = self.override_datetime
        else:
            today = date.today()
            now = datetime.now()
        for item in week:
            dt = item["scheduled_dt"]
            bucket = bucket_for_hour(dt.hour)
            col = dt.weekday()
            key = (item["med_id"], dt.strftime(DATE_FMT))
            cell = self.grid_labels.get((bucket, col))
            if not cell:
                continue

            text = f"{item['med_name']}\n{item['dose']}\n{dt.strftime('%H:%M')}"
            if key in act_map:
                a = act_map[key]
                if a == "taken":
                    cell.config(bg="#90ee90", text=text)
                elif a == "skipped":
                    cell.config(bg="#ffcccb", text=text)
                elif a == "snoozed":
                    cell.config(
                        bg="#d0e0ff",
                        text=f"{item['med_name']}\n(snoozed)\n{dt.strftime('%H:%M')}",
                    )
                else:
                    cell.config(text=text)
            else:
                if dt.date() == today and abs((now - dt).total_seconds()) <= 15 * 60:
                    cell.config(bg="#fff59d", text=text)
                else:
                    cell.config(text=text)

        self.update_idletasks()

    # ---------- Add/Edit tab ----------
    def _build_edit_tab(self):
        ttk.Label(
            self.tab_edit, text="Add Medication", style="Title.TLabel"
        ).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))

        # Name / Dose
        ttk.Label(self.tab_edit, text="Name:", style="Label.TLabel").grid(
            row=1, column=0, sticky="e", padx=6, pady=4
        )
        self.ent_name = ttk.Entry(self.tab_edit, width=32)
        self.ent_name.grid(row=1, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(self.tab_edit, text="Dose (e.g., 500 mg):", style="Label.TLabel").grid(
            row=2, column=0, sticky="e", padx=6, pady=4
        )
        self.ent_dose = ttk.Entry(self.tab_edit, width=32)
        self.ent_dose.grid(row=2, column=1, sticky="w", padx=6, pady=4)

        # ---- Time pickers in one compact row ----
        ttk.Label(self.tab_edit, text="Add Time (24h):", style="Label.TLabel").grid(
            row=3, column=0, sticky="e", padx=6, pady=4
        )

        time_frame = ttk.Frame(self.tab_edit)
        time_frame.grid(row=3, column=1, columnspan=3, sticky="w", padx=6, pady=4)

        hours = [f"{h:02d}" for h in range(24)]
        minutes = [f"{m:02d}" for m in range(0, 60, 5)]

        self.cb_hour = ttk.Combobox(time_frame, values=hours, width=4, state="readonly")
        self.cb_hour.set("08")
        self.cb_hour.pack(side="left")

        ttk.Label(time_frame, text=":", style="Bold.TLabel").pack(side="left", padx=(2, 2))

        self.cb_minute = ttk.Combobox(time_frame, values=minutes, width=4, state="readonly")
        self.cb_minute.set("00")
        self.cb_minute.pack(side="left")

        ttk.Button(time_frame, text="Add time", command=self._add_time_to_list).pack(
            side="left", padx=(6, 0)
        )

        # Times list
        ttk.Label(self.tab_edit, text="Times:", style="Label.TLabel").grid(
            row=4, column=0, sticky="e", padx=6, pady=4
        )

        self.times_listbox = tk.Listbox(self.tab_edit, height=4, width=18)
        self.times_listbox.grid(row=4, column=1, sticky="w", padx=6, pady=4)
        ttk.Button(
            self.tab_edit, text="Remove selected", command=self._remove_selected_time
        ).grid(row=4, column=2, sticky="w", padx=6)

        self.current_times = []

        # Day checkboxes
        ttk.Label(self.tab_edit, text="Days:", style="Label.TLabel").grid(
            row=5, column=0, sticky="e", padx=6, pady=4
        )
        self.day_vars = [tk.BooleanVar(value=True) for _ in range(7)]
        daysf = ttk.Frame(self.tab_edit)
        daysf.grid(row=5, column=1, columnspan=4, sticky="w")
        for i, d in enumerate(DAYS):
            ttk.Checkbutton(daysf, text=d, variable=self.day_vars[i]).grid(
                row=0, column=i, padx=(0, 6), sticky="w"
            )

        # Active
        self.var_active = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.tab_edit, text="Active", variable=self.var_active).grid(
            row=6, column=1, sticky="w", padx=6, pady=4
        )

        # Save
        ttk.Button(self.tab_edit, text="Save Medication", command=self._save_medication).grid(
            row=7, column=1, sticky="w", padx=6, pady=(10, 4)
        )

        # Viewer (table)
        ttk.Label(
            self.tab_edit,
            text="Current Medications",
            style="Bold.TLabel",
        ).grid(row=8, column=0, columnspan=6, sticky="w", pady=(14, 4))

        view_cols = ["med_id", "med_name", "dose", "times_csv", "days", "active"]
        self.tree = ttk.Treeview(self.tab_edit, columns=view_cols, show="headings", height=8)

        col_widths = {
            "med_id": 70,
            "med_name": 160,
            "dose": 120,
            "times_csv": 160,
            "days": 220,
            "active": 70,
        }

        for col in view_cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=col_widths[col], anchor="w", stretch=True)

        self.tree.grid(row=9, column=0, columnspan=6, sticky="nsew", padx=6, pady=6)

        # allow resizing to avoid clipping
        self.tab_edit.columnconfigure(1, weight=1)
        self.tab_edit.columnconfigure(2, weight=1)
        self.tab_edit.columnconfigure(3, weight=1)
        self.tab_edit.columnconfigure(4, weight=1)

        # Table action buttons
        ttk.Button(
            self.tab_edit, text="Reload list", command=self._reload_schedule_view
        ).grid(row=10, column=0, sticky="w", padx=6, pady=(0, 10))

        ttk.Button(
            self.tab_edit, text="Edit selected", command=self._edit_selected_med
        ).grid(row=10, column=1, sticky="w", padx=6, pady=(0, 10))

        ttk.Button(
            self.tab_edit, text="Delete selected", command=self._delete_selected_med
        ).grid(row=10, column=2, sticky="w", padx=6, pady=(0, 10))

        self._reload_schedule_view()

    def _add_time_to_list(self):
        hh, mm = self.cb_hour.get(), self.cb_minute.get()
        if hh and mm:
            val = f"{hh}:{mm}"
            if val not in self.current_times:
                self.current_times.append(val)
                self.current_times.sort()
                self.times_listbox.delete(0, tk.END)
                for t in self.current_times:
                    self.times_listbox.insert(tk.END, t)
        self.update_idletasks()

    def _remove_selected_time(self):
        sel = self.times_listbox.curselection()
        if sel:
            val = self.times_listbox.get(sel[0])
            if val in self.current_times:
                self.current_times.remove(val)
            self.times_listbox.delete(sel[0])
        self.update_idletasks()

    def _reload_schedule_view(self):
        # Clear previous rows
        for i in self.tree.get_children():
            self.tree.delete(i)

        # Insert rows with readable day names
        for r in read_rows(SCHEDULE_CSV):
            display_row = [
                r.get("med_id", ""),
                r.get("med_name", ""),
                r.get("dose", ""),
                r.get("times_csv", ""),
                days_mask_to_names(r.get("days_mask", "1111111")),
                r.get("active", "1"),
            ]
            self.tree.insert("", tk.END, values=display_row)

    # --------- NEW: helper to load a row into the form ---------
    def _load_med_into_form(self, med_row):
        """Fill the Add/Edit form from a med_row dict."""
        # Name & dose
        self.ent_name.delete(0, tk.END)
        self.ent_name.insert(0, med_row.get("med_name", ""))

        self.ent_dose.delete(0, tk.END)
        self.ent_dose.insert(0, med_row.get("dose", ""))

        # Times
        self.current_times.clear()
        self.times_listbox.delete(0, tk.END)
        times_csv = med_row.get("times_csv", "")
        for t in [p.strip() for p in times_csv.split(",") if p.strip()]:
            self.current_times.append(t)
        self.current_times.sort()
        for t in self.current_times:
            self.times_listbox.insert(tk.END, t)

        # Days
        mask = med_row.get("days_mask", "1111111")
        for i, var in enumerate(self.day_vars):
            bit = mask[i] if i < len(mask) else "0"
            var.set(bit == "1")

        # Active
        active_val = str(med_row.get("active", "1")).strip().lower()
        self.var_active.set(active_val in ["1", "true", "yes"])

    def _edit_selected_med(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Edit", "Please select a medication in the table.")
            return

        values = self.tree.item(sel[0], "values")
        med_id = str(values[0])
        if not med_id:
            messagebox.showwarning("Edit", "Selected row has no med_id.")
            return

        rows = read_rows(SCHEDULE_CSV)
        target = None
        for r in rows:
            if str(r.get("med_id", "")) == med_id:
                target = r
                break

        if target is None:
            messagebox.showerror("Edit", f"Medication with id={med_id} not found in CSV.")
            return

        # store current id for update on save
        self.current_edit_med_id = med_id
        self._load_med_into_form(target)
        self.tabs.select(self.tab_edit)
        messagebox.showinfo("Edit", f"Loaded medication ID {med_id} for editing.\n"
                                    "After changes, click 'Save Medication' to update.")

    def _delete_selected_med(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Delete", "Please select a medication in the table.")
            return

        values = self.tree.item(sel[0], "values")
        med_id = str(values[0])
        if not med_id:
            messagebox.showwarning("Delete", "Selected row has no med_id.")
            return

        ans = messagebox.askyesno(
            "Delete",
            f"Do you want to mark medication ID {med_id} as inactive?",
        )
        if not ans:
            return

        rows = read_rows(SCHEDULE_CSV)
        changed = False
        for r in rows:
            if str(r.get("med_id", "")) == med_id:
                r["active"] = "0"
                changed = True

        if not changed:
            messagebox.showerror("Delete", f"Medication with id={med_id} not found.")
            return

        write_all(SCHEDULE_CSV, SCHEDULE_HEADERS, rows)
        if self.current_edit_med_id == med_id:
            self.current_edit_med_id = None

        self._reload_schedule_view()
        self._update_grid_colors()
        self.update_idletasks()
        messagebox.showinfo("Delete", f"Medication {med_id} has been marked inactive.")

    def _save_medication(self):
        name = self.ent_name.get().strip()
        dose = self.ent_dose.get().strip()
        times = list(self.current_times)
        days_mask = coerce_days_mask_from_bools([v.get() for v in self.day_vars])
        active = "1" if self.var_active.get() else "0"

        if not name or not dose:
            messagebox.showerror("Missing", "Please enter a Name and a Dose.")
            return
        if not times:
            messagebox.showerror("No times", "Please add at least one time using the dropdowns.")
            return

        rows = read_rows(SCHEDULE_CSV)

        # If editing an existing medication, update it
        if self.current_edit_med_id is not None:
            med_id = self.current_edit_med_id
            updated = False
            for r in rows:
                if str(r.get("med_id", "")) == med_id:
                    r["med_name"] = name
                    r["dose"] = dose
                    r["times_csv"] = ",".join(times)
                    r["days_mask"] = days_mask
                    r["active"] = active
                    updated = True
                    break
            if not updated:
                messagebox.showerror("Save", f"Could not find medication id={med_id} to update.")
                return
            write_all(SCHEDULE_CSV, SCHEDULE_HEADERS, rows)
            messagebox.showinfo("Saved", f"Medication id={med_id} updated.")
            self.current_edit_med_id = None
        else:
            # New medication
            new_id = next_med_id(rows)
            row = {
                "med_id": str(new_id),
                "med_name": name,
                "dose": dose,
                "times_csv": ",".join(times),
                "days_mask": days_mask,
                "active": active,
            }
            append_row(SCHEDULE_CSV, SCHEDULE_HEADERS, row)
            messagebox.showinfo("Saved", f"Medication '{name}' added (id={new_id}).")

        self._reload_schedule_view()
        self._update_grid_colors()
        self.update_idletasks()

        # clear inputs
        self.ent_name.delete(0, tk.END)
        self.ent_dose.delete(0, tk.END)
        self.current_times.clear()
        self.times_listbox.delete(0, tk.END)

    # ---------- Summary tab ----------
    def _build_summary_tab(self):
        ttk.Label(
            self.tab_summary,
            text="Weekly Summary (last 7 days)",
            style="Title.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        self.summary_container = ttk.Frame(self.tab_summary)
        self.summary_container.pack(fill="both", expand=True)
        self._draw_summary()

        util = ttk.Frame(self.tab_summary)
        util.pack(pady=6)
        ttk.Button(util, text="Refresh summary", command=self._draw_summary).pack(
            side="left", padx=4
        )

    def _draw_summary(self):
        for w in self.summary_container.winfo_children():
            w.destroy()
        if not MATPLOTLIB_OK:
            ttk.Label(
                self.summary_container, text="Matplotlib not available. Chart disabled."
            ).pack(pady=16)
            return

        logs = read_rows(LOG_CSV)
        cutoff = datetime.now() - timedelta(days=7)
        counts = {"taken": 0, "snoozed": 0, "skipped": 0}
        for r in logs:
            try:
                when = datetime.strptime(r.get("actual_dt", ""), DATE_FMT)
                if when >= cutoff:
                    a = (r.get("action") or "").strip()
                    if a in counts:
                        counts[a] += 1
            except Exception:
                pass

        fig = Figure(figsize=(5.6, 3.4), dpi=120)
        ax = fig.add_subplot(111)
        ax.bar(list(counts.keys()), list(counts.values()))
        ax.set_title("Actions in last 7 days")
        ax.set_ylabel("Count")

        canvas = FigureCanvasTkAgg(fig, master=self.summary_container)
        canvas.draw()
        canvas.get_tk_widget().pack()
        self.update_idletasks()

    # ---------- scheduler (today only for popups) ----------
    def _scheduler_loop(self):
        try:
            # Use override datetime if set
            if self.override_datetime:
                now = self.override_datetime
                today = self.override_datetime.date()
            else:
                now = datetime.now()
                today = date.today()
            for item in self._build_week_schedule():
                if item["scheduled_dt"].date() != today:
                    continue
                sched = item["scheduled_dt"]
                if (
                    abs((now - sched).total_seconds()) <= 60
                    and not is_already_logged(item["med_id"], sched)
                ):
                    self._show_due_popup(item)
                    break
        except Exception as e:
            print("Scheduler error:", e)

        self._update_grid_colors()
        self.after(10_000, self._scheduler_loop)

    def _show_due_popup(self, item):
        top = tk.Toplevel(self)
        top.title("Dose Due")
        top.grab_set()

        ttk.Label(top, text="Medication due now:", style="Bold.TLabel").pack(
            padx=16, pady=(16, 8)
        )
        ttk.Label(
            top,
            text=f"{item['med_name']} — {item['dose']} (due {item['scheduled_dt'].strftime('%H:%M')})",
        ).pack(padx=16, pady=(0, 12))

        # Snooze minutes dropdown
        row = ttk.Frame(top)
        row.pack(pady=(0, 10))
        ttk.Label(row, text="Snooze for (minutes):").pack(side="left", padx=(0, 6))
        snooze_choices = ["5", "10", "15", "30", "60"]
        snooze_var = tk.StringVar(value="10")
        ttk.Combobox(
            row,
            values=snooze_choices,
            width=5,
            textvariable=snooze_var,
            state="readonly",
        ).pack(side="left")

        btns = ttk.Frame(top)
        btns.pack(pady=10)

        def do_take():
            log_action(item["med_id"], item["scheduled_dt"], "taken", datetime.now())
            self._update_grid_colors()
            self.update_idletasks()
            top.destroy()
            messagebox.showinfo("Logged", "Marked as TAKEN.")

        def do_snooze():
            try:
                mins = int(snooze_var.get())
            except Exception:
                mins = 10
            new_dt = item["scheduled_dt"] + timedelta(minutes=mins)
            self.snooze_mgr.add(item["med_id"], item["scheduled_dt"], new_dt)
            log_action(item["med_id"], item["scheduled_dt"], "snoozed", datetime.now())
            self._update_grid_colors()
            self.update_idletasks()
            top.destroy()
            messagebox.showinfo("Snoozed", f"Snoozed for {mins} minutes.")

        def do_skip():
            log_action(item["med_id"], item["scheduled_dt"], "skipped", datetime.now())
            self._update_grid_colors()
            self.update_idletasks()
            top.destroy()
            messagebox.showinfo("Logged", "Marked as SKIPPED.")

        ttk.Button(btns, text="Take", command=do_take).pack(side="left", padx=6)
        ttk.Button(btns, text="Snooze", command=do_snooze).pack(side="left", padx=6)
        ttk.Button(btns, text="Skip", command=do_skip).pack(side="left", padx=6)
        ttk.Button(top, text="Close", command=top.destroy).pack(pady=(0, 12))
        top.update()  # paint immediately

# ---------------- main ----------------
if __name__ == "__main__":
    app = PillBoxApp()
    app.mainloop()
