import random

def csv_reader(text: str,
                      delimiter: str = ",",
                      quotechar: str = '"',
                      strip_fields: bool = True):
    """
    A lightweight replacement for csv.reader suited for CircuitPython.
    Yields each parsed row as a list of strings.

    RFC-4180 rules supported:
        • Fields separated by `delimiter`
        • Fields may be quoted with `quotechar`
        • Inside quoted fields, escape quotechar by doubling it ("")
        • Newlines inside quoted fields are preserved
    """
    field = []
    row = []
    in_quotes = False
    i = 0
    length = len(text)

    while i < length:
        ch = text[i]

        if ch == quotechar:
            # Peek at next char to see if this is an escaped quote ("")
            nxt = text[i + 1] if i + 1 < length else None
            if in_quotes and nxt == quotechar:
                field.append(quotechar)   # literal "
                i += 1                    # skip the escape char
            else:
                in_quotes = not in_quotes  # enter / leave quoted field

        elif ch == delimiter and not in_quotes:
            # Field separator
            cell = "".join(field)
            if strip_fields:
                cell = cell.strip()
            row.append(cell)
            field = []

        elif (ch == "\n" or ch == "\r") and not in_quotes:
            # End-of-line (handle \r, \n or \r\n)
            cell = "".join(field)
            if strip_fields:
                cell = cell.strip()
            row.append(cell)
            field = []

            if row:                       # skip completely blank lines
                yield row
            row = []

            # If it's a CRLF pair, skip the second char
            if ch == "\r" and i + 1 < length and text[i + 1] == "\n":
                i += 1

        else:
            field.append(ch)

        i += 1

    # Final field / row (no trailing newline)
    cell = "".join(field)
    if strip_fields:
        cell = cell.strip()
    row.append(cell)
    if row != [""] or len(row) > 1:       # ignore lone empty row at EOF
        yield row

def generate_password(length, level):
    letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    lowercase = "abcdefghijklmnopqrstuvwxyz"
    digits = "0123456789"
    punctuation = "!@#$%^&*()-_=+[]{}|;:,.<>?/"
    if level == 0:
        chars = letters + digits
    elif level == 1:
        chars = lowercase + digits + punctuation
    else:
        chars = letters + digits + punctuation
    return ''.join(random.choice(chars) for _ in range(length))
