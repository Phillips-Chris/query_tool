#!/usr/bin/env python
"""Script to pull down copies of saved queries."""

import os
import sys
import click
import json
import axonius_api_client as axonapi
import logging

"""Setup Logging"""
LOG_FMT = "%(asctime)s %(levelname)-8s [%(name)s:%(funcName)s()] %(message)s"
logging.basicConfig(level=logging.ERROR, format=LOG_FMT)
LOG = logging.getLogger("query_tool")


"""Load variables"""
axonapi.constants.load_dotenv()

AX_URL = os.environ["AX_URL"]
AX_KEY = os.environ["AX_KEY"]
AX_SECRET = os.environ["AX_SECRET"]


@click.command()
@click.option(
    "--get",
    "-g",
    "get",
    is_flag=True,
    help="Flag to get query info. Either get or push is required.",
)
@click.option(
    "--push",
    "-p",
    "push",
    is_flag=True,
    help="Flag to push queries to servers. Either get or push is required.",
)
@click.option(
    "--devices",
    "-d",
    "devices",
    is_flag=True,
    help="Flag to define asset type of devices",
)
@click.option(
    "--users", "-u", "users", is_flag=True, help="Flag to define asset type of users",
)
@click.option(
    "--ax-queries",
    "-a",
    "ax",
    is_flag=True,
    help="(Optional) Pull Axonius built queries only",
)
@click.option(
    "--tag",
    "-t",
    "tags",
    default=[],
    multiple=True,
    help="(Optional) Define tags to pull queries by.",
)
@click.option(
    "--path",
    "-p",
    "path",
    default="",
    help="(Optional) Define directory path to push or pull from. \
    Local directory by default.",
)
def start(tags, path, get, push, devices, users, ax):
    """Start data gathering."""
    asset_type = get_asset_type(devices=devices, users=users)

    if get:
        sq_data = find_targets(tags=tags, asset_type=asset_type)
        if ax:
            find_ax_queries(sq_data=sq_data, path=path)
        else:
            for data in sq_data:
                write_data(data=data, path=path)
    elif push:
        add_sq(path=path)
    else:
        sys.exit("No option to --push or --get specified")


def get_asset_type(devices, users):
    """Determine asset type."""
    if devices:
        asset_type = ctx.devices
    elif users:
        asset_type = ctx.users
    else:
        sys.exit("No asset type of devices or users defined")

    return asset_type


def ax_connect(url, key, secret):
    """Connect to Axonius."""
    try:
        ctx = axonapi.Connect(url=url, key=key, secret=secret, certwarn=False)
        ctx.start()
        return ctx
    except Exception:
        LOG.exception("Error connecting to Axonius instance")
        exit(1)


def find_targets(tags, asset_type):
    """Determine if tags were provided."""
    try:
        if tags == ():
            sq_data = sq_get_all(asset_type=asset_type)
            return sq_data
        else:
            sq_data = sq_by_tag(tags=tags, asset_type=asset_type)
            return sq_data
    except Exception:
        LOG.exception("Error parsing tags/target")
        exit(1)


def sq_get_all(asset_type):
    """Get all saved queries."""
    try:
        sq_data = asset_type.saved_query.get()
        return sq_data
    except Exception:
        LOG.exception("Error retrieving saved query data")
        exit(1)


def sq_by_tag(tags, asset_type):
    """Get saved query data."""
    try:
        for tag in tags:
            sq_data = asset_type.saved_query.get_by_tags(value=tags)
            return sq_data
    except Exception:
        LOG.exception("Error retrieving saved query data")
        exit(1)


def find_ax_queries(sq_data, path):
    """Fine AX Queries."""
    try:
        for data in sq_data:
            if "AX -" in data["name"]:
                write_data(data=data, path=path)
            else:
                continue
    except Exception:
        LOG.exception("Error finding AX queries")
        exit(1)


def write_data(data, path):
    """Write queries to a file."""
    try:
        name = data["name"]
        filename = f"{path}{name}.json"

        with open(filename, "w") as outfile:
            outfile.write(axonapi.tools.json_reload(data))
    except Exception:
        LOG.exception("Error writing queries to file")
        exit(1)


def add_sq(path):
    """Create saved queries from files."""
    try:
        if path == "":
            list_path = "."
        else:
            list_path = path

        for file in os.listdir(list_path):
            if file.endswith(".json"):
                sq_data = load_json(file=file, path=path)
                ctx.devices.saved_query._add(data=sq_data)
    except Exception:
        LOG.exception("Error writing queries from file")
        exit(1)


def load_json(file, path):
    """Load JSON data from file."""
    with open(f"{path}{file}") as file:
        data = json.load(file)
        return data


ctx = ax_connect(url=AX_URL, key=AX_KEY, secret=AX_SECRET)
start()
