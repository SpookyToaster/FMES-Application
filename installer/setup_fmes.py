"""GUI helper for preparing a Windows PC to run FMES Scheduler."""

import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
import winreg


APP_TITLE = "FMES Scheduler Prerequisites"
ODBC_DRIVER_NAME = "ODBC Driver 17 for SQL Server"
ODBC_DRIVER_KEY = r"SOFTWARE\ODBC\ODBCINST.INI\ODBC Drivers"
WINGET_PACKAGE_ID = "Microsoft.msodbcsql.17"
SHARED_ROOT = Path("S:/FMES")


def local_config_path(local_app_data=None):
    """Return the per-user config path without depending on the repository."""
    app_data = local_app_data or os.getenv("LOCALAPPDATA")
    if not app_data:
        raise RuntimeError("LOCALAPPDATA is not set; cannot locate the local FMES config file.")
    return Path(app_data) / "FMES Scheduler" / ".env"


def template_path():
    """Return the bundled or source-tree environment template."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / ".env.example"
    return Path(__file__).resolve().parents[1] / ".env.example"


def ensure_local_config(config_file=None, source_template=None):
    """Create a local config from the template without overwriting an existing file."""
    destination = Path(config_file) if config_file else local_config_path()
    if destination.exists():
        return False

    source = Path(source_template) if source_template else template_path()
    if not source.is_file():
        raise FileNotFoundError(f"FMES config template was not found: {source}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return True


def odbc_driver_17_installed():
    """Check both Windows ODBC registry views for the required SQL driver."""
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ODBC_DRIVER_KEY, 0, winreg.KEY_READ | view) as key:
                value, _ = winreg.QueryValueEx(key, ODBC_DRIVER_NAME)
            if str(value).strip().lower() == "installed":
                return True
        except OSError:
            continue
    return False


def setup_status():
    """Return prerequisite status without exposing config contents."""
    config_file = local_config_path()
    return {
        "odbc": odbc_driver_17_installed(),
        "config": config_file.is_file(),
        "input_folder": (SHARED_ROOT / "Input_Files").is_dir(),
        "output_folder": (SHARED_ROOT / "Output_Files").is_dir(),
    }


class PrerequisiteSetupApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("650x470")
        self.root.minsize(580, 420)
        self.result_queue = queue.Queue()

        frame = ttk.Frame(root, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            frame,
            text="Prepare this computer to run FMES Scheduler",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            frame,
            text="Install the SQL driver, create your private local config, and verify shared-folder access.",
            wraplength=600,
        ).pack(anchor=tk.W, pady=(6, 12))

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=(0, 10))
        self.install_button = ttk.Button(buttons, text="Install ODBC Driver 17", command=self.install_odbc)
        self.install_button.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text="Create / Open Local Config", command=self.open_local_config).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(buttons, text="Check Setup", command=self.check_setup).pack(side=tk.LEFT)

        self.output = scrolledtext.ScrolledText(frame, height=16, state=tk.DISABLED, wrap=tk.WORD)
        self.output.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            frame,
            text="Config is stored under %LOCALAPPDATA% and is never copied to the shared folder.",
            wraplength=600,
        ).pack(anchor=tk.W, pady=(10, 0))

        self.write("Use Check Setup to see which prerequisites still need attention.")
        self.check_setup()

    def write(self, text):
        self.output.configure(state=tk.NORMAL)
        self.output.insert(tk.END, text.rstrip() + "\n")
        self.output.see(tk.END)
        self.output.configure(state=tk.DISABLED)

    def check_setup(self):
        status = setup_status()
        config_file = local_config_path()
        lines = [
            f"{'Ready' if status['odbc'] else 'Missing'}: {ODBC_DRIVER_NAME}",
            f"{'Ready' if status['config'] else 'Needs setup'}: {config_file}",
            f"{'Ready' if status['input_folder'] else 'Unavailable'}: {SHARED_ROOT / 'Input_Files'}",
            f"{'Ready' if status['output_folder'] else 'Unavailable'}: {SHARED_ROOT / 'Output_Files'}",
        ]
        self.write("\n".join(lines))

    def open_local_config(self):
        try:
            config_file = local_config_path()
            created = ensure_local_config(config_file=config_file)
            subprocess.Popen(["notepad.exe", str(config_file)])
        except (OSError, RuntimeError) as exc:
            messagebox.showerror(APP_TITLE, f"Could not create or open the local config:\n{exc}")
            return

        if created:
            self.write(f"Created config template at {config_file}. Fill in the database and email settings.")
        else:
            self.write(f"Opened existing local config at {config_file}; it was not overwritten.")

    def install_odbc(self):
        if odbc_driver_17_installed():
            self.write(f"{ODBC_DRIVER_NAME} is already installed.")
            return

        winget = shutil.which("winget")
        if not winget:
            messagebox.showerror(
                APP_TITLE,
                "WinGet was not found. Install Microsoft App Installer, then reopen this setup app.",
            )
            return

        self.install_button.configure(state=tk.DISABLED)
        self.write(f"Installing {ODBC_DRIVER_NAME} from the Microsoft WinGet source. Approve any Windows prompt.")
        worker = threading.Thread(target=self._run_winget, args=(winget,), daemon=True)
        worker.start()
        self.root.after(150, self._poll_install)

    def _run_winget(self, winget):
        command = [
            winget,
            "install",
            "--id",
            WINGET_PACKAGE_ID,
            "--exact",
            "--source",
            "winget",
            "--accept-package-agreements",
            "--accept-source-agreements",
            "--silent",
        ]
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            self.result_queue.put((completed.returncode, completed.stdout))
        except OSError as exc:
            self.result_queue.put((-1, str(exc)))

    def _poll_install(self):
        try:
            return_code, output = self.result_queue.get_nowait()
        except queue.Empty:
            self.root.after(150, self._poll_install)
            return

        if output.strip():
            self.write(output.strip())
        self.install_button.configure(state=tk.NORMAL)
        if return_code == 0 and odbc_driver_17_installed():
            self.write(f"Verified: {ODBC_DRIVER_NAME} is installed.")
        else:
            self.write(f"ODBC installation did not complete successfully (exit code {return_code}).")
            messagebox.showerror(
                APP_TITLE,
                "ODBC Driver 17 installation did not complete. Check the status output and retry.",
            )


def main():
    root = tk.Tk()
    PrerequisiteSetupApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
