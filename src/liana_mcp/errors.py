"""Messages safe to return to an MCP caller; never include raw RPC errors."""


class SafetyError(Exception):
    """A local precondition failed. The message contains no runtime identifiers."""
