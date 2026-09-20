"""Consistent SQLite snapshots and conservative, additive one-time imports."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=30)


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def snapshot(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination:
        raise ValueError('Snapshot must not replace the live database')
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=destination.parent, suffix='.db')
    os.close(fd)
    try:
        with closing(readonly(source)) as src, closing(sqlite3.connect(temporary)) as dst:
            src.backup(dst)
            dst.execute('PRAGMA journal_mode=DELETE')
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Snapshot failed integrity check')
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def merge(source, destination):
    """Insert missing PK records; differing duplicate IDs abort the entire import.

    No deletion propagation, last-writer-wins, automatic schema migration, or
    timestamp guesses. Take snapshots of both sides before invoking this function.
    """
    if Path(source).resolve() == Path(destination).resolve():
        raise ValueError('Source and destination must differ')
    if not Path(destination).is_file():
        raise ValueError('Destination database must already exist')
    report = {}
    with closing(readonly(source)) as src, closing(sqlite3.connect(destination, timeout=30)) as dst, dst:
        src.execute('BEGIN')
        dst.execute('BEGIN IMMEDIATE')
        for (table,) in src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            rows = src.execute(f'SELECT * FROM {quote(table)}').fetchall()
            if not rows:
                continue
            columns = src.execute(f'PRAGMA table_info({quote(table)})').fetchall()
            target = dst.execute(f'PRAGMA table_info({quote(table)})').fetchall()
            if columns != target:
                raise ValueError(f'Schema differs for {table}; manual migration required')
            pk = sorted((c[5], i) for i, c in enumerate(columns) if c[5])
            if not pk:
                raise ValueError(f'No stable primary key for {table}')
            indexes = [i for _, i in pk]
            condition = ' AND '.join(f'{quote(columns[i][1])} IS ?' for i in indexes)
            inserted = identical = 0
            for row in rows:
                key = tuple(row[i] for i in indexes)
                if any(v is None for v in key):
                    raise ValueError(f'Null primary key in {table}')
                old = dst.execute(f'SELECT * FROM {quote(table)} WHERE {condition}', key).fetchone()
                if old is not None:
                    if old != row:
                        raise ValueError(f'Conflicting record in {table}; import rolled back (no content logged)')
                    identical += 1
                else:
                    names = ','.join(quote(c[1]) for c in columns)
                    dst.execute(f'INSERT INTO {quote(table)} ({names}) VALUES ({",".join("?" for _ in row)})', row)
                    inserted += 1
            report[table] = {'inserted': inserted, 'identical': identical}
        if dst.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('Foreign key check failed; import rolled back')
        if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Integrity check failed; import rolled back')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['snapshot', 'merge'])
    parser.add_argument('source')
    parser.add_argument('destination')
    args = parser.parse_args()
    if args.operation == 'snapshot':
        snapshot(args.source, args.destination)
        print(json.dumps({'snapshot': args.destination}))
    else:
        print(json.dumps(merge(args.source, args.destination)))


if __name__ == '__main__':
    main()
