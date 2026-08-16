"""Self-check for secret valve encryption.

Covers the three ways this can go wrong in a live install:
- re-saving the valve page nesting the ciphertext (OpenWebUI re-validates the
  whole Valves model on every save),
- an existing plaintext API key breaking after an update,
- a missing or changed WEBUI_SECRET_KEY silently producing a garbage key
  instead of a readable error.

Extracts the encryption block from the built artifact so it tests what actually
ships, without importing OpenWebUI.

Usage:
    python helpers/test_valve_encryption.py
"""
from __future__ import annotations

import base64
import hashlib
import os
import sys
import types
from pathlib import Path

ARTIFACT = Path(__file__).resolve().parents[1] / "anthropic_pipe.py"

START = "# SECRET VALVE ENCRYPTION"
END = "# Import OpenWebUI builtin tools helper"


def load_encryption_module():
    """Execute just the encryption block from the compiled artifact."""
    source = ARTIFACT.read_text(encoding="utf-8")
    start = source.index(START)
    end = source.index(END, start)
    block = source[start:end]

    module = types.ModuleType("_valve_encryption")
    module.__dict__.update(
        {
            "os": os,
            "base64": base64,
            "hashlib": hashlib,
            "logging": __import__("logging"),
            "logger": __import__("logging").getLogger("test"),
            "Optional": __import__("typing").Optional,
            "Any": __import__("typing").Any,
        }
    )
    exec(compile(block, "artifact_encryption_block", "exec"), module.__dict__)
    sys.modules["_valve_encryption"] = module
    return module


SECRET_A = "test-secret-key-aaaa"
SECRET_B = "test-secret-key-bbbb"
PLAINTEXT = "sk-ant-api03-EXAMPLE-NOT-A-REAL-KEY"


def test_roundtrip(m):
    os.environ["WEBUI_SECRET_KEY"] = SECRET_A
    encrypted = m.encrypt_valve_secret(PLAINTEXT)
    assert encrypted.startswith("encrypted:"), encrypted
    assert PLAINTEXT not in encrypted, "plaintext must not survive in the stored value"
    assert m.decrypt_valve_secret(encrypted) == PLAINTEXT


def test_encryption_is_idempotent(m):
    """OpenWebUI re-validates Valves on every save; nesting would break the key."""
    os.environ["WEBUI_SECRET_KEY"] = SECRET_A
    once = m.encrypt_valve_secret(PLAINTEXT)
    twice = m.encrypt_valve_secret(once)
    thrice = m.encrypt_valve_secret(twice)
    assert once == twice == thrice, "re-encrypting an encrypted value must be a no-op"
    assert m.decrypt_valve_secret(thrice) == PLAINTEXT


def test_plaintext_passes_through(m):
    """Installs that predate this keep working without a migration."""
    os.environ["WEBUI_SECRET_KEY"] = SECRET_A
    assert m.decrypt_valve_secret(PLAINTEXT) == PLAINTEXT
    assert m.decrypt_valve_secret("Your API Key Here") == "Your API Key Here"


def test_empty_stays_empty(m):
    """An empty per-user override must not become a non-empty ciphertext.

    The request path treats a non-empty UserValves key as "user set their own",
    so encrypting "" would hijack every request with an empty key.
    """
    os.environ["WEBUI_SECRET_KEY"] = SECRET_A
    assert m.encrypt_valve_secret("") == ""
    assert m.decrypt_valve_secret("") == ""


def test_no_secret_key_is_plaintext_passthrough(m):
    os.environ.pop("WEBUI_SECRET_KEY", None)
    value = m.encrypt_valve_secret(PLAINTEXT)
    assert value == PLAINTEXT, "without WEBUI_SECRET_KEY the value must pass through"
    assert m.decrypt_valve_secret(value) == PLAINTEXT


def test_changed_secret_key_raises_readable_error(m):
    os.environ["WEBUI_SECRET_KEY"] = SECRET_A
    encrypted = m.encrypt_valve_secret(PLAINTEXT)
    os.environ["WEBUI_SECRET_KEY"] = SECRET_B
    try:
        m.decrypt_valve_secret(encrypted)
    except ValueError as e:
        assert "WEBUI_SECRET_KEY" in str(e), f"unhelpful error: {e}"
    else:
        raise AssertionError("a changed secret key must raise, not return garbage")


def test_missing_secret_key_on_encrypted_value_raises(m):
    os.environ["WEBUI_SECRET_KEY"] = SECRET_A
    encrypted = m.encrypt_valve_secret(PLAINTEXT)
    os.environ.pop("WEBUI_SECRET_KEY", None)
    try:
        m.decrypt_valve_secret(encrypted)
    except ValueError as e:
        assert "WEBUI_SECRET_KEY" in str(e)
    else:
        raise AssertionError("an encrypted value without a key must raise")


def test_fernet_key_secret_is_accepted(m):
    """A WEBUI_SECRET_KEY that already is a 44-char Fernet key must work."""
    from cryptography.fernet import Fernet

    os.environ["WEBUI_SECRET_KEY"] = Fernet.generate_key().decode()
    encrypted = m.encrypt_valve_secret(PLAINTEXT)
    assert m.decrypt_valve_secret(encrypted) == PLAINTEXT


def test_pydantic_valve_field(m):
    """The valve type must encrypt on validation and survive a model_dump round trip."""
    from pydantic import BaseModel, Field

    os.environ["WEBUI_SECRET_KEY"] = SECRET_A

    class Valves(BaseModel):
        ANTHROPIC_API_KEY: m.EncryptedStr = Field(default="")

    valves = Valves(ANTHROPIC_API_KEY=PLAINTEXT)
    stored = valves.model_dump()["ANTHROPIC_API_KEY"]
    assert stored.startswith("encrypted:"), "model_dump must hand OpenWebUI the ciphertext"
    assert m.decrypt_valve_secret(stored) == PLAINTEXT

    # Reload, the way OpenWebUI does with Valves(**stored_values).
    reloaded = Valves(**valves.model_dump())
    assert reloaded.model_dump()["ANTHROPIC_API_KEY"] == stored, "reload must not re-encrypt"
    assert reloaded.ANTHROPIC_API_KEY.get_secret() == PLAINTEXT

    assert Valves().model_dump()["ANTHROPIC_API_KEY"] == "", "default must stay empty"


def test_skipped_when_openwebui_encrypts(m):
    """No double encryption when ENABLE_VALVE_ENCRYPTION is on."""
    os.environ["WEBUI_SECRET_KEY"] = SECRET_A
    m.OPENWEBUI_ENCRYPTS_VALVES = True
    try:
        assert m.encrypt_valve_secret(PLAINTEXT) == PLAINTEXT
    finally:
        m.OPENWEBUI_ENCRYPTS_VALVES = False


def test_existing_ciphertext_survives_flag_flip(m):
    """A key encrypted while the flag was off must stay readable once it is on.

    Admins do turn ENABLE_VALVE_ENCRYPTION on later; decryption must therefore
    stay driven by the value's prefix, not by the current flag.
    """
    os.environ["WEBUI_SECRET_KEY"] = SECRET_A
    encrypted = m.encrypt_valve_secret(PLAINTEXT)
    assert encrypted.startswith("encrypted:")

    m.OPENWEBUI_ENCRYPTS_VALVES = True
    try:
        assert m.decrypt_valve_secret(encrypted) == PLAINTEXT
        # And it is not re-encrypted on the next valve save either.
        assert m.encrypt_valve_secret(encrypted) == encrypted
    finally:
        m.OPENWEBUI_ENCRYPTS_VALVES = False


def main():
    module = load_encryption_module()
    original_secret = os.environ.get("WEBUI_SECRET_KEY")
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    try:
        for test in tests:
            test(module)
            print(f"  ok  {test.__name__}")
    finally:
        if original_secret is None:
            os.environ.pop("WEBUI_SECRET_KEY", None)
        else:
            os.environ["WEBUI_SECRET_KEY"] = original_secret
    print(f"\n{len(tests)} checks passed")


if __name__ == "__main__":
    main()
