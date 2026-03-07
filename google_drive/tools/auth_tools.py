"""Account management tools for working with multiple Google accounts."""

from mcp.server.fastmcp import Context

from google_drive.auth import (
    get_default_account,
    list_authenticated_accounts,
    set_default_account,
)
from google_drive.config import get_config


async def list_accounts(ctx: Context = None) -> str:
    """List all authenticated Google accounts and which one is the default.

    Use this to see which Google accounts are available and which will be used
    when no account_email is specified in other tools.

    If an account the user wants is not listed, instruct them to run this
    command in a terminal:
        python scripts/add_account.py --email <email>

    A browser will open for Google sign-in. After the user confirms it is
    complete, call switch_account to make it the default.
    """
    config = get_config()
    accounts = list_authenticated_accounts(config.config_dir)
    default = get_default_account(config.config_dir)

    if not accounts:
        return (
            "No Google accounts are authenticated with this server.\n\n"
            "To add an account, ask the user to run this command in a terminal:\n"
            "    python scripts/add_account.py\n\n"
            "A browser will open for Google sign-in. After the user confirms "
            "it is complete, call switch_account with the authenticated email."
        )

    lines = ["Authenticated Google accounts:\n"]
    for email in accounts:
        marker = " (default)" if email == default else ""
        lines.append(f"  {email}{marker}")

    if not default and accounts:
        lines.append(
            "\nNo default account is set. Call switch_account to set one."
        )

    return "\n".join(lines)


async def switch_account(email: str, ctx: Context = None) -> str:
    """Set the default Google account for Drive operations.

    The default account is used by all Drive tools when no account_email is
    specified. To use a non-default account for a specific operation, pass
    account_email explicitly to that tool.

    The account must already be authenticated — it must appear in list_accounts.
    To add a new account, instruct the user to run:
        python scripts/add_account.py --email <email>

    A browser will open for sign-in. After the user confirms it is complete,
    call switch_account again.

    Args:
        email: Email address of the Google account to set as default.
    """
    config = get_config()
    accounts = list_authenticated_accounts(config.config_dir)

    if email not in accounts:
        return (
            f"Account '{email}' is not authenticated with this server.\n\n"
            f"Ask the user to run this command in a terminal:\n"
            f"    python scripts/add_account.py --email {email}\n\n"
            f"A browser will open for Google sign-in. After the user confirms "
            f"sign-in is complete, call switch_account again."
        )

    set_default_account(config.config_dir, email)

    return f"Default Google account set to: {email}"


auth_tools = [list_accounts, switch_account]
