"""Test package.

Present so ``tests.conftest`` resolves to a single module name - the shared
message fixtures are imported by several test modules, and without this mypy
sees ``conftest`` and ``tests.conftest`` as two different files.
"""
