#!/usr/bin/env python3
"""仕入れ候補発掘ツール — GUIランチャー（実行ボタン）

コマンドを打たずに検索を実行するための簡易GUI。
「実行ツール.command」をダブルクリックしても起動できる。
内部では main.py search を呼び出しているだけなので、CLIと動作は同一。
"""
from __future__ import annotations

import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

import yaml

BASE_DIR = Path(__file__).resolve().parent
PYTHON = BASE_DIR / ".venv" / "bin" / "python"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)


def load_config() -> dict:
    path = BASE_DIR / "config.yaml"
    if path.exists():
        with path.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.config = load_config()
        self.process: subprocess.Popen | None = None
        self.log_queue: queue.Queue[str | None] = queue.Queue()

        root.title("仕入れ候補発掘ツール")
        root.geometry("720x560")
        root.minsize(600, 480)

        self._build_form()
        self._build_buttons()
        self._build_log()
        self._poll_log()

    # ------------------------------------------------------------------
    def _build_form(self) -> None:
        frame = ttk.LabelFrame(self.root, text=" 検索条件 ")
        frame.pack(fill="x", padx=12, pady=(12, 6))
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        ttk.Label(frame, text="キーワード:").grid(row=0, column=0, sticky="e", padx=(10, 4), pady=4)
        self.keyword_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.keyword_var).grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=(0, 10), pady=4)

        ttk.Label(frame, text="JANコード:").grid(row=1, column=0, sticky="e", padx=(10, 4), pady=4)
        self.jan_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.jan_var).grid(
            row=1, column=1, sticky="ew", pady=4)
        ttk.Label(frame, text="※JAN検索が最も相場推定の精度が高い").grid(
            row=1, column=2, columnspan=2, sticky="w", padx=6)

        ttk.Label(frame, text="状態:").grid(row=2, column=0, sticky="e", padx=(10, 4), pady=4)
        self.condition_var = tk.StringVar(value="any")
        cond = ttk.Frame(frame)
        cond.grid(row=2, column=1, sticky="w")
        for label, value in [("すべて", "any"), ("新品", "new"), ("中古", "used")]:
            ttk.Radiobutton(cond, text=label, value=value,
                            variable=self.condition_var).pack(side="left", padx=(0, 8))

        ttk.Label(frame, text="最大件数/サイト:").grid(row=2, column=2, sticky="e", padx=(10, 4))
        self.max_var = tk.IntVar(value=20)
        ttk.Spinbox(frame, from_=1, to=50, textvariable=self.max_var, width=6).grid(
            row=2, column=3, sticky="w", padx=(0, 10))

        ttk.Label(frame, text="対象サイト:").grid(row=3, column=0, sticky="e", padx=(10, 4), pady=4)
        self.sites_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.sites_var).grid(row=3, column=1, sticky="ew", pady=4)
        ttk.Label(frame, text="空欄=設定通り（例: rakuten,yahoo）").grid(
            row=3, column=2, columnspan=2, sticky="w", padx=6)

        ttk.Label(frame, text="出力先:").grid(row=4, column=0, sticky="e", padx=(10, 4), pady=(4, 8))
        self.output_var = tk.StringVar(
            value=self.config.get("output", {}).get("default", "excel"))
        out = ttk.Frame(frame)
        out.grid(row=4, column=1, columnspan=3, sticky="w", pady=(4, 8))
        for label, value in [("Excel", "excel"), ("Google Sheets", "gsheet"), ("CSV", "csv")]:
            ttk.Radiobutton(out, text=label, value=value,
                            variable=self.output_var).pack(side="left", padx=(0, 8))

    def _build_buttons(self) -> None:
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=12, pady=6)

        self.run_button = ttk.Button(bar, text="▶ 実行", command=self.on_run)
        self.run_button.pack(side="left")

        self.stop_button = ttk.Button(bar, text="■ 中断", command=self.on_stop,
                                      state="disabled")
        self.stop_button.pack(side="left", padx=(8, 0))

        ttk.Button(bar, text="📄 結果Excelを開く", command=self.on_open_excel).pack(
            side="left", padx=(8, 0))
        ttk.Button(bar, text="ログを消去", command=lambda: self.log_text.delete("1.0", "end")).pack(
            side="right")

        self.status_var = tk.StringVar(value="待機中")
        ttk.Label(bar, textvariable=self.status_var).pack(side="right", padx=(0, 12))

    def _build_log(self) -> None:
        self.log_text = scrolledtext.ScrolledText(self.root, wrap="word", height=18,
                                                  font=("Menlo", 11))
        self.log_text.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        self._log("検索条件を入力して「▶ 実行」を押してください。\n"
                  "APIキー未設定の場合は .env に RAKUTEN_APP_ID / YAHOO_APP_ID を記入してください。\n")

    # ------------------------------------------------------------------
    def on_run(self) -> None:
        keyword = self.keyword_var.get().strip()
        jan = self.jan_var.get().strip()
        if not keyword and not jan:
            messagebox.showwarning("入力エラー", "キーワードまたはJANコードを入力してください")
            return
        if jan and not jan.isdigit():
            messagebox.showwarning("入力エラー", "JANコードは数字で入力してください")
            return

        cmd = [str(PYTHON), str(BASE_DIR / "main.py"), "search",
               "--max", str(self.max_var.get()),
               "--condition", self.condition_var.get(),
               "--output", self.output_var.get()]
        if keyword:
            cmd += ["--keyword", keyword]
        if jan:
            cmd += ["--jan", jan]
        sites = self.sites_var.get().strip()
        if sites:
            cmd += ["--sites", sites]

        self.run_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_var.set("検索中…")
        self._log(f"\n$ {' '.join(cmd[2:])}\n")
        threading.Thread(target=self._run_process, args=(cmd,), daemon=True).start()

    def _run_process(self, cmd: list[str]) -> None:
        try:
            self.process = subprocess.Popen(
                cmd, cwd=BASE_DIR,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            assert self.process.stdout is not None
            for line in self.process.stdout:
                self.log_queue.put(line)
            code = self.process.wait()
            self.log_queue.put(f"\n--- 終了（exit {code}）---\n")
        except Exception as exc:  # noqa: BLE001
            self.log_queue.put(f"\n実行エラー: {exc}\n")
        finally:
            self.process = None
            self.log_queue.put(None)  # 完了マーカー

    def on_stop(self) -> None:
        if self.process:
            self.process.terminate()
            self._log("\n（中断しました）\n")

    def on_open_excel(self) -> None:
        path = BASE_DIR / self.config.get("output", {}).get("excel_path", "仕入れ候補.xlsx")
        if not path.exists():
            messagebox.showinfo("結果ファイル", f"まだ出力がありません: {path.name}")
            return
        subprocess.run(["open", str(path)], check=False)

    # ------------------------------------------------------------------
    def _log(self, text: str) -> None:
        self.log_text.insert("end", text)
        self.log_text.see("end")

    def _poll_log(self) -> None:
        try:
            while True:
                item = self.log_queue.get_nowait()
                if item is None:  # 実行完了
                    self.run_button.config(state="normal")
                    self.stop_button.config(state="disabled")
                    self.status_var.set("待機中")
                else:
                    self._log(item)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log)


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
