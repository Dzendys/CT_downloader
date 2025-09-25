import typer
from typing_extensions import Annotated
from pathlib import Path
from prettytable import PrettyTable

from downloadCT import CT as ct, CT_Gold as ctg

app = typer.Typer(
    add_completion=False, context_settings={"help_option_names": ["-h", "--help"]}
)


@app.command()
def main(
    url: Annotated[
        str, typer.Option("-u", "--url", help="Url adresa na ČT", show_default=False)
    ],
    directory: Annotated[
        Path,
        typer.Option(
            "-d",
            "--directory",
            help="Umístění pro stažený soubor",
            show_default=True,
            exists=False,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = Path.cwd(),
    name: Annotated[
        str, typer.Option("-n", "--name", help="Jméno souboru", show_default=False)
    ] = None,
    subtitles: Annotated[
        bool,
        typer.Option("-s", "--subtitles", help="Stahovat titulky", show_default=True),
    ] = False,
    force_confirm: Annotated[
        bool,
        typer.Option(
            "-f",
            "--force-confirm",
            help="Přeskočit potvrzení pro stahování",
            show_default=True,
        ),
    ] = False,
):
    """Main CLI command for downloading videos from ČT"""
    if url.startswith(ctg.VALID_URLS[0]):
        c: ctg = ctg(url, directory, name)
    c: ct = ct(url, directory, name)

    if not force_confirm:
        c.displayInfo()
        print(
            "Přejete si stáhnout toto video podle těchno nastavení? \033[1mY/N\033[0m"
        )
        if input().upper() == "Y":
            c.download(subs=subtitles)
        return
    c.download(subs=subtitles)


if __name__ == "__main__":
    app()
