"""How a schema identifier becomes a Python one.

The runtime emitter must produce the *same* identifiers as the statically
generated device packages, so code written against either lines up name for name:

* enum members   -> :func:`enum_member_name`  (``DIPort0`` -> ``DI_PORT0``)
* payload fields -> :func:`field_name`        (``DutyCycle`` -> ``duty_cycle``)

Type-level identifiers (register classes, enum classes, ``{Name}Payload``) are
*not* transformed — the generator keeps those verbatim from the yml too.

See the upstream generator's package for more information:
https://github.com/harp-tech/generators
"""

import re

_SEPARATOR = "_"

# The generator's regex: an uppercase letter, optionally preceded by a separator.
# The separator is part of the match, so a match starting on ``_``/``-`` has its
# index on the separator rather than on the letter (mirrored in ``_replace``).
_BOUNDARY = re.compile(r"(?P<sep>[_\-])?(?P<char>[A-Z])")


def _screaming_snake(value: str) -> str:
    """Convert a camel/Pascal-case yml identifier to ``SCREAMING_SNAKE_CASE``.

    A direct port of ``FirmwareNamingConvention.Apply``. Consecutive capitals are
    kept as one run (``TestDIPort1`` -> ``TEST_DI_PORT1``, ``DIO0`` -> ``DIO0``),
    which is why this can't be replaced with a naive boundary regex.
    """
    # Skip the leading run of capitals/non-letters, stopping one short of a
    # capital that begins a new lowercase word (the ``P`` of ``DIPort0``).
    start = 0
    length = len(value)
    while start < length and (value[start].isupper() or not value[start].isalpha()):
        if (
            start > 1
            and (start + 1) < length
            and value[start + 1].isalpha()
            and value[start + 1].islower()
        ):
            break
        start += 1
    value = value[:start].lower() + value[start:]

    previous_match = 0

    def _replace(match: "re.Match[str]") -> str:
        nonlocal previous_match
        index = match.start()
        run = index - previous_match
        previous_match = index
        char = match.group("char").lower()
        # Separate unless this capital continues a run of capitals — and a run's
        # final capital still separates when it starts a new lowercase word.
        follower = index + 1
        separate = run != 1 or (follower < len(value) and value[follower].islower())
        return _SEPARATOR + char if separate else char

    # ``value`` is read inside ``_replace``; the rebind happens only afterwards,
    # so the lookahead always sees the pre-substitution string (as in the C#).
    return _BOUNDARY.sub(_replace, value).upper()


def enum_member_name(value: str) -> str:
    """The Python enum member name for a yml bit-mask or group-mask key.

    ``DIPort0`` -> ``DI_PORT0``.
    """
    return _screaming_snake(value)


def field_name(value: str) -> str:
    """The Python payload field name for a yml ``payloadSpec`` key.

    ``DutyCycle`` -> ``duty_cycle``. Matches the generator's ``GetPythonFieldName``.
    """
    return _screaming_snake(value).lower()
