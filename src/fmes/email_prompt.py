"""Timed GUI for choosing report-email recipients before an interactive run."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .local_settings import load_email_recipients, save_email_recipients


def _valid_email_address(value: str) -> bool:
    """Check a basic email address form suitable for the prompt's recipient field."""
    address = value.strip()
    if address.count("@") != 1 or any(character.isspace() for character in address):
        return False
    local_part, domain = address.split("@")
    return bool(local_part and domain and "." in domain and not domain.startswith(".") and not domain.endswith("."))


def prompt_for_email_recipient() -> str | None:
    """Prompt for recipient-list changes or one-run recipient before continuing."""
    root = tk.Tk()
    root.title("FMES Scheduler Email Options")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    frame = ttk.Frame(root, padding=14)
    frame.pack(fill=tk.BOTH, expand=True)
    ttk.Label(
        frame,
        text="Choose report email recipients, then continue. Closing this window keeps the current list.",
        wraplength=460,
    ).pack(anchor=tk.W, pady=(0, 8))

    recipient_box = tk.Listbox(frame, height=5, width=62, selectmode=tk.EXTENDED)
    recipient_box.pack(fill=tk.X, pady=(0, 8))
    recipients = load_email_recipients()

    def refresh_recipient_box():
        recipient_box.delete(0, tk.END)
        for recipient in recipients:
            recipient_box.insert(tk.END, recipient)

    refresh_recipient_box()

    add_frame = ttk.Frame(frame)
    add_frame.pack(fill=tk.X, pady=(0, 6))
    new_recipient = tk.StringVar()
    ttk.Entry(add_frame, textvariable=new_recipient).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def add_recipient():
        address = new_recipient.get().strip()
        if not _valid_email_address(address):
            messagebox.showwarning("Invalid email", "Enter a valid email address.", parent=root)
            return
        if address.casefold() not in {item.casefold() for item in recipients}:
            recipients.append(address)
            refresh_recipient_box()
        new_recipient.set("")

    ttk.Button(add_frame, text="Add", command=add_recipient).pack(side=tk.LEFT, padx=(6, 0))

    def remove_selected():
        selected = list(recipient_box.curselection())
        if not selected:
            messagebox.showinfo("Remove recipients", "Select one or more addresses to remove.", parent=root)
            return
        for index in reversed(selected):
            del recipients[index]
        refresh_recipient_box()

    ttk.Button(frame, text="Remove selected", command=remove_selected).pack(anchor=tk.W, pady=(0, 8))

    single_frame = ttk.Frame(frame)
    single_frame.pack(fill=tk.X, pady=(0, 10))
    ttk.Label(single_frame, text="Send this run to one person:").pack(anchor=tk.W)
    single_recipient = tk.StringVar()
    ttk.Entry(single_frame, textvariable=single_recipient).pack(side=tk.LEFT, fill=tk.X, expand=True)
    selected_recipient: str | None = None
    finished = False

    def finish(recipient: str | None):
        nonlocal selected_recipient, finished
        if finished:
            return
        selected_recipient = recipient
        finished = True
        root.destroy()

    def use_single_recipient():
        address = single_recipient.get().strip()
        if not _valid_email_address(address):
            messagebox.showwarning("Invalid email", "Enter a valid email address.", parent=root)
            return
        finish(address)

    ttk.Button(single_frame, text="Use for this run", command=use_single_recipient).pack(
        side=tk.LEFT, padx=(6, 0)
    )

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    def save_and_continue():
        try:
            save_email_recipients(recipients)
        except (OSError, RuntimeError) as exc:
            messagebox.showerror("Could not save recipients", str(exc), parent=root)
            return
        finish(None)

    ttk.Button(button_frame, text="Save list and continue", command=save_and_continue).pack(
        side=tk.LEFT
    )
    ttk.Button(button_frame, text="Continue", command=lambda: finish(None)).pack(
        side=tk.RIGHT
    )

    root.protocol("WM_DELETE_WINDOW", lambda: finish(None))
    root.mainloop()
    return selected_recipient
