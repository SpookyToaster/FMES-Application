"""
Utility for locating the OneDrive root at runtime.

Reads the OneDriveCommercial environment variable that is set automatically
on machines with the OneDrive for Business client installed.  Use the
returned path as the base for constructing file paths to shared resources
instead of hard-coding a specific user's home directory.
"""

from pathlib import Path
import os

# OneDriveCommercial is set by the OneDrive for Business sync client
onedrive = os.environ.get("OneDriveCommercial")

print(onedrive)
