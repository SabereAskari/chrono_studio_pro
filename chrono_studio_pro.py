"""
Chrono Studio Pro
تایمر و کورنومتر با رابط گرافیکی، حلقه‌ی متحرک، تاریخچه‌ی محلی و میان‌برها.

نصب:
    python -m pip install customtkinter

اجرا:
    python chrono_studio_pro.py
"""
import json
import math
import os
import time
import tkinter as tk
from datetime import datetime

import customtkinter as ctk

try:
    import winsound  # فقط ویندوز
except ImportError:
    winsound = None


# ---------------- تنظیمات برنامه ----------------
APP_NAME = "Chrono Studio Pro"
BG = "#0B1020"
PANEL = "#121A2B"
PANEL_2 = "#19253A"
TEXT = "#F3F6FF"
MUTED = "#91A0B8"
CYAN = "#42DDE0"
PURPLE = "#8065FF"
GREEN = "#2DD4A7"
RED = "#FF657F"
YELLOW = "#F6C96B"

APP_DIR = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "ChronoStudioPro")
HISTORY_FILE = os.path.join(APP_DIR, "history.json")
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")


def format_time(seconds, centiseconds=False):
    seconds = max(0.0, float(seconds))
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    result = f"{hours:02d}:{minutes:02d}:{secs:02d}"
    if centiseconds:
        result += f".{int((seconds - total) * 100):02d}"
    return result


def ensure_app_dir():
    os.makedirs(APP_DIR, exist_ok=True)


class ChronoStudioPro(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("980x720")
        self.minsize(820, 650)
        self.configure(fg_color=BG)

        ensure_app_dir()
        self.settings = self._load_json(SETTINGS_FILE, {"sound_enabled": True, "sound_type": "Beep"})
        self.history = self._load_json(HISTORY_FILE, [])

        # Timer state
        self.timer_running = False
        self.timer_deadline = 0.0
        self.timer_remaining = 300.0
        self.timer_initial = 300.0
        self.timer_job = None
        self.timer_finished_for_run = False

        # Stopwatch state
        self.sw_running = False
        self.sw_started_at = 0.0
        self.sw_elapsed = 0.0
        self.sw_job = None
        self.laps = []

        self._build_ui()
        self._draw_ring(1.0, CYAN)
        self._render_history()
        self._refresh_clock()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # میان‌برهای صفحه‌کلید
        self.bind("<space>", self._shortcut_space)
        self.bind("<Control-r>", self._shortcut_reset)
        self.bind("<Control-l>", self._shortcut_lap)
        self.bind("<Escape>", lambda _e: self.focus_set())

    # ---------- فایل‌ها ----------
    def _load_json(self, path, default):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return default

    def _save_json(self, path, data):
        ensure_app_dir()
        temp_path = path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)

    def _save_settings(self):
        self.settings["sound_enabled"] = bool(self.sound_var.get())
        self.settings["sound_type"] = self.sound_type_var.get()
        self._save_json(SETTINGS_FILE, self.settings)

    def _add_history(self, kind, duration, details=""):
        entry = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": kind,
            "duration": round(float(duration), 2),
            "formatted": format_time(duration, centiseconds=(kind == "Stopwatch")),
            "details": details,
        }
        self.history.insert(0, entry)
        self.history = self.history[:100]
        self._save_json(HISTORY_FILE, self.history)
        self._render_history()

    # ---------- رابط کاربری ----------
    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=26, pady=(20, 12))

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(left, text="CHRONO  /  STUDIO PRO",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=CYAN).pack(anchor="w")
        ctk.CTkLabel(left, text="زمان، در کنترل تو",
                     font=ctk.CTkFont(size=27, weight="bold"),
                     text_color=TEXT).pack(anchor="w", pady=(3, 0))

        self.clock_label = ctk.CTkLabel(header, text="",
                                        font=ctk.CTkFont(family="Consolas", size=13),
                                        text_color=MUTED)
        self.clock_label.pack(side="right", padx=(10, 0))

        self.tabs = ctk.CTkTabview(
            self, fg_color=PANEL, corner_radius=18,
            segmented_button_fg_color=PANEL_2,
            segmented_button_selected_color=PURPLE,
            segmented_button_selected_hover_color="#6D53E8",
            segmented_button_unselected_color=PANEL_2,
            segmented_button_unselected_hover_color="#26344D",
        )
        self.tabs.pack(fill="both", expand=True, padx=26, pady=(0, 16))
        self.timer_tab = self.tabs.add("◉  تایمر")
        self.sw_tab = self.tabs.add("◷  کورنومتر")
        self.history_tab = self.tabs.add("▤  تاریخچه")
        self.settings_tab = self.tabs.add("⚙  تنظیمات")
        self._build_timer_tab()
        self._build_stopwatch_tab()
        self._build_history_tab()
        self._build_settings_tab()

        ctk.CTkLabel(
            self, text="SPACE شروع / مکث     •     CTRL + R ریست     •     CTRL + L ثبت دور",
            font=ctk.CTkFont(size=10), text_color="#65738D"
        ).pack(pady=(0, 12))

    def _card(self, parent, **kwargs):
        return ctk.CTkFrame(parent, fg_color="#0D1424", corner_radius=18,
                            border_width=1, border_color="#25334C", **kwargs)

    def _build_timer_tab(self):
        tab = self.timer_tab
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(tab, text="تایمر تمرکز",
                     font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=TEXT).grid(row=0, column=0, pady=(18, 10))

        main = self._card(tab)
        main.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 14))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(0, weight=1)

        visual = ctk.CTkFrame(main, fg_color="transparent")
        visual.grid(row=0, column=0, sticky="nsew", padx=12, pady=(10, 0))
        visual.grid_columnconfigure(0, weight=1)
        self.ring = tk.Canvas(visual, width=300, height=270, bg="#0D1424",
                              highlightthickness=0, bd=0)
        self.ring.grid(row=0, column=0, pady=(0, 0))
        self.ring.bind("<Configure>", lambda _e: self._draw_ring(self._timer_fraction(), self._timer_color()))

        self.timer_big = ctk.CTkLabel(visual, text="00:05:00",
                                      font=ctk.CTkFont(family="Consolas", size=34, weight="bold"),
                                      text_color=CYAN)
        self.timer_big.place(relx=0.5, rely=0.43, anchor="center")
        self.timer_status = ctk.CTkLabel(visual, text="آماده‌ی شروع",
                                         font=ctk.CTkFont(size=12), text_color=MUTED)
        self.timer_status.place(relx=0.5, rely=0.55, anchor="center")

        controls = ctk.CTkFrame(main, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 16))
        controls.grid_columnconfigure((0, 1, 2), weight=1)

        inputs = ctk.CTkFrame(controls, fg_color="transparent")
        inputs.grid(row=0, column=0, columnspan=3, pady=(0, 12))
        self.hour_var = tk.StringVar(value="00")
        self.minute_var = tk.StringVar(value="05")
        self.second_var = tk.StringVar(value="00")
        for i, (label, var) in enumerate([
            ("ساعت", self.hour_var), ("دقیقه", self.minute_var), ("ثانیه", self.second_var)
        ]):
            col = ctk.CTkFrame(inputs, fg_color="transparent")
            col.grid(row=0, column=i, padx=7)
            ctk.CTkLabel(col, text=label, text_color=MUTED,
                         font=ctk.CTkFont(size=11)).pack(pady=(0, 5))
            ent = ctk.CTkEntry(col, textvariable=var, width=76, height=36,
                               justify="center", fg_color=PANEL_2,
                               border_color="#34435F", text_color=TEXT)
            ent.pack()
            ent.bind("<FocusOut>", lambda _e: self._timer_preview())

        presets = ctk.CTkFrame(controls, fg_color="transparent")
        presets.grid(row=1, column=0, columnspan=3, pady=(0, 10))
        for label, secs in [("۱ دقیقه", 60), ("۵ دقیقه", 300), ("۱۵ دقیقه", 900), ("۲۵ دقیقه", 1500)]:
            ctk.CTkButton(presets, text=label, width=78, height=28,
                          fg_color=PANEL_2, hover_color="#2A3853",
                          text_color=TEXT, corner_radius=8,
                          command=lambda s=secs: self._set_preset(s)).pack(side="left", padx=3)

        ctk.CTkButton(controls, text="▶  شروع", height=40, fg_color=PURPLE,
                      hover_color="#6D53E8", command=self.start_timer
                      ).grid(row=2, column=0, sticky="ew", padx=4)
        ctk.CTkButton(controls, text="Ⅱ  مکث / ادامه", height=40, fg_color=PANEL_2,
                      hover_color="#2A3853", text_color=TEXT, command=self.toggle_timer
                      ).grid(row=2, column=1, sticky="ew", padx=4)
        ctk.CTkButton(controls, text="↺  ریست", height=40, fg_color="#3A2030",
                      hover_color="#54283B", text_color="#FFB4C0", command=self.reset_timer
                      ).grid(row=2, column=2, sticky="ew", padx=4)

    def _build_stopwatch_tab(self):
        tab = self.sw_tab
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(tab, text="کورنومتر دقیق",
                     font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=TEXT).grid(row=0, column=0, pady=(18, 12))
        card = self._card(tab)
        card.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 14))
        self.sw_big = ctk.CTkLabel(card, text="00:00:00.00",
                                   font=ctk.CTkFont(family="Consolas", size=42, weight="bold"),
                                   text_color=GREEN)
        self.sw_big.pack(pady=(24, 10))
        ctk.CTkLabel(card, text="زمان با دقت صدم ثانیه",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(pady=(0, 20))

        buttons = ctk.CTkFrame(tab, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 10))
        buttons.grid_columnconfigure(0, weight=1)
        action_row = ctk.CTkFrame(buttons, fg_color="transparent")
        action_row.pack(fill="x", pady=(0, 12))
        ctk.CTkButton(action_row, text="▶  شروع", fg_color=PURPLE, hover_color="#6D53E8",
                      command=self.start_stopwatch).pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkButton(action_row, text="Ⅱ  توقف", fg_color=PANEL_2, hover_color="#2A3853",
                      text_color=TEXT, command=self.pause_stopwatch).pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkButton(action_row, text="＋  ثبت دور", fg_color="#173B3B", hover_color="#205352",
                      text_color="#9AF3E1", command=self.add_lap).pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkButton(action_row, text="↺  ریست", fg_color="#3A2030", hover_color="#54283B",
                      text_color="#FFB4C0", command=self.reset_stopwatch).pack(side="left", expand=True, fill="x", padx=4)

        lap_card = ctk.CTkFrame(buttons, fg_color=PANEL_2, corner_radius=12)
        lap_card.pack(fill="both", expand=True)
        ctk.CTkLabel(lap_card, text="دورهای ثبت‌شده  |  زمان کل و اختلاف هر دور",
                     text_color=MUTED, font=ctk.CTkFont(size=11, weight="bold")
                     ).pack(anchor="w", padx=12, pady=(10, 5))
        self.lap_box = ctk.CTkTextbox(lap_card, fg_color="#101827", text_color=TEXT,
                                      font=ctk.CTkFont(family="Consolas", size=12), height=140)
        self.lap_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.lap_box.insert("1.0", "هنوز دوری ثبت نشده است.")
        self.lap_box.configure(state="disabled")

    def _build_history_tab(self):
        tab = self.history_tab
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(18, 10))
        ctk.CTkLabel(top, text="فعالیت‌های ذخیره‌شده",
                     font=ctk.CTkFont(size=17, weight="bold"), text_color=TEXT).pack(side="left")
        ctk.CTkButton(top, text="پاک کردن تاریخچه", width=130, height=30,
                      fg_color="#3A2030", hover_color="#54283B",
                      text_color="#FFB4C0", command=self.clear_history).pack(side="right")
        self.history_box = ctk.CTkTextbox(tab, fg_color="#0D1424", text_color=TEXT,
                                          font=ctk.CTkFont(size=12), corner_radius=12)
        self.history_box.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))

    def _build_settings_tab(self):
        tab = self.settings_tab
        tab.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(tab, text="تنظیمات برنامه",
                     font=ctk.CTkFont(size=17, weight="bold"), text_color=TEXT
                     ).grid(row=0, column=0, sticky="w", padx=18, pady=(22, 18))
        card = ctk.CTkFrame(tab, fg_color="#0D1424", corner_radius=16)
        card.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 14))
        self.sound_var = tk.BooleanVar(value=bool(self.settings.get("sound_enabled", True)))
        self.sound_type_var = tk.StringVar(value=self.settings.get("sound_type", "Beep"))
        ctk.CTkCheckBox(card, text="فعال بودن صدای پایان تایمر",
                        variable=self.sound_var, text_color=TEXT,
                        fg_color=PURPLE, hover_color="#6D53E8",
                        command=self._save_settings).pack(anchor="w", padx=18, pady=(18, 12))
        ctk.CTkLabel(card, text="نوع صدا", text_color=MUTED).pack(anchor="w", padx=18)
        ctk.CTkOptionMenu(card, values=["Beep", "Alarm", "Chime"],
                          variable=self.sound_type_var, fg_color=PANEL_2,
                          button_color=PURPLE, button_hover_color="#6D53E8",
                          command=lambda _v: self._save_settings()).pack(anchor="w", padx=18, pady=(6, 18))
        ctk.CTkButton(card, text="تست صدا", width=120, fg_color=PANEL_2,
                      hover_color="#2A3853", command=self._play_sound).pack(anchor="w", padx=18, pady=(0, 18))
        info = ctk.CTkFrame(tab, fg_color=PANEL_2, corner_radius=12)
        info.grid(row=2, column=0, sticky="ew", padx=18, pady=8)
        ctk.CTkLabel(info, text="میان‌برها", text_color=CYAN,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(12, 6))
        ctk.CTkLabel(info, text="Space: شروع/مکث ابزار انتخاب‌شده\nCtrl + R: ریست ابزار انتخاب‌شده\nCtrl + L: ثبت دور در کورنومتر",
                     justify="left", text_color=TEXT, font=ctk.CTkFont(size=12)
                     ).pack(anchor="w", padx=14, pady=(0, 14))

    # ---------- حلقه‌ی تایمر ----------
    def _timer_fraction(self):
        if self.timer_initial <= 0:
            return 0.0
        return max(0.0, min(1.0, self.timer_remaining / self.timer_initial))

    def _timer_color(self):
        fraction = self._timer_fraction()
        if fraction <= 0.15:
            return RED
        if fraction <= 0.35:
            return YELLOW
        return CYAN

    def _draw_ring(self, fraction, color):
        if not hasattr(self, "ring"):
            return
        self.ring.delete("all")
        width = max(220, self.ring.winfo_width())
        height = max(220, self.ring.winfo_height())
        cx, cy = width / 2, height / 2
        radius = min(width, height) * 0.37
        box = (cx-radius, cy-radius, cx+radius, cy+radius)
        self.ring.create_oval(*box, outline="#26334B", width=13)
        # Canvas زاویه‌ی صفر را از سمت راست می‌گیرد؛ حلقه از بالا آغاز می‌شود.
        extent = max(0.0, min(1.0, fraction)) * 360
        if extent > 0:
            self.ring.create_arc(*box, start=90, extent=-extent, style="arc",
                                 outline=color, width=13)
        self.ring.create_oval(cx-3, cy-3, cx+3, cy+3, fill=color, outline="")

    def _timer_preview(self):
        if self.timer_running:
            return
        try:
            total = self._read_timer_inputs()
        except ValueError:
            return
        self.timer_remaining = self.timer_initial = total
        self.timer_big.configure(text=format_time(total), text_color=CYAN)
        self.timer_status.configure(text="آماده‌ی شروع", text_color=MUTED)
        self._draw_ring(1.0, CYAN)

    def _read_timer_inputs(self):
        try:
            h = int(self.hour_var.get() or "0")
            m = int(self.minute_var.get() or "0")
            s = int(self.second_var.get() or "0")
        except ValueError:
            raise ValueError("ساعت، دقیقه و ثانیه باید عدد صحیح باشند.")
        if min(h, m, s) < 0 or m > 59 or s > 59:
            raise ValueError("ساعت نمی‌تواند منفی باشد و دقیقه و ثانیه باید بین ۰ تا ۵۹ باشند.")
        total = h * 3600 + m * 60 + s
        if total <= 0:
            raise ValueError("زمان باید بیشتر از صفر باشد.")
        return total

    def _set_preset(self, seconds):
        self.pause_timer()
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        self.hour_var.set(f"{h:02d}")
        self.minute_var.set(f"{m:02d}")
        self.second_var.set(f"{s:02d}")
        self.timer_remaining = self.timer_initial = float(seconds)
        self.timer_finished_for_run = False
        self.timer_big.configure(text=format_time(seconds), text_color=CYAN)
        self.timer_status.configure(text="آماده‌ی شروع", text_color=MUTED)
        self._draw_ring(1, CYAN)

    def start_timer(self):
        if self.timer_running:
            return
        try:
            if self.timer_remaining <= 0 or self.timer_finished_for_run:
                self.timer_remaining = self._read_timer_inputs()
                self.timer_initial = self.timer_remaining
                self.timer_finished_for_run = False
            elif self.timer_status.cget("text") == "آماده‌ی شروع":
                self.timer_remaining = self._read_timer_inputs()
                self.timer_initial = self.timer_remaining
        except ValueError as exc:
            self.timer_status.configure(text=str(exc), text_color=RED)
            return
        self.timer_running = True
        self.timer_deadline = time.monotonic() + self.timer_remaining
        self.timer_status.configure(text="در حال شمارش معکوس…", text_color=CYAN)
        self._timer_tick()

    def _timer_tick(self):
        if not self.timer_running:
            return
        self.timer_remaining = max(0.0, self.timer_deadline - time.monotonic())
        color = self._timer_color()
        self.timer_big.configure(text=format_time(self.timer_remaining), text_color=color)
        self._draw_ring(self._timer_fraction(), color)
        if self.timer_remaining <= 0:
            self.timer_running = False
            self.timer_job = None
            self.timer_finished_for_run = True
            self.timer_big.configure(text="00:00:00", text_color=RED)
            self.timer_status.configure(text="زمان به پایان رسید!", text_color=RED)
            self._draw_ring(0, RED)
            self._add_history("Timer", self.timer_initial, "تایمر کامل شد")
            self._play_sound()
            return
        self.timer_job = self.after(50, self._timer_tick)

    def pause_timer(self):
        if self.timer_running:
            self.timer_remaining = max(0.0, self.timer_deadline - time.monotonic())
            self.timer_running = False
            if self.timer_job:
                self.after_cancel(self.timer_job)
                self.timer_job = None
            self.timer_status.configure(text="متوقف شده", text_color=MUTED)
            self.timer_big.configure(text=format_time(self.timer_remaining))
            self._draw_ring(self._timer_fraction(), self._timer_color())

    def toggle_timer(self):
        if self.timer_running:
            self.pause_timer()
        else:
            self.start_timer()

    def reset_timer(self):
        self.pause_timer()
        try:
            total = self._read_timer_inputs()
        except ValueError:
            total = 300
            self.hour_var.set("00")
            self.minute_var.set("05")
            self.second_var.set("00")
        self.timer_remaining = self.timer_initial = float(total)
        self.timer_finished_for_run = False
        self.timer_big.configure(text=format_time(total), text_color=CYAN)
        self.timer_status.configure(text="آماده‌ی شروع", text_color=MUTED)
        self._draw_ring(1, CYAN)

    # ---------- کورنومتر ----------
    def _elapsed(self):
        if self.sw_running:
            return self.sw_elapsed + (time.monotonic() - self.sw_started_at)
        return self.sw_elapsed

    def start_stopwatch(self):
        if self.sw_running:
            return
        self.sw_started_at = time.monotonic()
        self.sw_running = True
        self._stopwatch_tick()

    def pause_stopwatch(self):
        if not self.sw_running:
            return
        self.sw_elapsed = self._elapsed()
        self.sw_running = False
        if self.sw_job:
            self.after_cancel(self.sw_job)
            self.sw_job = None
        self.sw_big.configure(text=format_time(self.sw_elapsed, True))

    def reset_stopwatch(self):
        # زمان را قبل از خاموش کردن وضعیت running ثبت می‌کنیم.
        elapsed = self._elapsed()
        if self.sw_job:
            self.after_cancel(self.sw_job)
            self.sw_job = None
        self.sw_running = False
        if elapsed > 0:
            self._add_history("Stopwatch", elapsed, f"{len(self.laps)} دور ثبت شد")
        self.sw_elapsed = 0.0
        self.laps = []
        self.sw_big.configure(text="00:00:00.00")
        self._render_laps()

    def _stopwatch_tick(self):
        if not self.sw_running:
            return
        self.sw_big.configure(text=format_time(self._elapsed(), True))
        self.sw_job = self.after(30, self._stopwatch_tick)

    def add_lap(self):
        elapsed = self._elapsed()
        if elapsed <= 0:
            return
        self.laps.append(elapsed)
        self._render_laps()

    def _render_laps(self):
        if not hasattr(self, "lap_box"):
            return
        self.lap_box.configure(state="normal")
        self.lap_box.delete("1.0", "end")
        if not self.laps:
            self.lap_box.insert("1.0", "هنوز دوری ثبت نشده است.")
        else:
            lines = []
            previous = 0.0
            for i, elapsed in enumerate(self.laps, 1):
                split = elapsed - previous
                lines.append(f"دور {i:02d}    کل: {format_time(elapsed, True)}    این دور: {format_time(split, True)}")
                previous = elapsed
            self.lap_box.insert("1.0", "\n".join(reversed(lines)))
        self.lap_box.configure(state="disabled")

    # ---------- تاریخچه و صدا ----------
    def _render_history(self):
        if not hasattr(self, "history_box"):
            return
        self.history_box.configure(state="normal")
        self.history_box.delete("1.0", "end")
        if not self.history:
            self.history_box.insert("1.0", "هنوز فعالیتی ذخیره نشده است.\nبا پایان تایمر یا ریست کورنومتر، سابقه در این بخش ثبت می‌شود.")
        else:
            lines = []
            for item in self.history:
                label = "تایمر" if item.get("type") == "Timer" else "کورنومتر"
                lines.append(
                    f"{item.get('time', '')}   |   {label}   |   {item.get('formatted', '')}   |   {item.get('details', '')}"
                )
            self.history_box.insert("1.0", "\n".join(lines))
        self.history_box.configure(state="disabled")

    def clear_history(self):
        self.history = []
        self._save_json(HISTORY_FILE, self.history)
        self._render_history()

    def _play_sound(self):
        if not self.sound_var.get():
            return
        sound_type = self.sound_type_var.get()
        if winsound:
            try:
                if sound_type == "Alarm":
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                    self.after(180, lambda: winsound.MessageBeep(winsound.MB_ICONEXCLAMATION))
                    self.after(360, lambda: winsound.MessageBeep(winsound.MB_ICONEXCLAMATION))
                elif sound_type == "Chime":
                    winsound.MessageBeep(winsound.MB_ICONASTERISK)
                else:
                    winsound.Beep(880, 220)
            except RuntimeError:
                self.bell()
        else:
            self.bell()

    # ---------- میان‌برها ----------
    def _shortcut_space(self, _event=None):
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, tk.Text)):
            return
        selected = self.tabs.get()
        if "تایمر" in selected:
            self.toggle_timer()
        elif "کورنومتر" in selected:
            if self.sw_running:
                self.pause_stopwatch()
            else:
                self.start_stopwatch()

    def _shortcut_reset(self, _event=None):
        selected = self.tabs.get()
        if "تایمر" in selected:
            self.reset_timer()
        elif "کورنومتر" in selected:
            self.reset_stopwatch()

    def _shortcut_lap(self, _event=None):
        if "کورنومتر" in self.tabs.get():
            self.add_lap()

    def _refresh_clock(self):
        self.clock_label.configure(text=datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._refresh_clock)

    def _on_close(self):
        self._save_settings()
        for job in (self.timer_job, self.sw_job):
            if job:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        self.destroy()


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = ChronoStudioPro()
    app.mainloop()
