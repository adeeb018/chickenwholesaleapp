import os
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
from app.config.settings import get_audit_log_path
from app.database.base import Base

SENSITIVE_KEYS = {
    "password", "password_hash", "salt", "admin_password_hash", "admin_password_salt"
}

def _mask_value(key: str, val: Any) -> str:
    """Masks sensitive password or salt values."""
    if key in SENSITIVE_KEYS:
        return "***"
    return str(val) if val is not None else "None"

def _extract_column_dict(obj: Any) -> Dict[str, str]:
    """Extracts column name to value dictionary for an ORM model instance."""
    try:
        state = inspect(obj)
        data = {}
        is_app_setting = getattr(obj, "__tablename__", "") == "app_settings"
        setting_key = getattr(obj, "key", "") if is_app_setting else ""

        for col in state.mapper.column_attrs:
            val = getattr(obj, col.key, None)
            if col.key in SENSITIVE_KEYS or (is_app_setting and setting_key in SENSITIVE_KEYS and col.key == "value"):
                data[col.key] = "***"
            else:
                data[col.key] = str(val) if val is not None else "None"
        return data
    except Exception:
        return {}

class AuditLogger:
    """
    Central database operations audit logger.
    Automatically logs all INSERT, UPDATE, SOFT_DELETE, and DELETE operations
    performed via SQLAlchemy sessions to a persistent, user-accessible log file.
    """
    _lock = threading.Lock()
    _listeners_attached = False
    _enabled = True

    @classmethod
    def get_log_file_path(cls) -> Path:
        """Returns the absolute Path of the database operations log file."""
        return get_audit_log_path()

    @classmethod
    def get_log_size_bytes(cls) -> int:
        """Returns the size of the audit log file in bytes."""
        p = cls.get_log_file_path()
        return p.stat().st_size if p.exists() else 0

    @classmethod
    def log_system_event(cls, action: str, table: str, record_id: Any, details: str) -> None:
        """Manually records a high-level system or administrative event."""
        cls._write_log_line(action.upper(), table, record_id, details)

    @classmethod
    def _write_log_line(cls, action: str, table: str, record_id: Any, details: str) -> None:
        """Thread-safe append of a formatted audit log line to disk."""
        if not cls._enabled:
            return
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rec_id_str = str(record_id) if record_id is not None else "N/A"
            clean_details = str(details).replace("\r", " ").replace("\n", " ").strip()
            line = f"{ts} | {action} | {table} | {rec_id_str} | {clean_details}\n"

            log_path = cls.get_log_file_path()
            with cls._lock:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(line)
        except Exception:
            pass

    @classmethod
    def attach_listeners(cls, session_cls=Session) -> None:
        """Hooks SQLAlchemy event listeners into the Session lifecycle."""
        if cls._listeners_attached:
            return

        @event.listens_for(session_cls, "before_flush")
        def _on_before_flush(session, flush_context, instances):
            if not cls._enabled:
                return
            pending = session.info.setdefault("audit_pending", [])

            # 1. New objects (INSERT)
            for obj in session.new:
                if isinstance(obj, Base):
                    pending.append({
                        "action": "INSERT",
                        "obj": obj,
                        "table": getattr(obj, "__tablename__", type(obj).__name__)
                    })

            # 2. Dirty objects (UPDATE / SOFT_DELETE)
            for obj in session.dirty:
                if not isinstance(obj, Base) or obj in session.deleted:
                    continue
                try:
                    state = inspect(obj)
                    changes = {}
                    is_app_setting = getattr(obj, "__tablename__", "") == "app_settings"
                    setting_key = getattr(obj, "key", "") if is_app_setting else ""

                    for attr in state.attrs:
                        hist = attr.history
                        if hist.has_changes():
                            old_v = hist.deleted[0] if hist.deleted else None
                            new_v = hist.added[0] if hist.added else None
                            if attr.key in SENSITIVE_KEYS or (is_app_setting and setting_key in SENSITIVE_KEYS and attr.key == "value"):
                                changes[attr.key] = ("***", "***")
                            else:
                                changes[attr.key] = (
                                    str(old_v) if old_v is not None else "None",
                                    str(new_v) if new_v is not None else "None"
                                )
                    if changes:
                        pending.append({
                            "action": "UPDATE",
                            "obj": obj,
                            "table": getattr(obj, "__tablename__", type(obj).__name__),
                            "id": getattr(obj, "id", None),
                            "changes": changes
                        })
                except Exception:
                    pass

            # 3. Deleted objects (DELETE)
            for obj in session.deleted:
                if not isinstance(obj, Base):
                    continue
                try:
                    data = _extract_column_dict(obj)
                    pending.append({
                        "action": "DELETE",
                        "table": getattr(obj, "__tablename__", type(obj).__name__),
                        "id": getattr(obj, "id", None),
                        "data": data
                    })
                except Exception:
                    pass

        @event.listens_for(session_cls, "after_flush")
        def _on_after_flush(session, flush_context):
            if not cls._enabled:
                return
            pending = session.info.get("audit_pending", [])
            records = session.info.setdefault("audit_records", [])

            for p in pending:
                try:
                    obj = p.get("obj")
                    table = p.get("table", "unknown")
                    action = p.get("action", "UNKNOWN")
                    rec_id = p.get("id") or (getattr(obj, "id", None) if obj else None)

                    if action == "INSERT":
                        data = _extract_column_dict(obj) if obj else {}
                        # If id was not in p, take from obj now that flush generated it
                        if rec_id is None and "id" in data:
                            rec_id = data["id"]
                        details = ", ".join(f"{k}={v}" for k, v in data.items())
                    elif action == "UPDATE":
                        changes = p.get("changes", {})
                        # Detect soft delete
                        if "is_deleted" in changes:
                            old_del, new_del = changes["is_deleted"]
                            if old_del in ("False", "0", "None") and new_del in ("True", "1"):
                                action = "SOFT_DELETE"
                        details = ", ".join(f"{k}: {v[0]} -> {v[1]}" for k, v in changes.items())
                    elif action == "DELETE":
                        data = p.get("data", {})
                        details = ", ".join(f"{k}={v}" for k, v in data.items())
                    else:
                        details = ""

                    records.append({
                        "action": action,
                        "table": table,
                        "id": rec_id,
                        "details": details
                    })
                except Exception:
                    pass

            session.info["audit_pending"] = []

        @event.listens_for(session_cls, "after_commit")
        def _on_after_commit(session):
            records = session.info.pop("audit_records", [])
            for r in records:
                cls._write_log_line(
                    action=r["action"],
                    table=r["table"],
                    record_id=r["id"],
                    details=r["details"]
                )

        @event.listens_for(session_cls, "after_rollback")
        def _on_after_rollback(session):
            session.info.pop("audit_records", None)
            session.info.pop("audit_pending", None)

        cls._listeners_attached = True

    @classmethod
    def read_logs(
        cls,
        max_lines: int = 5000,
        search_text: Optional[str] = None,
        action_filter: Optional[str] = None,
        table_filter: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Parses and filters audit logs from the log file, returned in reverse
        chronological order (newest operations first).
        """
        log_path = cls.get_log_file_path()
        if not log_path.exists():
            return []

        results = []
        search_query = search_text.strip().lower() if search_text else None
        act_filter = action_filter.strip().upper() if action_filter and action_filter != "ALL" else None
        tbl_filter = table_filter.strip().lower() if table_filter and table_filter != "ALL" else None

        try:
            with cls._lock:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()

            # Iterate in reverse chronological order
            for line in reversed(lines):
                line_str = line.strip()
                if not line_str:
                    continue

                parts = [p.strip() for p in line_str.split("|", 4)]
                if len(parts) == 5:
                    ts, act, tbl, rid, det = parts
                elif len(parts) >= 2:
                    ts = parts[0]
                    act = parts[1]
                    tbl = parts[2] if len(parts) > 2 else "unknown"
                    rid = parts[3] if len(parts) > 3 else "N/A"
                    det = parts[4] if len(parts) > 4 else ""
                else:
                    continue

                if act_filter and act.upper() != act_filter:
                    continue

                if tbl_filter and tbl.lower() != tbl_filter:
                    continue

                if search_query:
                    searchable = f"{ts} {act} {tbl} {rid} {det}".lower()
                    if search_query not in searchable:
                        continue

                results.append({
                    "timestamp": ts,
                    "action": act,
                    "table": tbl,
                    "record_id": rid,
                    "details": det,
                    "raw": line_str
                })

                if len(results) >= max_lines:
                    break

        except Exception:
            pass

        return results

    @classmethod
    def get_distinct_tables(cls) -> List[str]:
        """Returns sorted list of distinct table names found in the audit log."""
        log_path = cls.get_log_file_path()
        if not log_path.exists():
            return []

        tables = set()
        try:
            with cls._lock:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        parts = line.split("|")
                        if len(parts) >= 3:
                            t = parts[2].strip()
                            if t and t != "unknown":
                                tables.add(t)
        except Exception:
            pass

        return sorted(list(tables))
