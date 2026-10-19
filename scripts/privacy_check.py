"""Scan publication candidates without printing matched private values.

This is a targeted safeguard, not a comprehensive security certification.
"""
from pathlib import Path
import argparse
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'private-key': rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'github-token': rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})',
    'aws-access-key': rb'AKIA[0-9A-Z]{16}',
    'openai-key': rb'sk-(?:proj-)?[A-Za-z0-9_-]{40,}',
    'personal-email': rb'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
    'windows-user-path': rb'[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s]+',
    'unix-home-path': rb'/(?:home|Users)/[a-zA-Z][a-zA-Z0-9_.-]*/',
}
FORBIDDEN = {'.env', 'secrets.toml', '.databrickscfg'}


def scan(paths):
    findings = []
    for relative in paths:
        path = ROOT/relative
        if path.name in FORBIDDEN or path.suffix.lower() in {'.pem','.key','.pfx','.p12'}:
            findings.append((relative, 'credential-file'))
        if path.is_file():
            raw = path.read_bytes()
            for label, expression in PATTERNS.items():
                if re.search(expression, raw):
                    findings.append((relative, label))
    return findings


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tracked', action='store_true')
    parser.add_argument('--staged', action='store_true')
    args = parser.parse_args()
    command = ['git', 'ls-files', '-z'] if args.tracked or args.staged else ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z']
    files = [p for p in subprocess.check_output(command, cwd=ROOT).decode('utf-8').split('\0') if p]
    findings = scan(files)
    for path, category in findings:
        print(f'{category}: {path}')
    print(f'Checked {len(files)} files; {len(findings)} targeted privacy findings. Matched values are never printed.')
    raise SystemExit(bool(findings))
