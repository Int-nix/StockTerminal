#!/usr/bin/env python3
"""StockTerminal private-beta release server (Python standard library only).

Run from the StockTerminal project directory: python3 release_server.py
"""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import ipaddress
import sys
import tempfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
RELEASES = ROOT / 'releases'
MANIFEST = RELEASES / 'manifest.json'
HOST = os.environ.get('STOCKTERMINAL_RELEASE_HOST', '0.0.0.0')
PORT = int(os.environ.get('STOCKTERMINAL_RELEASE_PORT', '8765'))

EXCLUDED_DIRS = {
    '.git', '.venv', 'venv', '.stockterminal-venv',
    '__pycache__', '.pytest_cache', '.mypy_cache',
    '.idea', '.vscode', 'data', 'releases',
    'logs', 'build', 'dist', '.DS_Store'
}

EXCLUDED_FILES = {
    'release_server.py', '.env', '.env.local',
    '.env.production', 'desktop.ini', '.DS_Store'
}

EXCLUDED_SUFFIXES = {
    '.pyc', '.pyo', '.db', '.sqlite', '.sqlite3',
    '.log', '.pem', '.key', '.p12', '.pfx'
}

VERSION_PATTERN = re.compile(
    r'^[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.-]+)?$'
)


def should_include(path):
    rel = path.relative_to(ROOT)

    if any(
        part in EXCLUDED_DIRS or part.startswith('.')
        for part in rel.parts[:-1]
    ):
        return False

    if path.name in EXCLUDED_FILES or path.name.startswith('.'):
        return False

    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False

    if path.is_symlink():
        return False

    return True


def files_to_package():
    for directory, dirs, files in os.walk(
        ROOT,
        followlinks=False
    ):
        parent = Path(directory)

        dirs[:] = sorted(
            d for d in dirs
            if d not in EXCLUDED_DIRS
            and not d.startswith('.')
            and not (parent / d).is_symlink()
        )

        for name in sorted(files):
            file = parent / name

            if should_include(file):
                yield file


def read_manifest():
    if MANIFEST.exists():
        return json.loads(
            MANIFEST.read_text(encoding='utf-8')
        )

    return None


def atomic_write_json(destination, data):
    fd, tmp = tempfile.mkstemp(
        dir=RELEASES,
        prefix='.manifest-',
        suffix='.tmp'
    )

    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            f.write('\n')

        os.replace(tmp, destination)

    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def publish(version):
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(
            'Version must look like 0.5.1 or 0.5.1-beta.1'
        )

    RELEASES.mkdir(exist_ok=True)

    filename = f'stockterminal-{version}.zip'
    target = RELEASES / filename

    if target.exists():
        raise FileExistsError(
            f'{filename} already exists. Use a new version number.'
        )

    package_files = list(files_to_package())

    if not (ROOT / 'main.py').exists():
        raise FileNotFoundError(
            'main.py not found next to release_server.py'
        )

    if not (ROOT / 'requirements.txt').exists():
        raise FileNotFoundError(
            'requirements.txt not found next to release_server.py'
        )

    fd, tmp = tempfile.mkstemp(
        dir=RELEASES,
        prefix='.package-',
        suffix='.zip'
    )

    os.close(fd)

    try:
        with ZipFile(
            tmp,
            'w',
            compression=ZIP_DEFLATED,
            compresslevel=6
        ) as z:
            for file in package_files:
                z.write(
                    file,
                    file.relative_to(ROOT).as_posix()
                )

        digest = hashlib.sha256()

        with open(tmp, 'rb') as f:
            for block in iter(
                lambda: f.read(1024 * 1024),
                b''
            ):
                digest.update(block)

        os.replace(tmp, target)

    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

    manifest = {
        'application': 'StockTerminal',
        'latest_version': version,
        'filename': filename,
        'download_path': f'/releases/{filename}',
        'sha256': digest.hexdigest(),
        'size_bytes': target.stat().st_size,
        'published_at': datetime.now(
            timezone.utc
        ).isoformat(),
    }

    atomic_write_json(MANIFEST, manifest)

    return manifest, len(package_files)


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        path = urlsplit(self.path).path

        if path in ('/', '/manifest.json'):

            if not MANIFEST.is_file():
                self.send_error(
                    404,
                    'No release has been published yet'
                )
                return

            self.send_file(
                MANIFEST,
                'application/json'
            )

        elif path == '/versions.json':

            versions = []

            for target in RELEASES.glob(
                'stockterminal-*.zip'
            ):
                name = target.name

                match = re.fullmatch(
                    r'stockterminal-'
                    r'([0-9]+\.[0-9]+\.[0-9]+'
                    r'(?:-[a-zA-Z0-9.-]+)?)\.zip',
                    name
                )

                if not match:
                    continue

                digest = hashlib.sha256()

                with target.open('rb') as stream:
                    for block in iter(
                        lambda: stream.read(1024 * 1024),
                        b''
                    ):
                        digest.update(block)

                versions.append({
                    'version': match.group(1),
                    'download_path': f'/releases/{name}',
                    'sha256': digest.hexdigest(),
                    'size_bytes': target.stat().st_size
                })

            versions.sort(
                key=lambda r: tuple(
                    int(n)
                    for n in re.match(
                        r'^(\d+)\.(\d+)\.(\d+)',
                        r['version']
                    ).groups()
                ),
                reverse=True
            )

            payload = json.dumps({
                'application': 'StockTerminal',
                'versions': versions
            }).encode('utf-8')

            self.send_response(200)
            self.send_header(
                'Content-Type',
                'application/json'
            )
            self.send_header(
                'Content-Length',
                str(len(payload))
            )
            self.send_header(
                'Cache-Control',
                'no-store'
            )
            self.end_headers()
            self.wfile.write(payload)

        elif path.startswith('/releases/'):

            name = path.removeprefix('/releases/')

            if not re.fullmatch(
                r'stockterminal-'
                r'[0-9]+\.[0-9]+\.[0-9]+'
                r'(?:-[a-zA-Z0-9.-]+)?\.zip',
                name
            ):
                self.send_error(404)
                return

            target = RELEASES / name

            if not target.is_file():
                self.send_error(404)
                return

            self.send_file(
                target,
                'application/zip'
            )

        else:
            self.send_error(404)

    def send_file(self, path, content_type):
        self.send_response(200)

        self.send_header(
            'Content-Type',
            content_type
        )

        self.send_header(
            'Content-Length',
            str(path.stat().st_size)
        )

        self.send_header(
            'Cache-Control',
            'no-store'
            if path == MANIFEST
            else 'public, max-age=86400'
        )

        self.send_header(
            'X-Content-Type-Options',
            'nosniff'
        )

        self.end_headers()

        try:
            with path.open('rb') as f:
                for chunk in iter(
                    lambda: f.read(1024 * 1024),
                    b''
                ):
                    self.wfile.write(chunk)

        except (
            BrokenPipeError,
            ConnectionResetError
        ):
            pass



def local_network_addresses():
    """Find likely LAN IPv4 addresses without third-party dependencies."""
    candidates = set()

    # On Windows, include multiple connected Wi-Fi/Ethernet interfaces.
    if sys.platform == 'win32':
        command = [
            'powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
            "Get-NetIPAddress -AddressFamily IPv4 | "
            "Where-Object { $_.AddressState -eq 'Preferred' } | "
            "Select-Object -ExpandProperty IPAddress"
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=8,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            if result.returncode == 0:
                candidates.update(result.stdout.splitlines())
        except (OSError, subprocess.TimeoutExpired):
            pass

    # Portable fallback: address used for an outbound route (no packets sent).
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('192.0.2.1', 80))
            candidates.add(sock.getsockname()[0])
    except OSError:
        pass

    try:
        candidates.update(item[4][0] for item in socket.getaddrinfo(
            socket.gethostname(), None, socket.AF_INET
        ))
    except OSError:
        pass

    addresses = []
    for value in candidates:
        try:
            addr = ipaddress.ip_address(value.strip())
        except ValueError:
            continue
        if addr.version == 4 and addr.is_private and not addr.is_loopback and not addr.is_link_local:
            addresses.append(str(addr))

    # Prefer typical home LAN addresses to VPN and virtual adapters.
    def priority(value):
        return (0 if value.startswith('192.168.') else
                1 if value.startswith('172.') else 2, value)

    return sorted(set(addresses), key=priority)


def main():
    print('\n' + '=' * 45)
    print('        STOCKTERMINAL RELEASE SERVER')
    print('=' * 45)

    print('Project:', ROOT)

    current = read_manifest()

    print(
        'Current published version:',
        current['latest_version']
        if current
        else '(none)'
    )

    answer = input(
        '\nPublish current project? [y/N]: '
    ).strip().lower()

    if answer in ('y', 'yes'):

        version = input(
            'Enter version (e.g. 0.5.1): '
        ).strip()

        try:
            manifest, count = publish(version)

        except (OSError, ValueError) as exc:
            print('ERROR:', exc)
            return 1

        print(
            f'\nPublished {version}: '
            f'{count} files, '
            f'{manifest["size_bytes"]:,} bytes'
        )

        print(
            'SHA-256:',
            manifest['sha256']
        )

    elif not MANIFEST.exists():
        print(
            'No release published. '
            'Start again and choose y to publish one.'
        )
        return 1

    print(f'\nListening on: {HOST}:{PORT}')
    print(f'LOCAL ACCESS: http://127.0.0.1:{PORT}/versions.json')
    if HOST in ('0.0.0.0', ''):
        addresses = local_network_addresses()
        if addresses:
            print('\nPOSSIBLE NETWORK ADDRESSES (Mac / other PCs):')
            for addr in addresses:
                print(f'  http://{addr}:{PORT}/versions.json')
            print('Try the 192.168.x.x address on your Mac first.')
        else:
            print('\nCould not automatically detect a LAN address.')
        print('These addresses require the same reachable network and')
        print('a firewall/VPN configuration that permits TCP port', PORT)
    print('\nPress Ctrl+C to stop.\n')

    if HOST not in (
        '127.0.0.1',
        'localhost',
        '::1'
    ):
        print(
            'WARNING: Server exposed beyond localhost. '
            'Use HTTPS, access controls, and trusted '
            'release signatures before public deployment.\n'
        )

    try:
        with ThreadingHTTPServer(
            (HOST, PORT),
            Handler
        ) as server:
            server.serve_forever()

    except KeyboardInterrupt:
        print('\nServer stopped.')

    return 0


if __name__ == '__main__':
    sys.exit(main())
