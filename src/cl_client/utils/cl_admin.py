#!/usr/bin/env python3
"""CLI utility for managing CoLAN server users and configuration.

Usage:
    # List all users
    cl-admin --auth-url http://localhost:8010 --username admin --password admin users list

    # Create user with permissions
    cl-admin --auth-url http://localhost:8010 --username admin --password admin \
        users create testuser --password testpass --permissions ai_inference_support,media_store_read

    # Update user permissions
    cl-admin --auth-url http://localhost:8010 --username admin --password admin \
        users update testuser --permissions ai_inference_support,media_store_read,media_store_write

    # Delete user
    cl-admin --auth-url http://localhost:8010 --username admin --password admin \
        users delete testuser

    # Get store guest mode status
    cl-admin --auth-url http://localhost:8010 --store-url http://localhost:8011 \
        --username admin --password admin config get-guest-mode --service store

    # Get compute guest mode status
    cl-admin --auth-url http://localhost:8010 --compute-url http://localhost:8012 \
        --username admin --password admin config get-guest-mode --service compute

    # Enable store guest mode
    cl-admin --auth-url http://localhost:8010 --store-url http://localhost:8011 \
        --username admin --password admin config set-guest-mode store on

    # Enable compute guest mode
    cl-admin --auth-url http://localhost:8010 --compute-url http://localhost:8012 \
        --username admin --password admin config set-guest-mode compute on

    # Disable store guest mode
    cl-admin --auth-url http://localhost:8010 --store-url http://localhost:8011 \
        --username admin --password admin config set-guest-mode store off
"""

import asyncio
import sys
from typing import Any, Optional

import click
import httpx
from pydantic import BaseModel
from cl_client.auth_client import AuthClient
from cl_client.auth_models import UserCreateRequest, UserUpdateRequest
from cl_client.store_client import StoreClient
from cl_client.auth import JWTAuthProvider


class ServerRootResponse(BaseModel):
    """Server root endpoint response."""
    status: str
    service: str
    version: str
    guestMode: str = "off"


class CliContext(BaseModel):
    """CLI context object for passing data between commands."""
    auth_url: str
    username: str
    password: str
    store_url: str | None = None
    compute_url: str | None = None

    @classmethod
    def from_click_context(cls, ctx: click.Context) -> "CliContext":
        """Parse Click context object into Pydantic model."""
        return cls.model_validate(ctx.obj)


@click.group()
@click.option("--auth-url", required=True, help="Auth service URL")
@click.option("--username", required=True, help="Admin username")
@click.option("--password", required=True, help="Admin password")
@click.pass_context
def cli(ctx: click.Context, auth_url: str, username: str, password: str) -> None:
    """CoLAN server administration CLI."""
    ctx.ensure_object(dict)
    ctx.obj["auth_url"] = auth_url
    ctx.obj["username"] = username
    ctx.obj["password"] = password


@cli.group()
def users() -> None:
    """User management commands."""
    pass


@users.command("list")
@click.pass_context
def users_list(ctx: click.Context) -> None:
    """List all users."""
    cli_ctx = CliContext.from_click_context(ctx)
    asyncio.run(_list_users(cli_ctx.auth_url, cli_ctx.username, cli_ctx.password))


@users.command("create")
@click.argument("new_username")
@click.option("--password", "new_password", required=True, help="New user password")
@click.option("--permissions", default="", help="Comma-separated permissions")
@click.option("--admin", is_flag=True, help="Grant admin privileges")
@click.pass_context
def users_create(ctx: click.Context, new_username: str, new_password: str, permissions: str, admin: bool) -> None:
    """Create a new user."""
    cli_ctx = CliContext.from_click_context(ctx)
    perms = [p.strip() for p in permissions.split(",") if p.strip()]
    asyncio.run(_create_user(
        cli_ctx.auth_url,
        cli_ctx.username,
        cli_ctx.password,
        new_username,
        new_password,
        perms,
        admin
    ))


@users.command("update")
@click.argument("target_username")
@click.option("--password", "new_password", help="New password")
@click.option("--permissions", help="Comma-separated permissions")
@click.option("--admin", type=bool, help="Set admin status (true/false)")
@click.pass_context
def users_update(ctx: click.Context, target_username: str, new_password: Optional[str],
                 permissions: Optional[str], admin: Optional[bool]) -> None:
    """Update user details."""
    cli_ctx = CliContext.from_click_context(ctx)
    perms = [p.strip() for p in permissions.split(",") if p.strip()] if permissions else None
    asyncio.run(_update_user(
        cli_ctx.auth_url,
        cli_ctx.username,
        cli_ctx.password,
        target_username,
        new_password,
        perms,
        admin
    ))


@users.command("delete")
@click.argument("target_username")
@click.pass_context
def users_delete(ctx: click.Context, target_username: str) -> None:
    """Delete a user."""
    cli_ctx = CliContext.from_click_context(ctx)
    asyncio.run(_delete_user(cli_ctx.auth_url, cli_ctx.username, cli_ctx.password, target_username))


@cli.group()
@click.option("--store-url", help="Store service URL")
@click.option("--compute-url", help="Compute service URL")
@click.pass_context
def config(ctx: click.Context, store_url: Optional[str], compute_url: Optional[str]) -> None:
    """Server configuration commands."""
    ctx.obj["store_url"] = store_url
    ctx.obj["compute_url"] = compute_url


@config.command("get-guest-mode")
@click.option("--service", type=click.Choice(["store", "compute"]), required=True, help="Service to query")
@click.pass_context
def get_guest_mode(ctx: click.Context, service: str) -> None:
    """Get current guest mode status."""
    cli_ctx = CliContext.from_click_context(ctx)
    if service == "store":
        if not cli_ctx.store_url:
            click.echo("Error: --store-url required for store service", err=True)
            sys.exit(1)
        asyncio.run(_get_guest_mode_store(cli_ctx.store_url))
    else:  # compute
        if not cli_ctx.compute_url:
            click.echo("Error: --compute-url required for compute service", err=True)
            sys.exit(1)
        asyncio.run(_get_guest_mode_compute(cli_ctx.compute_url))


@config.command("set-guest-mode")
@click.argument("service", type=click.Choice(["store", "compute"]))
@click.argument("mode", type=click.Choice(["on", "off"]))
@click.pass_context
def set_guest_mode(ctx: click.Context, service: str, mode: str) -> None:
    """Enable or disable guest mode for a service."""
    cli_ctx = CliContext.from_click_context(ctx)
    enabled = (mode == "on")

    if service == "store":
        if not cli_ctx.store_url:
            click.echo("Error: --store-url required for store service", err=True)
            sys.exit(1)
        asyncio.run(_set_guest_mode_store(
            cli_ctx.auth_url,
            cli_ctx.store_url,
            cli_ctx.username,
            cli_ctx.password,
            enabled
        ))
    else:  # compute
        if not cli_ctx.compute_url:
            click.echo("Error: --compute-url required for compute service", err=True)
            sys.exit(1)
        asyncio.run(_set_guest_mode_compute(
            cli_ctx.auth_url,
            cli_ctx.compute_url,
            cli_ctx.username,
            cli_ctx.password,
            enabled
        ))


# Async implementation functions

async def _list_users(auth_url: str, username: str, password: str) -> None:
    """List all users in the system."""
    async with AuthClient(base_url=auth_url) as client:
        token_resp = await client.login(username, password)
        users = await client.list_users(token_resp.access_token)

        click.echo(f"\n{'ID':<6} {'Username':<20} {'Admin':<8} {'Active':<8} {'Permissions'}")
        click.echo("-" * 80)
        for user in users:
            perms = ",".join(user.permissions) if user.permissions else "-"
            click.echo(f"{user.id:<6} {user.username:<20} {str(user.is_admin):<8} {str(user.is_active):<8} {perms}")


async def _create_user(auth_url: str, admin_username: str, admin_password: str,
                       new_username: str, new_password: str, permissions: list[str], is_admin: bool) -> None:
    """Create a new user."""
    async with AuthClient(base_url=auth_url) as client:
        token_resp = await client.login(admin_username, admin_password)

        user_create = UserCreateRequest(
            username=new_username,
            password=new_password,
            permissions=permissions,
            is_admin=is_admin,
            is_active=True,  # New users are active by default
        )

        user = await client.create_user(token_resp.access_token, user_create)
        click.echo(f"✓ Created user: {user.username} (ID: {user.id})")
        if permissions:
            click.echo(f"  Permissions: {', '.join(permissions)}")
        if is_admin:
            click.echo("  Admin: Yes")


async def _update_user(auth_url: str, admin_username: str, admin_password: str,
                       target_username: str, new_password: Optional[str],
                       permissions: Optional[list[str]], is_admin: Optional[bool]) -> None:
    """Update user details."""
    async with AuthClient(base_url=auth_url) as client:
        token_resp = await client.login(admin_username, admin_password)

        # Get user ID by username
        users = await client.list_users(token_resp.access_token)
        target_user = next((u for u in users if u.username == target_username), None)
        if not target_user:
            click.echo(f"✗ User not found: {target_username}", err=True)
            sys.exit(1)

        update_req = UserUpdateRequest(
            password=new_password,
            permissions=permissions,
            is_admin=is_admin,
            is_active=None,  # Don't change is_active unless specified
        )

        user = await client.update_user(token_resp.access_token, target_user.id, update_req)
        click.echo(f"✓ Updated user: {user.username}")


async def _delete_user(auth_url: str, admin_username: str, admin_password: str,
                       target_username: str) -> None:
    """Delete a user."""
    async with AuthClient(base_url=auth_url) as client:
        token_resp = await client.login(admin_username, admin_password)

        # Get user ID by username
        users = await client.list_users(token_resp.access_token)
        target_user = next((u for u in users if u.username == target_username), None)
        if not target_user:
            click.echo(f"✗ User not found: {target_username}", err=True)
            sys.exit(1)

        await client.delete_user(token_resp.access_token, target_user.id)
        click.echo(f"✓ Deleted user: {target_username}")


async def _get_guest_mode_store(store_url: str) -> None:
    """Get store guest mode status."""
    async with StoreClient(base_url=store_url) as client:
        config = await client.get_config()
        status = "ENABLED" if config.guest_mode else "DISABLED"
        click.echo(f"Store guest mode: {status}")


async def _get_guest_mode_compute(compute_url: str) -> None:
    """Get compute guest mode status."""
    async with httpx.AsyncClient() as client:
        r = await client.get(compute_url)
        info_raw: Any = r.json()
        info = ServerRootResponse.model_validate(info_raw)
        status = "ENABLED" if info.guestMode == "on" else "DISABLED"
        click.echo(f"Compute guest mode: {status}")


async def _set_guest_mode_store(auth_url: str, store_url: str, username: str, password: str, enabled: bool) -> None:
    """Enable or disable store guest mode."""
    async with AuthClient(base_url=auth_url) as auth_client:
        token_resp = await auth_client.login(username, password)

        auth_provider = JWTAuthProvider(token=token_resp.access_token)
        async with StoreClient(base_url=store_url, auth_provider=auth_provider) as store_client:
            await store_client.update_read_auth(enabled=enabled)
            status = "ENABLED" if enabled else "DISABLED"
            click.echo(f"✓ Store guest mode {status}")


async def _set_guest_mode_compute(auth_url: str, compute_url: str, username: str, password: str, enabled: bool) -> None:
    """Enable or disable compute guest mode."""
    # Note: Implementation depends on compute service API
    # This is a placeholder - adjust based on actual compute service API
    click.echo("⚠ Compute guest mode configuration not yet implemented")
    click.echo("  Please configure compute guest mode via server configuration or admin API")
    sys.exit(1)


if __name__ == "__main__":
    cli(obj={})
