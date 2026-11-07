#!/usr/bin/env python3

"""
The tool to check the availability or syntax of domains, IPv4, IPv6 or URL.

::


    ██████╗ ██╗   ██╗███████╗██╗   ██╗███╗   ██╗ ██████╗███████╗██████╗ ██╗     ███████╗
    ██╔══██╗╚██╗ ██╔╝██╔════╝██║   ██║████╗  ██║██╔════╝██╔════╝██╔══██╗██║     ██╔════╝
    ██████╔╝ ╚████╔╝ █████╗  ██║   ██║██╔██╗ ██║██║     █████╗  ██████╔╝██║     █████╗
    ██╔═══╝   ╚██╔╝  ██╔══╝  ██║   ██║██║╚██╗██║██║     ██╔══╝  ██╔══██╗██║     ██╔══╝
    ██║        ██║   ██║     ╚██████╔╝██║ ╚████║╚██████╗███████╗██████╔╝███████╗███████╗
    ╚═╝        ╚═╝   ╚═╝      ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝╚══════╝╚═════╝ ╚══════╝╚══════╝

This script is part of the PyFunceble project.

Author:
    Nissar Chababy, @funilrys, contactTATAfunilrysTODTODcom

Special thanks:
    https://pyfunceble.github.io/special-thanks.html

Contributors:
    https://pyfunceble.github.io/contributors.html

Project link:
    https://github.com/funilrys/PyFunceble

Project documentation:
    https://pyfunceble.readthedocs.io/en/dev/

Project homepage:
    https://pyfunceble.github.io/

License:
::


    Copyright (c) 2017-2026 Nissar Chababy

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        https://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""

import functools
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Callable, Dict

import requests
from bs4 import BeautifulSoup
from PyFunceble.cli.continuous_integration.exceptions import (
    ContinuousIntegrationException,
    StopExecution,
)
from PyFunceble.cli.continuous_integration.github_actions import GitHubActions
from PyFunceble.helpers.dict import DictHelper

# pylint: disable=too-many-return-statements,too-many-branches,too-many-locals


class UserAgentsUpdater:
    """
    Provides the user agents updater.

    :param bool learning_mode:
        Activates the learning mode.

        .. warning::
            This is only for development purposes.
    """

    DEFAULT_TIMEOUT = 60
    CACHE_EXPIRATION = 3600 * 24 * 7  # 1 week

    OUTPUT_FILE = "user_agents.json"

    CACHE_FILE = "user_agent_cache.json"
    LEARNING_FILE = "learning.xml"

    URL = "https://www.useragents.me/"

    learning_mode = False

    def __init__(self, learning_mode: bool = False):
        self.learning_mode = learning_mode

    def execute_if_authorized(  # pylint: disable=no-self-argument
        default: Any = None,
    ) -> Callable[..., Callable[..., Any]]:
        """
        Executes the decorated method only if we are authorized to process.
        Otherwise, apply the given :code:`default`.
        """

        def inner_method(func) -> Callable[..., Any]:
            @functools.wraps(func)
            def wrapper(self, *args, **kwargs):
                if self.authorized:
                    return func(self, *args, **kwargs)  # pylint: disable=not-callable
                return default

            return wrapper

        return inner_method

    @property
    def default_user_agent(self) -> str:
        """
        Provides the default user agent to use.

        :return:
            The default user agent to use.
        """

        try:
            return DictHelper().from_json_file(
                self.OUTPUT_FILE, return_dict_on_error=False
            )["@modern"]["chrome"]["linux"]
        except TypeError:
            return (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/107.0.0.0 Safari/537.36"
            )

    @property
    def authorized(self) -> bool:
        """
        Checks if we are authorized to run.
        """

        cache = self.read_cache()

        if not cache or not cache.get("data"):
            return True

        cache_timestamp = datetime.fromisoformat(cache["@timestamp"]).replace(tzinfo=timezone.utc)
        elapsed = datetime.now(timezone.utc) - cache_timestamp

        return elapsed.total_seconds() > self.CACHE_EXPIRATION

    def read_cache(self) -> dict:
        """
        Reads the cache.
        """

        return (
            DictHelper().from_json_file(self.CACHE_FILE, return_dict_on_error=False)
            or {}
        )

    @execute_if_authorized(None)  # pylint: disable=too-many-function-args
    def fetch_user_agents(self, *, write_cache: bool = True) -> Dict[str, Any]:
        """
        Fetches the user agents from the source.
        """

        if not self.learning_mode:
            response = requests.get(self.URL, timeout=self.DEFAULT_TIMEOUT)
            response_content = response.text
        else:
            with open(self.LEARNING_FILE, "r", encoding="utf-8") as file_stream:
                response_content = file_stream.read()

        pretty_soup = BeautifulSoup(response_content, "html.parser")
        fetched_data = {}

        logging.debug(pretty_soup)

        for container in pretty_soup.find_all("section", id=True):
            category_id = container["id"]
            if category_id in ("desktop", "mobile", "tablet"):
                agent_type, device_group = "common", category_id
            elif category_id.startswith("latest-"):
                agent_type, device_group = "latest", category_id[len("latest-") :]
            else:
                continue

            table = container.find("table")
            if not table or not table.find("thead") or not table.find("tbody"):
                continue

            headers = [
                header.get_text(strip=True).lower().replace(" ", "")
                for header in table.find("thead").find_all("th")
            ]

            if not {"useragent", "os", "browser"}.issubset(headers):
                continue

            logging.debug("ID: %s", category_id)
            logging.debug("Agent type: %s | Device group: %s", agent_type, device_group)
            logging.debug("Headers: %s", headers)

            for row in table.find("tbody").find_all("tr"):
                cells = row.find_all("td")
                datasets = dict(zip(headers, [x.get_text(strip=True) for x in cells]))

                logging.debug("Cells: %s | Datasets: %s", cells, datasets)

                if not all(datasets.get(key) for key in ("useragent", "os", "browser")):
                    continue

                if "device" in datasets and "more info" in datasets["device"]:
                    datasets["device"] = datasets["device"].split()[0].strip()

                datasets["normalized_browser"] = self.normalize_browser(
                    datasets["browser"]
                )
                datasets["normalized_os"] = self.normalize_os(datasets["os"])

                fetched_data.setdefault(agent_type, {}).setdefault(device_group, []).append(
                    datasets
                )

        if not fetched_data:
            logging.warning("No user agents found; leaving existing files unchanged")
            return {}

        cache_data = {
            "@timestamp": datetime.now(timezone.utc).isoformat(),
            "data": fetched_data,
        }

        logging.debug(fetched_data)

        if write_cache:
            DictHelper(cache_data).to_json_file(self.CACHE_FILE, indent=2)

        return cache_data

    def normalize_browser(self, browser: str) -> str:
        """
        Normalizes the given browser.

        :param str browser:
            The browser to normalize.

        :return:
            The normalized browser.
        """

        if "chrome" in browser.lower() or "google" in browser.lower():
            return "chrome"

        if "firefox" in browser.lower():
            return "firefox"

        if "safari" in browser.lower():
            return "safari"

        if "opera" in browser.lower():
            return "opera"

        if "other" in browser.lower():
            return "other"

        if "edge" in browser.lower():
            return "edge"

        if "samsung" in browser.lower():
            return "samsung"

        if "android" in browser.lower():
            return "android"

        return browser.split(" ", 1)[0].lower()

    def normalize_os(self, os: str) -> str:
        """
        Normalizes the given OS.

        :param str os:
            The OS to normalize.

        :return:
            The normalized OS.
        """

        mac_os = ["mac", "mac os", "macos", "macintosh"]
        linux_os = ["linux", "ubuntu", "debian", "fedora", "centos", "redhat"]

        if any(x in os.lower() for x in linux_os):
            return "linux"

        if "windows" in os.lower():
            return "windows"

        if any(x in os.lower() for x in mac_os):
            return "macosx"

        if "ios" in os.lower():
            return "ios"

        if "android" in os.lower():
            return "android"

        if "ios" in os.lower():
            return "ios"

        return os.split(" ", 1)[0].lower()

    def generate_user_agents(self) -> Dict[str, Any]:
        """
        Generates the final and normalized user agents file.
        """

        cache = self.read_cache()

        if not cache:
            return {}

        normalized_data = {"@modern": {}}

        for device_groups in cache["data"].values():
            for user_agents in device_groups.values():
                for user_agent in user_agents:
                    if (
                        user_agent["normalized_browser"] not in normalized_data
                        or user_agent["normalized_browser"]
                        not in normalized_data["@modern"]
                    ):
                        normalized_data[user_agent["normalized_browser"]] = {}
                        normalized_data["@modern"][
                            user_agent["normalized_browser"]
                        ] = {}

                    if (
                        user_agent["normalized_os"]
                        not in normalized_data[user_agent["normalized_browser"]]
                    ):
                        normalized_data[user_agent["normalized_browser"]][
                            user_agent["normalized_os"]
                        ] = None
                        normalized_data["@modern"][user_agent["normalized_browser"]][
                            user_agent["normalized_os"]
                        ] = []

                    normalized_data["@modern"][user_agent["normalized_browser"]][
                        user_agent["normalized_os"]
                    ].append(user_agent["useragent"])

                    normalized_data[user_agent["normalized_browser"]][
                        user_agent["normalized_os"]
                    ] = secrets.choice(
                        normalized_data["@modern"][user_agent["normalized_browser"]][
                            user_agent["normalized_os"]
                        ]
                    )

                    if user_agent["normalized_os"] == "windows":
                        normalized_data[user_agent["normalized_browser"]]["win10"] = (
                            normalized_data[user_agent["normalized_browser"]][
                                user_agent["normalized_os"]
                            ]
                        )
                        normalized_data["@modern"][user_agent["normalized_browser"]][
                            "win10"
                        ] = normalized_data["@modern"][
                            user_agent["normalized_browser"]
                        ][
                            user_agent["normalized_os"]
                        ]

        if not normalized_data["@modern"]:
            return {}

        necessary = ["linux", "macosx", "windows", "win10"]

        for browser, platforms in normalized_data["@modern"].items():
            fallback = list(
                dict.fromkeys(agent for agents in platforms.values() for agent in agents)
            )
            for os in necessary:
                if not platforms.get(os):
                    platforms[os] = fallback.copy()
                    normalized_data[browser][os] = secrets.choice(fallback)

        DictHelper(normalized_data).to_json_file(self.OUTPUT_FILE, indent=2)

        return normalized_data


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s :: %(levelname)s :: %(message)s"
    )

    updater = UserAgentsUpdater()
    fetched = updater.fetch_user_agents(write_cache=False)
    if fetched:
        try:
            CI_ENGINE = GitHubActions(
                authorized=True,
                end_commit_message=f"Update of {UserAgentsUpdater.OUTPUT_FILE}",
            )
            CI_ENGINE.init()
        except ContinuousIntegrationException:
            pass

        DictHelper(fetched).to_json_file(updater.CACHE_FILE, indent=2)
        updater.generate_user_agents()

        try:
            CI_ENGINE.apply_end_commit()
        except StopExecution:
            pass
