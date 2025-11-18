# this code does not run, it's just to show the context of the file
class SnoozeManager:
    def __init__(self, SNOOZE_CSV: str = "snoozes.csv"):

        self.SNOOZE_CSV = SNOOZE_CSV
        self.overrides = {}

        # if needed, load existing snoozes from CSV to dict otherwise create new csv file
        if not os.path.exists(SNOOZE_CSV):
            with open(SNOOZE_CSV, "w") as f:
                f.write("med_id,scheduled_iso,new_dt_iso\n")
        else:
            df = pandas.read_csv(SNOOZE_CSV)
            for _, row in df.iterrows(): # make dictionary of overrides (maybe switch to using a dataframe?)
                self.overrides[(row["med_id"], row["scheduled_iso"])] = datetime.fromisoformat(row["new_dt_iso"])

    def save_snoozes(self):
        # save current overrides dict to CSV
        with open(self.SNOOZE_CSV, "w") as f:
            f.write("med_id,scheduled_iso,new_dt_iso\n")
            for (med_id, scheduled_iso), new_dt in self.overrides.items():
                f.write(f"{med_id},{scheduled_iso},{new_dt.isoformat()}\n")
    
    def add_snooze(self, med_id: str, scheduled_iso: str, new_dt: datetime):
        self.overrides[(med_id, scheduled_iso)] = new_dt
        self.save_snoozes()
    
    def get_override(self, med_id: str, scheduled_iso: str) -> datetime | None:
        return self.overrides.get((med_id, scheduled_iso))


# Create global instance (still global but encapsulated)
# use instead of your previous global SNOOZE_OVERRIDES = {}
snooze_manager = SnoozeManager()

def build_today_schedule() -> list[dict]:
    # ...existing code...
    override = snooze_manager.get_override(r["med_id"], scheduled_iso)
    # ...rest of function...