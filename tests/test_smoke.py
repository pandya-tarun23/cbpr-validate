from typer.testing import CliRunner

import cbpr_validate
from cbpr_validate.cli import app

runner = CliRunner()


def test_version_is_set() -> None:
    assert cbpr_validate.__version__


def test_cli_version_command() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert cbpr_validate.__version__ in result.stdout
