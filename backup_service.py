"""
Automatic database backup service.
- Backup on app startup
- Periodic backup every N hours
- Keep only the latest N backups
- Safe online backup using sqlite3.backup() API
"""

import os
import re
import glob
import sqlite3
from datetime import datetime
from database import DB_PATH

_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
BACKUP_DIR = os.path.join(_DATA_DIR, "backups")


def perform_backup():
    """Create a safe backup of the SQLite database.

    Uses sqlite3.backup() API which safely copies the database
    even while it is being written to (handles WAL mode correctly).
    Returns the backup filename on success.
    """
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    # Use sqlite3.backup() for safe online backup
    source = sqlite3.connect(DB_PATH)
    dest = sqlite3.connect(backup_path)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()

    # Clean up old backups
    cleanup_old_backups(keep=5)

    return backup_filename


def cleanup_old_backups(keep=5):
    """Keep only the latest N backup files, remove the rest."""
    pattern = os.path.join(BACKUP_DIR, "backup_*.db")
    backups = sorted(glob.glob(pattern))
    while len(backups) > keep:
        try:
            os.remove(backups.pop(0))
        except OSError:
            pass


def get_backup_list():
    """Return list of available backups with metadata."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    pattern = os.path.join(BACKUP_DIR, "backup_*.db")
    backups = sorted(glob.glob(pattern), reverse=True)
    result = []
    for path in backups:
        filename = os.path.basename(path)
        try:
            stat = os.stat(path)
            result.append({
                "filename": filename,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        except OSError:
            pass
    return result


def restore_from_backup(backup_path):
    """Restore the database from a backup file.

    Uses sqlite3.backup() to safely overwrite the current database.
    WARNING: This is a destructive operation — always create a
    pre-restore backup before calling this.
    """
    if not os.path.exists(backup_path):
        return False, "Backup file not found"

    try:
        source = sqlite3.connect(backup_path)
        dest = sqlite3.connect(DB_PATH)
        try:
            source.backup(dest)
        finally:
            dest.close()
            source.close()
        return True, "Restored successfully"
    except Exception as e:
        return False, f"Restore failed: {str(e)}"


def start_auto_backup(interval_hours=6):
    """Start periodic backup loop using eventlet green thread.

    This must be called AFTER eventlet monkey-patching is in effect.
    Uses eventlet.spawn + eventlet.sleep for non-blocking periodic execution.
    """
    try:
        import eventlet
    except ImportError:
        # Fallback for development without eventlet
        import threading

        def backup_loop():
            import time
            while True:
                time.sleep(interval_hours * 3600)
                try:
                    filename = perform_backup()
                    print(f"[Auto-Backup] Created: {filename}")
                except Exception as e:
                    print(f"[Auto-Backup] Error: {e}")

        t = threading.Thread(target=backup_loop, daemon=True)
        t.start()
        print(f"[Auto-Backup] Scheduled every {interval_hours}h (threading fallback)")
        return

    def backup_loop():
        while True:
            eventlet.sleep(interval_hours * 3600)
            try:
                filename = perform_backup()
                print(f"[Auto-Backup] Created: {filename}")
            except Exception as e:
                print(f"[Auto-Backup] Error: {e}")

    eventlet.spawn(backup_loop)
    print(f"[Auto-Backup] Scheduled every {interval_hours}h (eventlet)")


def is_valid_backup_filename(filename):
    """Validate backup filename format to prevent path traversal."""
    return bool(re.match(r'^backup_\d{8}_\d{6}\.db$', filename))
