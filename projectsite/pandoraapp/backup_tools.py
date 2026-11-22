"""Database backups and live restore.

MySQL: Windows-user encrypted snapshots with isolated restore verification.
SQLite: copies made with SQLite's online backup, which is safe while the app is running.
"""
from contextlib import closing, contextmanager
import ctypes
from ctypes import wintypes
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import pickle
import re
import sqlite3
from uuid import uuid4

import MySQLdb
from django.db import connection

from .reports import MANILA


def extension():
    return 'sqlite3' if connection.vendor == 'sqlite' else 'dpapi'


def daily_pattern():
    return f'pandora-????-??-??.{extension()}'


def safety_pattern():
    return f'pre-restore-*.{extension()}'


class BackupBusy(Exception):
    """Another backup or restore holds the lock."""


class RestoreError(Exception):
    """A live restore failed; `entry` says whether the live database was changed."""

    def __init__(self, entry):
        super().__init__(entry.get('error_type', 'RestoreError'))
        self.entry = entry


class Blob(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]


def protect(data, *, decrypt=False):
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    function = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def quoted(name):
    return '`' + name.replace('`', '``') + '`'


def rows_digest(rows):
    return hashlib.sha256(pickle.dumps(tuple(sorted(rows, key=repr)), protocol=4)).hexdigest()


def snapshot():
    params = connection.get_connection_params()
    source = MySQLdb.connect(**params)
    try:
        with source.cursor() as cursor:
            cursor.execute('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            cursor.execute('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
            cursor.execute('SELECT TABLE_NAME, ENGINE, TABLE_TYPE FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME')
            tables = cursor.fetchall()
            if not tables or any(engine != 'InnoDB' or kind != 'BASE TABLE' for _, engine, kind in tables):
                raise ValueError('Backup requires InnoDB base tables.')
            result = {}
            for table, _, _ in tables:
                cursor.execute('SHOW CREATE TABLE ' + quoted(table))
                ddl = cursor.fetchone()[1]
                cursor.execute('SELECT * FROM ' + quoted(table))
                rows = cursor.fetchall()
                columns = [column[0] for column in cursor.description]
                result[table] = {'ddl': ddl, 'columns': columns, 'rows': rows,
                                 'digest': rows_digest(rows)}
            source.commit()
            return result
    finally:
        source.close()


def write_backup(path, data):
    Path(path).write_bytes(protect(pickle.dumps(data, protocol=4)))


def read_backup(path):
    # Only consume backups created by this application in the protected directory.
    # Pickle data is authenticated by the current-user DPAPI envelope before loading.
    return pickle.loads(protect(Path(path).read_bytes(), decrypt=True))


def load_tables(cursor, data):
    """Create every table in the cursor's current database and insert its rows."""
    cursor.execute('SET FOREIGN_KEY_CHECKS=0')
    for table in data.values():
        cursor.execute(table['ddl'])
    for name, table in data.items():
        if table['rows']:
            columns = ','.join(quoted(column) for column in table['columns'])
            placeholders = ','.join(['%s'] * len(table['columns']))
            cursor.executemany(f'INSERT INTO {quoted(name)} ({columns}) VALUES ({placeholders})', table['rows'])
    cursor.execute('SET FOREIGN_KEY_CHECKS=1')


def check_tables(cursor, data):
    """Compare every loaded table with the snapshot's row fingerprint."""
    results = {}
    for name, table in data.items():
        cursor.execute('SELECT * FROM ' + quoted(name))
        restored = cursor.fetchall()
        if rows_digest(restored) != table['digest']:
            raise ValueError('Restored table does not match snapshot.')
        results[name] = {'rows': len(restored), 'sha256': table['digest']}
    return results


def verify_data(data):
    params = connection.get_connection_params()
    params.pop('db', None)
    params.pop('database', None)
    target = 'pandora_recovery_' + uuid4().hex
    server = MySQLdb.connect(**params)
    created = False
    try:
        with server.cursor() as cursor:
            # CREATE without IF NOT EXISTS prevents any reuse of an existing database.
            cursor.execute('CREATE DATABASE ' + quoted(target) + ' CHARACTER SET utf8mb4')
            created = True
            cursor.execute('USE ' + quoted(target))
            load_tables(cursor, data)
            server.commit()
            results = check_tables(cursor, data)
            return {'target': target, 'all_tables_match': True, 'tables': results,
                    'target_removed_after_check': True}
    finally:
        if created:
            # Only the fresh UUID database created in this invocation can be removed.
            if not re.fullmatch(r'pandora_recovery_[a-f0-9]{32}', target):
                raise ValueError('Invalid recovery target.')
            with server.cursor() as cursor:
                cursor.execute('DROP DATABASE ' + quoted(target))
        server.close()


def restore_verify(path):
    return verify_data(read_backup(path))


def replace_live(data):
    """Drop every table in the configured database, then load and check `data`."""
    live = MySQLdb.connect(**connection.get_connection_params())
    try:
        with live.cursor() as cursor:
            cursor.execute('SET FOREIGN_KEY_CHECKS=0')
            cursor.execute("SELECT TABLE_NAME FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'")
            existing = [row[0] for row in cursor.fetchall()]
            if existing:
                cursor.execute('DROP TABLE ' + ','.join(quoted(name) for name in existing))
            load_tables(cursor, data)
            live.commit()
            return check_tables(cursor, data)
    finally:
        live.close()


def default_directory():
    if 'LOCALAPPDATA' in os.environ:
        return Path(os.environ['LOCALAPPDATA']) / 'Pandora' / 'Backups'
    return Path.home() / 'pandora-backups'  # Linux, e.g. PythonAnywhere: outside the web folders


def _sqlite_counts(conn):
    """(tables, rows) of a SQLite database after checking it is intact and is a Pandora database."""
    if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise ValueError('Backup file is damaged.')
    tables = [row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    if 'django_migrations' not in tables:
        raise ValueError('Not a Pandora database.')
    rows = sum(conn.execute('SELECT count(*) FROM "%s"' % name.replace('"', '""')).fetchone()[0]
               for name in tables)
    return len(tables), rows


def _sqlite_file(path):
    return closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True))


def save_current(path):
    """Write the live database to `path`; returns the number of tables."""
    if connection.vendor == 'sqlite':
        connection.ensure_connection()
        with closing(sqlite3.connect(path)) as target:
            connection.connection.backup(target)
        with _sqlite_file(path) as saved:
            return _sqlite_counts(saved)[0]
    data = snapshot()
    write_backup(path, data)
    return len(data)


def check_backup(path):
    """Raise unless the backup at `path` can be restored."""
    if connection.vendor == 'sqlite':
        with _sqlite_file(path) as backup:
            return _sqlite_counts(backup)
    return verify_data(read_backup(path))


def load_backup(path):
    """Replace the live database with the backup at `path`; returns (tables, rows)."""
    if connection.vendor == 'sqlite':
        connection.ensure_connection()
        with _sqlite_file(path) as source:
            source.backup(connection.connection)
        return _sqlite_counts(connection.connection)
    tables = replace_live(read_backup(path))
    return len(tables), sum(table['rows'] for table in tables.values())


def list_backups(directory):
    """Daily and pre-restore backups in `directory`, newest first."""
    directory = Path(directory)
    found = list(directory.glob(daily_pattern())) + list(directory.glob(safety_pattern()))
    return sorted(found, key=lambda path: path.stat().st_mtime, reverse=True)


def find_backup(directory, choice):
    """Resolve 'latest', a YYYY-MM-DD date, or a listed file name to a backup in `directory`."""
    if choice == 'latest':
        daily = sorted(Path(directory).glob(daily_pattern()), reverse=True)
        return daily[0] if daily else None
    wanted = {choice, f'pandora-{choice}.{extension()}'}
    # Matching listed names only means no path outside the backup directory is ever read.
    return next((path for path in list_backups(directory) if path.name in wanted), None)


def append_log(directory, entry):
    with (Path(directory) / 'backup-log.jsonl').open('a', encoding='utf-8') as output:
        output.write(json.dumps(entry) + '\n')


@contextmanager
def exclusive(directory):
    """Hold the backup lock; yields False if another backup or restore has it."""
    if os.name == 'nt':
        import msvcrt
        take = lambda lock: msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        release = lambda lock: msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        take = lambda lock: fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        release = lambda lock: fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    with (Path(directory) / 'backup.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        try:
            take(lock)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            lock.seek(0)
            release(lock)


def run_backup(directory, *, verify=False):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    now = datetime.now(MANILA)
    entry = {'time': now.isoformat(), 'status': 'failed'}
    with exclusive(directory) as acquired:
        if not acquired:
            entry['status'] = 'skipped_busy'
            append_log(directory, entry)
            return entry
        temporary = directory / 'backup.pending'
        try:
            tables = save_current(temporary)
            verification = check_backup(temporary) if verify else None
            path = directory / f'pandora-{now:%Y-%m-%d}.{extension()}'
            temporary.replace(path)
            entry.update(status='success', file=path.name, bytes=path.stat().st_size,
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest(), tables=tables)
            if verification:
                entry['verification'] = verification
            # Retain seven successful daily snapshots. Failed attempts never prune.
            backups = sorted(directory.glob(daily_pattern()), reverse=True)
            for old in backups[7:]:
                old.unlink()
            return entry
        except Exception as exc:
            # Record the error class without credentials or SQL data in logs.
            entry['error_type'] = type(exc).__name__
            raise
        finally:
            temporary.unlink(missing_ok=True)
            append_log(directory, entry)


def restore_live(path, directory):
    """Replace the live database with the backup at `path`.

    The backup is first proven in an isolated database, and the current data is saved
    as a pre-restore backup. If loading into the live database fails, the saved data
    is loaded back automatically.
    """
    directory = Path(directory)
    path = Path(path)
    now = datetime.now(MANILA)
    entry = {'time': now.isoformat(), 'action': 'restore', 'file': path.name, 'status': 'failed'}
    with exclusive(directory) as acquired:
        if not acquired:
            entry['status'] = 'skipped_busy'
            append_log(directory, entry)
            raise BackupBusy()
        try:
            check_backup(path)
            safety = directory / f'pre-restore-{now:%Y-%m-%d-%H%M%S}.{extension()}'
            save_current(safety)
            entry['safety_backup'] = safety.name
            try:
                tables, rows = load_backup(path)
            except Exception:
                entry['rolled_back'] = False
                load_backup(safety)
                entry['rolled_back'] = True
                raise
            entry.update(status='success', tables=tables, rows=rows)
            return entry
        except Exception as exc:
            # Record the error class without credentials or SQL data in logs.
            entry['error_type'] = type(exc).__name__
            raise RestoreError(entry) from exc
        finally:
            append_log(directory, entry)
