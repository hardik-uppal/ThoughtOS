"""Pull a consistent home-server snapshot; optionally deploy the Git package.

Not bidirectional SQLite replication. All live writes belong on the server.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import sys
import uuid
from .database_admin import readonly
from contextlib import closing


def run(command):
    subprocess.run(command, check=True)


def remote_main():
    """Run any ThoughtOS CLI command on the canonical host over SSH."""
    config = json.loads((Path.home() / '.config/thoughtos/sync.json').read_text())
    host, command = config['host'], config['remote_command']
    if host.startswith('-') or not command.startswith('/'):
        raise ValueError('Invalid remote configuration')
    os.execvp('ssh', ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', host,
                      shlex.join([command, *sys.argv[1:]])])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(Path.home() / '.config/thoughtos/sync.json'))
    parser.add_argument('--deploy', action='store_true', help='Also fast-forward server code and install its package')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    host = config['host']
    if host.startswith('-'):
        raise ValueError('Invalid SSH host')
    repo, python, database = (config[k] for k in ('remote_repo', 'remote_python', 'remote_db'))
    if not all(p.startswith('/') for p in (repo, python, database)):
        raise ValueError('Remote paths must be absolute')
    destination = Path(config['local_snapshot']).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    remote_copy = str(Path(database).parent / 'backups' / ('sync-' + uuid.uuid4().hex + '.db'))
    ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', host]
    def remote(argv):
        run(ssh + [shlex.join(argv)])
    fd, local_temp = tempfile.mkstemp(dir=destination.parent, suffix='.db')
    os.close(fd)
    try:
        remote([python, '-m', 'thoughtos_server.database_admin', 'snapshot', database, remote_copy])
        # Stream binary data over authenticated SSH; no shell/SCP path interpolation.
        with open(local_temp, 'wb') as output:
            subprocess.run(ssh + [shlex.join(['cat', remote_copy])], stdout=output, check=True)
        with closing(readonly(local_temp)) as conn:
            if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Downloaded snapshot failed integrity check')
        os.chmod(local_temp, 0o400)
        os.replace(local_temp, destination)
        print(f'Read-only snapshot updated: {destination}')
    finally:
        if os.path.exists(local_temp):
            os.unlink(local_temp)
        remote(['rm', '-f', '--', remote_copy])
    if args.deploy:
        branch = config['branch']
        if branch.startswith('-'):
            raise ValueError('Invalid Git branch')
        # Refuse local server edits and divergent history; never reset --hard.
        script = 'set -eu; cd ' + shlex.quote(repo) + '; '
        script += 'test -z "$(git status --porcelain --untracked-files=no)"; '
        script += shlex.join(['git', 'fetch', 'origin', branch]) + '; '
        script += 'git merge --ff-only FETCH_HEAD; '
        script += shlex.join([python, '-m', 'pip', 'install', '--no-deps', '--force-reinstall', '.'])
        remote(['sh', '-c', script])
        print('Server package deployed. Restart MCP sessions to load new code.')


if __name__ == '__main__':
    main()
