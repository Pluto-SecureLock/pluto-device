# backup_handler.py

from __future__ import annotations

class BackupCommandError(Exception):
    """Raised for user-facing backup command errors."""


def _parse_hex_key(hex_str: str) -> bytes:
    try:
        return bytes.fromhex(hex_str)
    except ValueError as e:
        raise BackupCommandError("Invalid HEX key. Expected: backup <HEXKEY>.") from e

def handle_backup_command(command: str, authenticator) -> str:
    """
    Supported commands:
      - backup --state                    (checks if backup key exists)
      - backup                            (creates backup using stored key)
      - backup <key>                      (stores new key; errors if key already stored)
      - backup --overwrite <key>          (stores/overwrites key)
      - backup --load <encrypted_blob>    (uses stored key; errors if missing)
      - backup --load <hex_key>:<blob>    (uses provided key; stores key; errors if key already stored)

    Returns a string response to be written back to the user.
    """
    tokens = command.strip().split()

    if not tokens or tokens[0] != "backup":
        raise BackupCommandError("Internal: not a backup command.")

    # backup --state
    if len(tokens) == 2 and tokens[1] == "--state":
        return "backup_key: True" if authenticator.has_backup_key() else "backup_key: False"

    # backup
    if len(tokens) == 1:
        vault = authenticator.get_vault()
        key_bytes = authenticator.get_backup_key()
        if not key_bytes:
            raise BackupCommandError("No stored backup key. Use: backup <HEXKEY> or backup --overwrite <HEXKEY>.")
        backup_data = vault.backup(key_bytes)
        return str(backup_data)

    # backup <key>
    if len(tokens) == 2 and not tokens[1].startswith("--"):
        vault = authenticator.get_vault()
        new_key = _parse_hex_key(tokens[1])

        if authenticator.has_backup_key():
            raise BackupCommandError("A backup key is already stored. Use: backup --overwrite <HEXKEY>.")

        authenticator.store_backup_key(new_key)
        backup_data = vault.backup(new_key)
        return str(backup_data)

    # backup --overwrite <key>
    if len(tokens) == 3 and tokens[1] == "--overwrite":
        vault = authenticator.get_vault()
        new_key = _parse_hex_key(tokens[2])

        authenticator.store_backup_key(new_key)  # overwrite semantics live in this method or storage layer
        backup_data = vault.backup(new_key)
        return str(backup_data)
    
    # backup --load <encrypted_blob>  OR  backup --load <hex_key>:<encrypted_blob>
    if len(tokens) == 3 and tokens[1] == "--load":
        payload = tokens[2]
        vault = authenticator.get_vault()

        if ":" in payload:
            # Form: <hex_key>:<blob>
            key_hex, blob = payload.split(":", 1)
            if not key_hex or not blob:
                raise BackupCommandError("Invalid load payload. Expected: backup --load <HEXKEY>:<ENCRYPTED_BLOB>")

            key_bytes = _parse_hex_key(key_hex)

            # store new key, but do NOT silently replace an existing one
            if authenticator.has_backup_key():
                raise BackupCommandError("A backup key is already stored. Use an overwrite flow before loading.")

            result = vault.restore(key_bytes, blob)
            authenticator.store_backup_key(key_bytes)
            return str(result)

        else:
            # Form: <blob> only -> use stored key
            blob = payload
            key_bytes = authenticator.get_backup_key()
            if not key_bytes:
                raise BackupCommandError("No stored backup key. Use: backup --load <HEXKEY>:<ENCRYPTED_BLOB>")

            result = vault.restore(key_bytes, blob)
            return str(result)

    # Anything else
    raise BackupCommandError(
        "Invalid backup command.\n"
        "Use:\n"
        "  backup --state\n"
        "  backup\n"
        "  backup <HEXKEY>\n"
        "  backup --overwrite <HEXKEY>"
        "  backup --load <HEXKEY>:<ENCRYPTED_BLOB>"
    )
