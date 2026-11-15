"""Source repositories for the synthetic SWE trajectory dataset.

Every repo is pure Python with a permissive license (Apache-2.0 compatible
for redistribution of derived training data). Repos used by the public
competition tasks are excluded (see EXCLUDED_REPOS) and must never be added.
"""
import os

WORK = os.environ.get("SWE_WORK", "/tmp/claude-0/work")
REPOS_DIR = os.path.join(WORK, "repos")
WS_DIR = os.path.join(WORK, "ws")
VENV = os.path.join(WORK, "venv")

# Public competition task repos (fastapi_*, requests_*, rich_*, httpx seen in
# the paper code). Re-check against DataSets/public/data/tasks.jsonl and add
# any other repo found there.
EXCLUDED_REPOS = {"fastapi", "requests", "rich", "httpx", "starlette",
                  "pydantic", "typer", "flask", "urllib3"}

# name -> (github slug, SPDX license id)
REPOS = {
    "arrow": ("arrow-py/arrow", "Apache-2.0"),
    "attrs": ("python-attrs/attrs", "MIT"),
    "boltons": ("mahmoud/boltons", "BSD-3-Clause"),
    "bottle": ("bottlepy/bottle", "MIT"),
    "cachetools": ("tkem/cachetools", "MIT"),
    "cerberus": ("pyeve/cerberus", "ISC"),
    "click": ("pallets/click", "BSD-3-Clause"),
    "dacite": ("konradhalas/dacite", "MIT"),
    "funcy": ("Suor/funcy", "BSD-3-Clause"),
    "glom": ("mahmoud/glom", "BSD-3-Clause"),
    "humanize": ("python-humanize/humanize", "MIT"),
    "iniconfig": ("pytest-dev/iniconfig", "MIT"),
    "isodate": ("gweis/isodate", "BSD-3-Clause"),
    "itsdangerous": ("pallets/itsdangerous", "BSD-3-Clause"),
    "jinja": ("pallets/jinja", "BSD-3-Clause"),
    "jsonschema": ("python-jsonschema/jsonschema", "MIT"),
    "markupsafe": ("pallets/markupsafe", "BSD-3-Clause"),
    "marshmallow": ("marshmallow-code/marshmallow", "MIT"),
    "mistune": ("lepture/mistune", "BSD-3-Clause"),
    "more-itertools": ("more-itertools/more-itertools", "MIT"),
    "packaging": ("pypa/packaging", "Apache-2.0 OR BSD-2-Clause"),
    "pluggy": ("pytest-dev/pluggy", "MIT"),
    "prettytable": ("jazzband/prettytable", "BSD-3-Clause"),
    "pydash": ("dgilland/pydash", "MIT"),
    "pyjwt": ("jpadilla/pyjwt", "MIT"),
    "pyparsing": ("pyparsing/pyparsing", "MIT"),
    "python-semver": ("python-semver/python-semver", "BSD-3-Clause"),
    "python-slugify": ("un33k/python-slugify", "MIT"),
    "python-sortedcontainers": ("grantjenks/python-sortedcontainers", "Apache-2.0"),
    "python-tabulate": ("astanin/python-tabulate", "MIT"),
    "schema": ("keleshev/schema", "MIT"),
    "sqlparse": ("andialbrecht/sqlparse", "BSD-3-Clause"),
    "tomlkit": ("python-poetry/tomlkit", "MIT"),
    "toolz": ("pytoolz/toolz", "BSD-3-Clause"),
    "voluptuous": ("alecthomas/voluptuous", "BSD-3-Clause"),
    "xmltodict": ("martinblech/xmltodict", "MIT"),
}

assert not (set(REPOS) & EXCLUDED_REPOS)
