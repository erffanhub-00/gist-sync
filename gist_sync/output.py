"""Terminal output: colors only on a terminal, English only.

Persian does not render correctly in the terminal, so everything
the program prints is English. The menu and status lines use
colors when the output is a terminal; piped output stays plain.
"""

import sys


def paint(text, code, stream=None):
    """Color text with an ANSI code, only when the stream is a terminal."""
    if stream is None:
        stream = sys.stdout
    try:
        is_tty = stream.isatty()
    except Exception:
        is_tty = False
    if is_tty:
        return f"\033[{code}m{text}\033[0m"
    return text


def info(message):
    print(f"[{paint('INFO', '36')}] {message}")


def ok(message):
    print(f"[{paint('OK', '32')}] {message}")


def skip(message):
    print(f"[{paint('SKIP', '33')}] {message}")


def fail(message):
    print(f"[{paint('FAIL', '31')}] {message}")


def error(message):
    print(f"[{paint('ERROR', '31', sys.stderr)}] {message}", file=sys.stderr)
