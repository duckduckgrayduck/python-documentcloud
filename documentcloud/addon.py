"""
This is a base class for DocumentCloud Add-Ons to inherit from.
It provides some common Add-On functionality.
"""

# Standard Library
import argparse
import json
import os
import sys

# Third Party
import requests

# Local
from .client import DocumentCloud


class BaseAddOn:
    """Functionality shared between normal Add-On's and Cron Add-On's"""

    def __init__(self):
        args = self._parse_arguments()
        client = self._create_client(args)

        # a unique identifier for this run
        self.id = args.pop("id", None)
        # Documents is a list of document IDs which were selected to run with this
        # addon activation
        self.documents = args.pop("documents", None)
        # Query is the search query selected to run with this addon activation
        self.query = args.pop("query", None)
        # user and org IDs
        self.user_id = args.pop("user", None)
        self.org_id = args.pop("organization", None)
        # add on specific data
        self.data = args.pop("data", None)

    def _create_client(self, args):
        client_kwargs = {k: v for k, v in args.items() if k in ["base_uri", "auth_uri"]}
        username = (
            args["username"] if "username" in args else os.environ.get("DC_USERNAME")
        )
        password = (
            args["password"] if "username" in args else os.environ.get("DC_USERNAME")
        )
        if username and password:
            client_kwargs["username"] = username
            client_kwargs["password"] = password
        self.client = DocumentCloud(**client_kwargs)
        if "refresh_token" in args:
            self.client.refresh_token = args["refresh_token"]
        if "token" in args:
            self.client.session.headers.update(
                {"Authorization": "Bearer {}".format(args["token"])}
            )

        # custom user agent for AddOns
        self.client.session.headers["User-Agent"] += " (DC AddOn)"

    def _parse_arguments():
        """Parse command line arguments"""
        parser = argparse.ArgumentParser(
            description="Run a DocumentCloud add on.\n\n"
            "Command line arguments are provided for testing locally.\n"
            "A JSON blob may also be passed in, as is done when running on "
            "GitHub actions."
        )
        parser.add_argument(
            "--username",
            help="DocumentCloud username - "
            "can also be passed in environment variable DC_USERNAME",
        )
        parser.add_argument(
            "--password",
            help="DocumentCloud password - "
            "can also be passed in environment variable DC_PASSWORD",
        )
        parser.add_argument("--token", help="DocumentCloud access token")
        parser.add_argument("--refresh_token", help="DocumentCloud refresh token")
        parser.add_argument("--documents", type=int, nargs="+", help="Document IDs")
        parser.add_argument("--query", help="Search query")
        parser.add_argument("--data", help="Parameter JSON")
        parser.add_argument("--base_uri", help="Set an alternate base URI")
        parser.add_argument("--auth_uri", help="Set an alternate auth URI")
        parser.add_argument("json", help="JSON blob for passing in arguments")
        args = parser.parse_args()
        # convert args to a dictionary
        args = vars(args)
        if "data" in args:
            args["data"] = json.loads(args["data"])
        blob = args.pop("json")
        # merge json blob into the arguments
        args.update(json.loads(blob))
        return args

    def send_mail(self, subject, content):
        """Send yourself an email"""
        return self.client.post(
            "messages/", json={"subject": subject, "content": content}
        )


class AddOn(BaseAddOn):
    """Base functionality for DocumentCloud Add-Ons."""

    def set_progress(self, progress):
        """Set the progress as a percentage between 0 and 100."""
        if not self.id:
            return None
        assert 0 <= progress <= 100
        return self.client.patch(f"addon_runs/{self.id}/", json={"progress": progress})

    def set_message(self, message):
        """Set the progress message."""
        if not self.id:
            return None
        return self.client.patch(f"addon_runs/{self.id}/", json={"message": message})

    def upload_file(self, file):
        """Uploads a file to the addon run."""
        if not self.id:
            return None
        # go to the beginning of the file
        file.seek(0)
        file_name = os.path.basename(file.name)
        resp = self.client.get(
            f"addon_runs/{self.id}/", params={"upload_file": file_name}
        )
        presigned_url = resp.json()["presigned_url"]
        # use buffer as it should always be binary, which requests wants
        response = requests.put(presigned_url, data=file.buffer)
        response.raise_for_status()
        return self.client.patch(
            f"addon_runs/{self.id}/", json={"file_name": file_name}
        )


class CronAddOn(BaseAddOn):
    """Base functionality for a Cron Add-On"""

    def __init__(self):
        self.client = DocumentCloud(
            username=os.environ["DC_USERNAME"], password=os.environ["DC_PASSWORD"]
        )
