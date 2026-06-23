import typer

app = typer.Typer(help="cbpr-validate: ISO 20022 CBPR+ usage-guideline validator")


@app.command()
def version() -> None:
    from cbpr_validate import __version__

    typer.echo(__version__)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
