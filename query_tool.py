#!/usr/bin/env python
"""Script to push/pull copies of saved queries."""
import os
import pathlib
import random
import sys
from typing import List, Union

import axonius_api_client as axonapi
import click

NOW = axonapi.tools.dt_now()
NOW_STR = NOW.strftime("%Y-%m-%dT%H-%M-%S-%Z")
DEFAULT_PREFIX = f"ax_sq_export_{NOW_STR}"
LOG = axonapi.LOG
FIELDS_TO_STRIP = [
    "archived",
    "date_fetched",
    "last_updated",
    "updated_by",
    "user_id",
    "uuid",
]

"""Load variables"""
axonapi.constants.load_dotenv()


@click.command(context_settings={"auto_envvar_prefix": "AX"},)
@click.option(
    "--export/--import",
    "-e/-i",
    "export",
    is_flag=True,
    default=None,
    required=True,
    help="Exporting or importing queries",
)
@click.option(
    "--asset-type",
    "-a",
    "asset_type",
    required=True,
    show_default=True,
    type=click.Choice(["users", "devices"]),
    help="Type of assets to export saved queries for.",
)
@click.option(
    "--name-prefix",
    "-np",
    "name_prefix",
    default="",
    required=False,
    show_default=True,
    show_envvar=True,
    help="Pull queries that match a defined prefix.",
)
@click.option(
    "--tags",
    "-t",
    "tags",
    default="",
    metavar="CSV of tags",
    required=False,
    show_default=True,
    show_envvar=True,
    help="Define tags to pull queries by.",
)
@click.option(
    "--import-path",
    "-ip",
    "import_path",
    type=click.Path(exists=True, resolve_path=True),
    help="Define directory or single file to import from.",
    required=False,
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--export-path",
    "-xp",
    "export_path",
    default=os.getcwd(),
    type=click.Path(file_okay=False, dir_okay=True, resolve_path=True),
    help="Define directory path to export to.",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--export-prefix",
    "-xp",
    "export_prefix",
    default=DEFAULT_PREFIX,
    help="Prefix to use on exported files.",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--single-file/--no-single-file",
    "-sf/-nsf",
    "single_file",
    default=True,
    help="Export queries to a single file or a folder with a file for each query",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--url",
    "-u",
    "url",
    required=True,
    help="URL of an Axonius instance",
    metavar="URL",
    prompt="URL",
    show_envvar=True,
    show_default=True,
)
@click.option(
    "--key",
    "-k",
    "key",
    required=True,
    help="API Key of user in an Axonius instance",
    metavar="KEY",
    prompt="API Key of user",
    hide_input=True,
    show_envvar=True,
    show_default=True,
)
@click.option(
    "--secret",
    "-s",
    "secret",
    required=True,
    help="API Secret of user in an Axonius instance",
    metavar="SECRET",
    prompt="API Secret of user",
    hide_input=True,
    show_envvar=True,
    show_default=True,
)
def cli(
    url: str,
    key: str,
    secret: str,
    tags: str,
    asset_type: str,
    export: bool,
    name_prefix: bool,
    export_path: Union[str, pathlib.Path],
    export_prefix: str,
    import_path: Union[str, pathlib.Path],
    single_file: bool,
):
    """Start data gathering."""
    tags = tags or ""
    tags = [x.strip() for x in tags.strip().split(",") if x.strip()]

    ctx = axonapi.Connect(
        url=url,
        key=key,
        secret=secret,
        certwarn=False,
        log_console=True,
        log_level_console="error",
    )
    ctx.start()

    api_obj = getattr(ctx, asset_type)

    if export:
        do_export(
            api_obj=api_obj,
            tags=tags,
            name_prefix=name_prefix,
            path=export_path,
            single_file=single_file,
            export_prefix=export_prefix,
        )
    else:
        do_import(api_obj=api_obj, path=import_path)


def do_import(
    api_obj: axonapi.api.assets.asset_mixin.AssetMixin, path: Union[str, pathlib.Path],
):
    """Diaf."""
    if not path:
        click.secho(message="import path must be supplied!", err=True, fg="red")
        sys.exit(1)

    fq_path = pathlib.Path(path)

    sqs_to_add = []

    if fq_path.is_file():
        if not fq_path.suffix == ".json":
            click.secho(message="not a json file!", err=True, fg="red")
            sys.exit(1)

        resolved_path, content = axonapi.tools.path_read(obj=fq_path, is_json=True)
        sqs_to_add += content
    elif fq_path.is_dir():
        sq_files = [x for x in fq_path.iterdir() if x.suffix == ".json"]
        if not sq_files:
            click.secho(message="no json files found!", err=True, fg="red")
            sys.exit(1)

        for sq_file in sq_files:
            resolved_path, content = axonapi.tools.path_read(obj=sq_file, is_json=True)
            sqs_to_add.append(content)
    else:
        click.secho(message="Valid file or directory not specified", err=True, fg="red")
        sys.exit(1)

    existing_sqs = api_obj.saved_query.get()
    existing_names = [x["name"] for x in existing_sqs]

    for sq_to_add in sqs_to_add:
        name = sq_to_add["name"]

        if name in existing_names:
            # add option to delete and re-add, until update method comes out
            click.secho(
                message=f"Saved query {name} already exists! Skipping..",
                err=True,
                fg="yellow",
            )
            continue

        [sq_to_add.pop(x, None) for x in FIELDS_TO_STRIP]
        uuid = api_obj.saved_query._add(data=sq_to_add)
        click.secho(
            message=f"Created saved query {name} with uuid {uuid}", err=True, fg="green",
        )


def do_export(
    api_obj: axonapi.api.assets.asset_mixin.AssetMixin,
    tags: List[str],
    name_prefix: str,
    path: Union[str, pathlib.Path],
    export_prefix: str,
    single_file: bool,
):
    """Diaf."""
    sqs = api_obj.saved_query.get()

    if name_prefix:
        known = [x["name"] for x in sqs]
        known = "\n".join(known)
        sqs = [sq for sq in sqs if sq["name"].startswith(name_prefix)]

        if not sqs:
            click.secho(
                message=f"NO SQs beginning with {name_prefix}, known names:\n{known}",
                err=True,
                fg="red",
            )
            sys.exit(1)

    if tags:
        known = []
        for sq in sqs:
            known += sq.get("tags", [])
        known = "\n".join(list(set(known)))
        sqs = [sq for sq in sqs if any([tag in sq.get("tags", []) for tag in tags])]

        if not sqs:
            click.secho(
                message=f"NO SQs with tags {list(tags)}, known tags:\n{known}",
                err=True,
                fg="red",
            )
            sys.exit(1)

    dest_path = pathlib.Path(path)

    if single_file:
        dest_file = f"{export_prefix}.json"
        full_dest_path = dest_path / dest_file
        axonapi.tools.path_write(obj=full_dest_path, data=sqs, is_json=True)
        click.secho(
            message=f"Wrote {len(sqs)} SQs to {full_dest_path}", err=True, fg="green"
        )
    else:
        for sq in sqs:
            name = sq["name"]
            safe_name = "".join([x for x in name if x.isalnum() or x in [" ", "-"]])
            dest_file = f"{safe_name}.json"
            full_dest_path = dest_path / export_prefix / dest_file
            if full_dest_path.is_file():
                rand = random.randint(0, 999999)
                full_dest_path = dest_path / export_prefix / f"{safe_name}_{rand}.json"
            axonapi.tools.path_write(obj=full_dest_path, data=sq, is_json=True)
            click.secho(message=f"Wrote {full_dest_path}", err=True, fg="green")


if __name__ == "__main__":
    cli()
