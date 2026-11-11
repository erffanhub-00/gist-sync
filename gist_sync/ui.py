"""Asking the user things: menus, prompts, paged lists.

Everything here is English only: Persian does not render
correctly in the terminal.
"""

import os
import sys

from .output import error, paint

PAGE_SIZE = 10


def _flush_stdin():
    """Discard any unread input (stray Enter presses, half-read
    escape sequences). Unix only; silently does nothing when
    stdin is not a terminal.
    """
    try:
        import termios
        if sys.stdin.isatty():
            termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except Exception:
        pass


def ask_yes_no(question, default=True):
    """Ask a yes/no question. Enter accepts the default.

    Returns the default when there is no terminal to ask in,
    so the program never hangs waiting for input.
    """
    if not sys.stdin.isatty():
        return default
    hint = "[Y/n]" if default else "[y/N]"
    try:
        answer = input(f"{question} {hint} ").strip().lower()
    except EOFError:
        return default
    if not answer:
        return default
    if answer in ("y", "yes"):
        return True
    if answer in ("n", "no"):
        return False
    return default


def ask_public_or_secret():
    """Ask 1 for public, 2 for secret. Default is secret (safer)."""
    if not sys.stdin.isatty():
        return True
    try:
        answer = input("Public (1) or secret (2)? [2] ").strip()
    except EOFError:
        return True
    if answer == "1":
        return False
    return True


def ask_folder_name(suggestion, label="Folder name"):
    """Ask for a folder name, showing the suggestion as the default.

    Enter accepts the suggestion. The suggestion is what the
    program would have used by itself (the file's name, or the
    gist's files). When there is no terminal to ask in, the
    suggestion is used without asking.
    """
    if not sys.stdin.isatty():
        return suggestion
    while True:
        try:
            answer = input(f"{label} [{suggestion}]: ").strip()
        except EOFError:
            return suggestion
        if not answer:
            return suggestion
        if "/" in answer or "\\" in answer or answer in (".", ".."):
            error("A folder name cannot contain / or \\. Try again.")
            continue
        return answer


def ask_description():
    """Ask for a gist description. Enter means none.

    The description is typed in the terminal, so it must be
    English: Persian does not display correctly there. (The
    description itself is saved on GitHub as typed.)
    """
    if not sys.stdin.isatty():
        return ""
    try:
        return input("Description, in English (Enter for none): ").strip()
    except EOFError:
        return ""


def _read_key(fd):
    """Read one keypress from a terminal: 'up', 'down', 'enter',
    'esc', 'q', or the character itself.

    Unix only (termios). The terminal is put in raw mode for the
    one keypress and restored right away. Arrow keys come in two
    forms and both are handled: ESC [ A / ESC [ B (normal mode)
    and ESC O A / ESC O B (application cursor mode). Any input
    left unread afterwards (for example a trailing newline when
    Enter arrives as CR LF) is discarded, so it cannot leak into
    the next prompt.
    """
    import select
    import termios
    import tty

    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = os.read(fd, 1).decode("utf-8", "ignore")
        if ch == "\x1b":
            # An arrow key sends ESC plus two more bytes. Wait
            # briefly for the rest; a lone ESC means ESC was pressed.
            ready, _, _ = select.select([fd], [], [], 0.15)
            if not ready:
                return "esc"
            seq = os.read(fd, 2).decode("utf-8", "ignore")
            if seq in ("[A", "OA"):
                return "up"
            if seq in ("[B", "OB"):
                return "down"
            return "other"
        if ch in ("\r", "\n"):
            return "enter"
        if ch == "\x03":
            raise KeyboardInterrupt
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        try:
            termios.tcflush(fd, termios.TCIFLUSH)
        except Exception:
            pass


def choose_option(options, title):
    """Pick one option from a menu. Returns its key, or None.

    options is a list of (key, label). On a real terminal the
    user moves with the up/down arrow keys and confirms with
    Enter (q or ESC quits); the chosen line is highlighted.
    Typing the number works too. When arrow keys are not
    available (no terminal, or termios missing), it falls back
    to typing the number.
    """
    keys = [key for key, _label in options]
    try:
        fd = sys.stdin.fileno()
        if not sys.stdin.isatty():
            raise OSError("not a terminal")
        selected = 0
        while True:
            # Clear the screen and redraw the menu.
            print("\033[2J\033[H", end="")
            print(paint(f"  {title}", "1;36"))
            for index, (_key, label) in enumerate(options):
                if index == selected:
                    print(paint(f"  > {label} ", "1;7"))
                else:
                    print(f"    {label}")
            print(paint("  ↑ ↓ to move, Enter to choose, "
                        "or type the number, q to quit", "33"))
            key = _read_key(fd)
            if key == "up":
                selected = (selected - 1) % len(options)
            elif key == "down":
                selected = (selected + 1) % len(options)
            elif key == "enter":
                return keys[selected]
            elif key in ("q", "esc"):
                return None
            elif key in keys:
                # Typing the number works too, like before.
                return key
    except Exception:
        # No arrow keys here: type the number instead. A wrong
        # key asks again instead of leaving the menu.
        while True:
            print(f"  {title}")
            for key, label in options:
                print(f"  {key}. {label}")
            try:
                answer = input("Choose: ").strip()
            except EOFError:
                return None
            if answer in keys:
                return answer
            if not answer or answer == "q":
                return None
            error("Choose one of: " + ", ".join(keys) + ".")


def wait_for_enter():
    """Pause so the user can read the output, then go back to the menu.

    Any stray Enter presses left over from the menu are discarded
    first, so this really waits for a fresh Enter.
    """
    if not sys.stdin.isatty():
        return
    _flush_stdin()
    try:
        input("Press Enter to go back to the menu. ")
    except EOFError:
        return


def pick_from_list(items, format_item, title, allow_pick):
    """Show items 10 per page, let the user move between pages.

    Numbering runs across all pages (1..N). Keys: n = next page,
    p = previous page, 0 = back. When picking is allowed, typing
    a number chooses that item and its index (0-based) is
    returned; otherwise None is returned. When there is no
    terminal, all items are printed at once and None is returned.
    """
    if not items:
        return None
    if not sys.stdin.isatty():
        for index, item in enumerate(items, start=1):
            print(f"  {index}. {format_item(item)}")
        return None
    pages = (len(items) + PAGE_SIZE - 1) // PAGE_SIZE
    page = 0
    while True:
        print(title)
        start = page * PAGE_SIZE
        for index, item in enumerate(items[start:start + PAGE_SIZE],
                                     start=start + 1):
            print(f"  {index}. {format_item(item)}")
        keys = "[n] next, [p] previous" if pages > 1 else ""
        if allow_pick:
            keys += ", [number] choose" if keys else "[number] choose"
            keys += ", [0] back"
        else:
            keys += ", [q] quit" if keys else "[q] quit"
        print(f"Page {page + 1} of {pages} — {keys}")
        try:
            answer = input("> ").strip().lower()
        except EOFError:
            print()
            return None
        if answer in ("n", "next"):
            if page < pages - 1:
                page += 1
            else:
                error("Already on the last page.")
            continue
        if answer in ("p", "prev", "previous"):
            if page > 0:
                page -= 1
            else:
                error("Already on the first page.")
            continue
        if answer in ("q", "quit", "0"):
            return None
        if allow_pick and answer.isdigit():
            number = int(answer)
            if 1 <= number <= len(items):
                return number - 1
            error("That number is not on the list.")
            continue
        error("Type n for next, p for previous"
              + (", a number to choose" if allow_pick else "")
              + ", or 0 to go back.")
