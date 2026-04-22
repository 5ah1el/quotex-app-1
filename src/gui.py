import asyncio
import logging
import os
import sys
import threading
import time
from datetime import datetime
from typing import Dict, List

import customtkinter as ctk
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "config", "api_keys.env"))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.automation.advanced_predictor import AdvancedOTCPredictor
from src.data_storage import DataStorage
from src.signal_engine import SignalEngine
from src.twelve_data_connector import TwelveDataConnector

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

PAIRS = {
    "Live Forex": [
        "EUR/USD",
        "GBP/USD",
        "USD/JPY",
        "AUD/USD",
        "USD/CAD",
        "NZD/USD",
        "USD/CHF",
        "EUR/GBP",
    ],
    "Live Metals": [
        "XAU/USD",
        "XAG/USD",
    ],
    "Major Currency OTC": [
        "EUR/USD-OTC",
        "GBP/USD-OTC",
        "USD/JPY-OTC",
        "AUD/USD-OTC",
        "USD/CAD-OTC",
        "NZD/USD-OTC",
        "USD/CHF-OTC",
        "EUR/GBP-OTC",
    ],
    "Other OTC Markets": [
        "AUD/JPY-OTC",
        "CAD/CHF-OTC",
        "GBP/CAD-OTC",
        "CHF/JPY-OTC",
        "EUR/CHF-OTC",
        "GBP/AUD-OTC",
        "GBP/CHF-OTC",
        "USD/INR-OTC",
        "XAU/USD-OTC",
        "XAG/USD-OTC",
    ],
}

TIMEFRAMES = ["5", "15", "30", "60", "120", "300"]


class QuotexOTCApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Quotex OTC Signal Bot")
        self.geometry("1400x900")

        self.connector = TwelveDataConnector()
        self.signal_engine = SignalEngine()
        self.storage = DataStorage()
        self.predictor = AdvancedOTCPredictor(
            config={
                "prediction.model_type": "advanced_otc",
                "prediction.confidence_threshold": 0.60,
                "prediction.lookback_period": 20,
                "prediction.min_data_points": 50,
            },
            logger=logging.getLogger(__name__),
        )

        self.active_pairs: List[str] = []
        self.running = False
        self.paused = False
        self.total_signals = 0
        self.win_count = 0
        self.loss_count = 0
        self.safety_margin_seconds = 3
        self.scan_in_progress = False
        self.last_scan_bucket = None

        self.status_var = ctk.StringVar(value="Status: Stopped")
        self.market_var = ctk.StringVar(value="Mode: Live Markets")
        self.timeframe_var = ctk.StringVar(value="60")
        self.source_var = ctk.StringVar(value="Twelve Data Polling")

        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0, fg_color="#212121")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        self.logo_label = ctk.CTkLabel(
            self.sidebar,
            text="Quotex OTC Bot",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        self.logo_label.pack(pady=(20, 10))

        self.status_label = ctk.CTkLabel(
            self.sidebar,
            textvariable=self.status_var,
            text_color="#6c757d",
            font=ctk.CTkFont(size=14),
        )
        self.status_label.pack(pady=0)

        self.market_label = ctk.CTkLabel(
            self.sidebar,
            textvariable=self.market_var,
            text_color="#28a745",
            font=ctk.CTkFont(size=12),
        )
        self.market_label.pack(pady=(0, 20))

        self.start_btn = ctk.CTkButton(
            self.sidebar,
            text="Start Live Scan",
            command=self.start_bot,
            fg_color="#28a745",
            hover_color="#218838",
            height=40,
            font=ctk.CTkFont(weight="bold"),
        )
        self.start_btn.pack(fill="x", padx=20, pady=5)

        self.pause_btn = ctk.CTkButton(
            self.sidebar,
            text="Pause",
            command=self.toggle_pause,
            fg_color="#ffc107",
            hover_color="#e0a800",
            text_color="black",
            height=40,
            font=ctk.CTkFont(weight="bold"),
            state="disabled",
        )
        self.pause_btn.pack(fill="x", padx=20, pady=5)

        self.stop_btn = ctk.CTkButton(
            self.sidebar,
            text="Stop Bot",
            command=self.stop_bot,
            fg_color="#dc3545",
            hover_color="#c82333",
            height=40,
            font=ctk.CTkFont(weight="bold"),
            state="disabled",
        )
        self.stop_btn.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(
            self.sidebar,
            text="Data Source:",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=(20, 5))
        self.source_display = ctk.CTkLabel(self.sidebar, textvariable=self.source_var, text_color="#17a2b8")
        self.source_display.pack(fill="x", padx=20)

        self.tf_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.tf_frame.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            self.tf_frame,
            text="Scan Interval (sec):",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=5)
        self.tf_menu = ctk.CTkOptionMenu(self.tf_frame, variable=self.timeframe_var, values=TIMEFRAMES, height=35)
        self.tf_menu.pack(fill="x")

        self.safety_label = ctk.CTkLabel(
            self.tf_frame,
            text=f"Signal trigger: {self.safety_margin_seconds}s before candle close",
            text_color="#ffc107",
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.safety_label.pack(pady=5)

        ctk.CTkLabel(
            self.sidebar,
            text="Select Markets:",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=(10, 5))

        self.market_tabs = ctk.CTkSegmentedButton(self.sidebar, values=list(PAIRS.keys()), command=self.update_market_list)
        self.market_tabs.pack(fill="x", padx=10, pady=5)
        self.market_tabs.set("Live Forex")

        self.pairs_scroll = ctk.CTkScrollableFrame(self.sidebar, height=180, fg_color="#1a1a1a")
        self.pairs_scroll.pack(fill="both", expand=True, padx=10, pady=5)

        self.pair_vars: Dict[str, ctk.BooleanVar] = {}
        self.update_market_list("Live Forex")

        self.sel_btn_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sel_btn_frame.pack(fill="x", padx=10, pady=(5, 10))

        ctk.CTkButton(self.sel_btn_frame, text="Select All", height=25, command=self.select_all).pack(
            side="left", fill="x", expand=True, padx=(0, 2)
        )
        ctk.CTkButton(self.sel_btn_frame, text="Deselect All", height=25, command=self.deselect_all).pack(
            side="right", fill="x", expand=True, padx=(2, 0)
        )

        self.clear_log_btn = ctk.CTkButton(
            self.sidebar,
            text="Clear Log",
            command=self.clear_logs,
            fg_color="#495057",
            hover_color="#343a40",
            height=35,
        )
        self.clear_log_btn.pack(fill="x", padx=20, pady=(0, 10))

        self.main_content = ctk.CTkFrame(self, fg_color="#121212", corner_radius=0)
        self.main_content.grid(row=0, column=1, sticky="nsew")
        self.main_content.grid_columnconfigure(0, weight=1)
        self.main_content.grid_rowconfigure(3, weight=1)
        self.main_content.grid_rowconfigure(4, weight=0)

        self.dash_title = ctk.CTkLabel(
            self.main_content,
            text="Institutional Trading Signals Dashboard",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.dash_title.grid(row=0, column=0, pady=(20, 10))

        self.stats_frame = ctk.CTkFrame(self.main_content, height=50, fg_color="#1e1e1e")
        self.stats_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)

        self.stat_labels = {}
        stats_info = [
            ("Total Signals", "white"),
            ("Buy", "#28a745"),
            ("Sell", "#dc3545"),
            ("Wins", "#20c997"),
            ("Losses", "#fd7e14"),
            ("Accuracy", "#ffc107"),
            ("Latency", "#17a2b8"),
            ("Recovery Mode", "#dc3545"),
            ("Regime", "#17a2b8"),
        ]

        for idx, (name, color) in enumerate(stats_info):
            self.stats_frame.grid_columnconfigure(idx, weight=1)
            label = ctk.CTkLabel(
                self.stats_frame,
                text=f"{name}: 0",
                text_color=color,
                font=ctk.CTkFont(size=14, weight="bold"),
            )
            label.grid(row=0, column=idx, padx=10, pady=10)
            self.stat_labels[name] = label

        self.table_header = ctk.CTkFrame(self.main_content, height=30, fg_color="#2d2d2d")
        self.table_header.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 0))

        cols = ["Time", "Market", "TF", "Signal", "Quality", "Confidence", "Regime", "Reasons", "Result"]
        for idx, col in enumerate(cols):
            self.table_header.grid_columnconfigure(idx, weight=1)
            ctk.CTkLabel(self.table_header, text=col, font=ctk.CTkFont(size=12, weight="bold")).grid(
                row=0, column=idx, pady=5
            )

        self.table_scroll = ctk.CTkScrollableFrame(self.main_content, fg_color="#1a1a1a")
        self.table_scroll.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 20))

        self.log_frame = ctk.CTkFrame(self.main_content, height=200, fg_color="#0a0a0a")
        self.log_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 20))
        self.log_frame.grid_propagate(False)

        ctk.CTkLabel(self.log_frame, text="Activity Log:", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=10, pady=5
        )
        self.log_text = ctk.CTkTextbox(self.log_frame, font=("Consolas", 11), fg_color="#0a0a0a", border_width=0)
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

    def update_market_list(self, category):
        self.update_market_mode(category)
        for widget in self.pairs_scroll.winfo_children():
            widget.destroy()

        for pair in PAIRS[category]:
            if pair not in self.pair_vars:
                self.pair_vars[pair] = ctk.BooleanVar(value=False)
            ctk.CTkCheckBox(
                self.pairs_scroll,
                text=pair,
                variable=self.pair_vars[pair],
                font=ctk.CTkFont(size=12),
            ).pack(anchor="w", padx=10, pady=2)

    def update_market_mode(self, category: str):
        is_otc = "OTC" in category
        self.market_var.set("Mode: OTC Markets" if is_otc else "Mode: Live Markets")
        if is_otc:
            self.source_var.set("Twelve Data Polling (Live Forex/Metals Proxy For OTC Labels)")
        else:
            self.source_var.set("Twelve Data Polling (Live Forex/Metals)")

    def select_all(self):
        for pair in PAIRS[self.market_tabs.get()]:
            self.pair_vars[pair].set(True)

    def deselect_all(self):
        for pair in PAIRS[self.market_tabs.get()]:
            self.pair_vars[pair].set(False)

    def log(self, message):
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        self.log_text.insert("end", f"{timestamp} {message}\n")
        self.log_text.see("end")

    def clear_logs(self):
        self.log_text.delete("1.0", "end")
        for widget in self.table_scroll.winfo_children():
            widget.destroy()
        self.storage.clear_cache()
        self.signal_engine.reset_history()
        self.total_signals = 0
        self.win_count = 0
        self.loss_count = 0
        self.stat_labels["Total Signals"].configure(text="Total Signals: 0")
        self.stat_labels["Buy"].configure(text="Buy: 0")
        self.stat_labels["Sell"].configure(text="Sell: 0")
        self.stat_labels["Wins"].configure(text="Wins: 0")
        self.stat_labels["Losses"].configure(text="Losses: 0")
        self.stat_labels["Accuracy"].configure(text="Confidence: 0%")
        self.stat_labels["Latency"].configure(text="Latency: 0ms")
        self.stat_labels["Recovery Mode"].configure(text="Recovery: OFF", text_color="#28a745")
        self.stat_labels["Regime"].configure(text="Regime: 0")
        self.log("Log and saved signals cleared")

    def start_bot(self):
        if self.running:
            self.log("Bot is already running")
            return

        self.active_pairs = [pair for pair, value in self.pair_vars.items() if value.get()]
        if not self.active_pairs:
            self.log("Error: Please select at least one market")
            return

        self.running = True
        self.paused = False
        self.status_var.set("Status: Running")
        self.status_label.configure(text_color="#28a745")
        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal", text="Pause")
        self.stop_btn.configure(state="normal")

        self.log(f"Starting bot with {len(self.active_pairs)} markets")
        self.log(f"Markets: {', '.join(self.active_pairs)}")
        self.log(f"Connecting to {self.source_var.get()}")
        if not getattr(self.connector, "api_key", ""):
            self.log("Missing TWELVE_DATA_API_KEY. Add it in config/api_keys.env")
            self.stop_bot()
            return
        self.log("=" * 50)

        self.connector.start_websocket(self.active_pairs)

        self.analysis_thread = threading.Thread(target=self.run_analysis_loop, daemon=True)
        self.analysis_thread.start()

    def toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.status_var.set("Status: Paused")
            self.status_label.configure(text_color="#ffc107")
            self.pause_btn.configure(text="Resume")
            self.log("Bot paused")
        else:
            self.status_var.set("Status: Running")
            self.status_label.configure(text_color="#28a745")
            self.pause_btn.configure(text="Pause")
            self.log("Bot resumed")

    def stop_bot(self):
        self.running = False
        self.status_var.set("Status: Stopped")
        self.status_label.configure(text_color="#6c757d")
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled", text="Pause")
        self.stop_btn.configure(state="disabled")
        self.connector.stop_websocket()
        self.log("Bot stopped")

    def run_analysis_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.continuous_analysis())

    def _build_candle_history(self, df, timeframe_seconds: int):
        now_ts = time.time()
        time_left = int(max(0, timeframe_seconds - (now_ts % timeframe_seconds)))
        candle_history = []

        for idx, row in df.iterrows():
            is_last = idx == len(df) - 1
            candle_history.append(
                {
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume", 1.0)),
                    "datetime": row["datetime"].isoformat() if hasattr(row["datetime"], "isoformat") else str(row["datetime"]),
                    "is_closed": not is_last,
                    "time_left": time_left if is_last else 0,
                }
            )
        return candle_history

    async def continuous_analysis(self):
        self.log("Live scan ready")
        while self.running:
            if self.paused:
                await asyncio.sleep(1)
                continue

            try:
                tf_val = int(self.timeframe_var.get())
                now_ts = time.time()
                seconds_until_boundary = tf_val - (now_ts % tf_val)
                trigger_wait = seconds_until_boundary - self.safety_margin_seconds
                if trigger_wait <= 0:
                    trigger_wait += tf_val

                next_trigger = datetime.fromtimestamp(now_ts + trigger_wait)
                self.log(
                    f"Next scan at {next_trigger.strftime('%H:%M:%S')} "
                    f"({self.safety_margin_seconds}s before candle close)"
                )
                await asyncio.sleep(trigger_wait)

                candle_bucket = int(time.time() // tf_val)
                if self.scan_in_progress or self.last_scan_bucket == candle_bucket:
                    await asyncio.sleep(1)
                    continue

                self.scan_in_progress = True
                self.last_scan_bucket = candle_bucket
                self.log(f"Scan trigger: {datetime.now().strftime('%H:%M:%S')}")
                signals = []

                for pair in self.active_pairs:
                    df = self.connector.get_time_series(pair, str(tf_val), 300)
                    if df is None or len(df) < 50:
                        continue

                    mtf_trend = self.connector.get_mtf_trend(pair)
                    indicators = self.connector.calculate_indicators(df)
                    if not indicators:
                        continue

                    candle_history = self._build_candle_history(df, tf_val)
                    prediction = await self.predictor.predict(pair, str(tf_val), candle_history)
                    signal = self.signal_engine.generate_signal_from_prediction(
                        pair,
                        prediction,
                        indicators,
                        str(tf_val),
                        df,
                        mtf_trend,
                    )
                    self.storage.save_price(pair, indicators["current_price"])
                    if signal["signal"] != "HOLD":
                        signals.append(signal)
                        self.storage.save_signal(signal)
                    elif prediction.get("direction") == "WAITING":
                        self.log(f"{pair}: {prediction.get('reason', 'Waiting for close')}")

                if signals:
                    self.update_dashboard(signals)
                else:
                    self.log("No market data available for this scan")

                await asyncio.sleep(1)
            except Exception as exc:
                self.log(f"Analysis error: {exc}")
                await asyncio.sleep(2)
            finally:
                self.scan_in_progress = False

    def update_dashboard(self, signals: List[Dict]):
        self.after(0, lambda: self._update_ui_safe(signals))

    def mark_signal_result(self, signal: Dict, result: str, status_label, w_button, l_button):
        previous = signal.get("manual_result")
        if previous == result:
            return

        if previous == "W":
            self.win_count = max(0, self.win_count - 1)
        elif previous == "L":
            self.loss_count = max(0, self.loss_count - 1)

        signal["manual_result"] = result
        self.storage.update_signal_result(signal["signal_id"], result)

        if result == "W":
            self.win_count += 1
            status_label.configure(text="W", text_color="#20c997")
        else:
            self.loss_count += 1
            status_label.configure(text="L", text_color="#fd7e14")

        w_button.configure(state="disabled" if result == "W" else "normal")
        l_button.configure(state="disabled" if result == "L" else "normal")
        self.refresh_result_stats()
        self.log(f"Marked {signal['symbol']} {signal['signal']} as {result}")

    def refresh_result_stats(self):
        self.stat_labels["Wins"].configure(text=f"Wins: {self.win_count}")
        self.stat_labels["Losses"].configure(text=f"Losses: {self.loss_count}")
        decided = self.win_count + self.loss_count
        win_rate = round((self.win_count / decided) * 100, 1) if decided else 0
        self.stat_labels["Accuracy"].configure(text=f"Win Rate: {win_rate}%")

    def _update_ui_safe(self, signals: List[Dict]):
        summary = self.signal_engine.get_signals_summary(signals)
        if all(signal["signal"] == "HOLD" for signal in signals):
            self.log(f"Scan complete: no setup found ({signals[0]['regime']})")

        self.total_signals = summary["total_signals"]
        self.stat_labels["Total Signals"].configure(text=f"Total Signals: {self.total_signals}")
        self.stat_labels["Buy"].configure(text=f"Buy: {summary['buy_count']}")
        self.stat_labels["Sell"].configure(text=f"Sell: {summary['sell_count']}")
        self.refresh_result_stats()
        self.stat_labels["Latency"].configure(text=f"Latency: {self.connector.get_latency()}ms")
        self.stat_labels["Recovery Mode"].configure(
            text=f"Recovery: {'ON' if summary['recovery_mode'] else 'OFF'}",
            text_color="#dc3545" if summary["recovery_mode"] else "#28a745",
        )
        self.stat_labels["Regime"].configure(text=f"Regime: {signals[0]['regime']}")

        if len(self.table_scroll.winfo_children()) > 50:
            for widget in self.table_scroll.winfo_children()[:10]:
                widget.destroy()

        for signal in signals:
            if signal["signal"] == "HOLD":
                continue

            row_frame = ctk.CTkFrame(self.table_scroll, fg_color="#242424", corner_radius=5)
            row_frame.pack(fill="x", pady=2, padx=5)
            for idx in range(9):
                row_frame.grid_columnconfigure(idx, weight=1)

            sig_color = "#28a745" if signal["signal"] == "BUY" else "#dc3545"
            ctk.CTkLabel(row_frame, text=datetime.now().strftime("%H:%M:%S"), font=ctk.CTkFont(size=11)).grid(row=0, column=0)
            ctk.CTkLabel(row_frame, text=signal["symbol"], font=ctk.CTkFont(size=11)).grid(row=0, column=1)
            ctk.CTkLabel(row_frame, text=f"{self.timeframe_var.get()}s", font=ctk.CTkFont(size=11)).grid(row=0, column=2)
            ctk.CTkLabel(
                row_frame,
                text=signal["signal"],
                text_color=sig_color,
                font=ctk.CTkFont(size=11, weight="bold"),
            ).grid(row=0, column=3)
            ctk.CTkLabel(
                row_frame,
                text="High" if signal["confidence"] >= 80 else "Standard",
                font=ctk.CTkFont(size=11),
            ).grid(row=0, column=4)
            ctk.CTkLabel(row_frame, text=f"{signal['confidence']}%", font=ctk.CTkFont(size=11)).grid(row=0, column=5)
            ctk.CTkLabel(row_frame, text=signal["regime"], font=ctk.CTkFont(size=11)).grid(row=0, column=6)
            ctk.CTkLabel(row_frame, text=signal["reasons"], font=ctk.CTkFont(size=10), text_color="gray").grid(
                row=0, column=7
            )
            result_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            result_frame.grid(row=0, column=8, padx=4)
            status_label = ctk.CTkLabel(result_frame, text=signal.get("manual_result", "-"), width=18)
            status_label.pack(side="left", padx=(0, 4))
            w_button = ctk.CTkButton(result_frame, text="W", width=28, height=24, fg_color="#20c997", hover_color="#198754")
            l_button = ctk.CTkButton(result_frame, text="L", width=28, height=24, fg_color="#fd7e14", hover_color="#e67700")
            w_button.configure(command=lambda s=signal, lbl=status_label, wb=w_button, lb=l_button: self.mark_signal_result(s, "W", lbl, wb, lb))
            l_button.configure(command=lambda s=signal, lbl=status_label, wb=w_button, lb=l_button: self.mark_signal_result(s, "L", lbl, wb, lb))
            w_button.pack(side="left", padx=1)
            l_button.pack(side="left", padx=1)

            if signal.get("manual_result") == "W":
                status_label.configure(text="W", text_color="#20c997")
                w_button.configure(state="disabled")
            elif signal.get("manual_result") == "L":
                status_label.configure(text="L", text_color="#fd7e14")
                l_button.configure(state="disabled")

            if signal["recovery_active"]:
                self.log(f"[RECOVERY] {signal['symbol']} -> {signal['signal']} ({signal['confidence']}%)")
            else:
                self.log(f"SIGNAL: {signal['symbol']} -> {signal['signal']} ({signal['confidence']}%)")


if __name__ == "__main__":
    app = QuotexOTCApp()
    app.mainloop()
