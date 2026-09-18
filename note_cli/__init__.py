"""note — a decision-graph and goal notebook for a git repo."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("notegraph")
except PackageNotFoundError:          # running from a source tree, not installed
    __version__ = "0+unknown"
