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


    MIT License

    Copyright (c) 2019, 2020, 2021, 2022 PyFunceble
    Copyright (c) 2017, 2018, 2019, 2020, 2021, 2022 Nissar Chababy

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
"""

import copy
import time

import requests
from datetime import timedelta
from PyFunceble.cli.continuous_integration.exceptions import (
    ContinuousIntegrationException,
    StopExecution,
)
from PyFunceble.cli.continuous_integration.github_actions import GitHubActions
from PyFunceble.config.loader import ConfigLoader
from PyFunceble.helpers.dict import DictHelper
from requests_cache import CachedSession

REQ_SESSION = CachedSession(
    "http_cache",
    backend="sqlite",
    cache_control=True,
    expire_after=timedelta(days=1),
    allowable_codes=[200, 404],
    allowable_methods=["GET", "POST"],
    stale_if_error=True,
)

#requests.packages.urllib3.util.connection.HAS_IPV4 = False

OUTPUT_FILE = "user_agents.json"

URL = "https://user-agents.net/download"
PLATFORMS = ["linux", "win10", "macosx"]
REQ_DATA_BASE = {
    "browser": "chrome",
    "browser_bits": 64,
    "platform": "linux",
    "platform_bits": 64,
    "download": "json",
    "limit": 1,
}
BROWSERS = ["chrome", "firefox", "safari", "ie", "edge", "opera"]

try:
    HEADERS = {
        "User-Agent": DictHelper().from_json_file(
            OUTPUT_FILE, return_dict_on_error=False
        )["chrome"]["linux"]
    }
except TypeError:
    HEADERS = {
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36"
    }


def __request_latest_user_agent(data):
    """
    Provides the latest user agent from https://user-agents.net/

    :param dict data:
        The data to post

    :rtype: None, str
    :raise Exception if we get something which is not 200 nor 404.
    """

    req = REQ_SESSION.post(URL, data=data, headers=HEADERS, timeout=10.0)

    if req.status_code in [404]:
        return None

    if not req.status_code in [200]:
        raise Exception(
            f"Could not get response to work with while requesting.\n"
            f"URL:{req.url}\n"
            f"STATUS: {req.status_code}\n"
            f"DATA: {data}\n"
            f"HEADERS: {HEADERS}"
        )

    result = req.json()[-1]

    if result:
        return "".join([x for x in result.split() if "ip:" not in x])

    return result


def get_latest_user_agents(browsers, platforms):
    """
    Fetch the latest user agent of the given
    browser at the given platform.

    :param list browser:
        A list of browser to get information about.
    :param list platforms:
        A list of platforms to get information for.
    """

    result = {}

    for browser in browsers:
        data = copy.deepcopy(REQ_DATA_BASE)
        data["browser"] = browser

        for platform in platforms:
            data["platform"] = platform

            if "mac" in platform:
                del data["browser_bits"]
                del data["platform_bits"]

            if browser not in result:
                result[browser] = {}

            print(f"Starting: {browser} | {platform}")
            result[browser][platform] = __request_latest_user_agent(data)
            print(f"Finished: {browser} | {platform}")

            time.sleep(60.0)

    return result


if __name__ == "__main__":
    # We initiate the repostiory.
    try:
        CI_ENGINE = GitHubActions(
            authorized=True, end_commit_message=f"Update of {OUTPUT_FILE}"
        )
        CI_ENGINE.init()
    except ContinuousIntegrationException:
        pass

    DictHelper(get_latest_user_agents(BROWSERS, PLATFORMS)).to_json_file(OUTPUT_FILE)

    try:
        CI_ENGINE.apply_end_commit()
    except StopExecution:
        pass
