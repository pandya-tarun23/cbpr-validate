from typer.testing import CliRunner

import cbpr_validate
from cbpr_validate.cli import app

runner = CliRunner()


def test_version_is_set() -> None:
    assert cbpr_validate.__version__


def test_cli_version_command() -> None:
    # The CLI grew subcommands in Phase 5, so the version now has to be asked
    # for by name; a bare invocation prints help.
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert cbpr_validate.__version__ in result.stdout
