"""CLI interface for telegram-downloader."""

from __future__ import annotations

import asyncio
import sys

import csv
import io
import json

import click
from rich.console import Console
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TransferSpeedColumn
from rich.table import Table

from src.core.config import Config
from src.core.logger import setup_logger
from src.core.types import DownloadStatus, MediaType, SubscriptionStatus

console = Console()


def run_async(coro):
    """Run an async function."""
    return asyncio.run(coro)


async def _get_app(config: Config):
    """Create and initialize the application components."""
    from src.core.client import create_client
    from src.database.db import DatabaseManager
    from src.downloader.downloader import MediaDownloader
    from src.queue.download_queue import DownloadQueue
    from src.resolver.resolver import MediaResolver
    from src.scheduler.scheduler import DownloadScheduler
    from src.subscription.manager import SubscriptionManager

    client = create_client(config)
    db = DatabaseManager(config.db_path)
    await db.connect()

    downloader = MediaDownloader(client, config.download_path)
    resolver = MediaResolver(client)
    queue = DownloadQueue(
        downloader, db,
        max_concurrent=config.max_concurrent_downloads,
        max_retries=config.max_retries,
        retry_delay=config.retry_delay,
    )
    subscription = SubscriptionManager(client, db)
    scheduler = DownloadScheduler(
        client, db, queue,
        check_interval=config.check_interval,
    )

    return {
        "client": client,
        "db": db,
        "downloader": downloader,
        "resolver": resolver,
        "queue": queue,
        "subscription": subscription,
        "scheduler": scheduler,
    }


async def _start_client(client, config: Config) -> None:
    """Start the Telegram client, skipping interactive login if already authorized."""
    await client.connect()

    if await client.is_user_authorized():
        return

    # Not authorized - need interactive login
    if config.phone:
        await client.start(phone=config.phone)
    else:
        await client.start(phone=lambda: click.prompt("Enter phone number"))


def _parse_chat_id(chat_id: str) -> int | str:
    """Parse chat_id string to int (if numeric) or keep as username string."""
    return int(chat_id) if chat_id.lstrip("-").isdigit() else chat_id


@click.group()
@click.option("--env", default=None, help="Path to .env file")
@click.pass_context
def cli(ctx, env):
    """Telegram Downloader - Auto-download media from Telegram channels."""
    ctx.ensure_object(dict)
    config = Config.from_env(env)
    ctx.obj["config"] = config

    errors = config.validate()
    if errors and ctx.invoked_subcommand not in ("config", None):
        for err in errors:
            console.print(f"[red]Config error:[/red] {err}")
        console.print("\nSet up your .env file. See .env.example for reference.")
        sys.exit(1)

    setup_logger(level=config.log_level, log_dir=config.log_dir)


@cli.command()
@click.argument("chat_id")
@click.option("--limit", "-l", default=None, type=int, help="Max messages to scan")
@click.option("--videos/--no-videos", default=True, help="Download videos")
@click.option("--images/--no-images", default=True, help="Download images")
@click.option("--min-size", default=None, type=int, help="Min file size in bytes")
@click.option("--max-size", default=None, type=int, help="Max file size in bytes")
@click.pass_context
def download(ctx, chat_id, limit, videos, images, min_size, max_size):
    """Download media from a chat or channel.

    CHAT_ID can be a numeric ID or @username.
    """
    config = ctx.obj["config"]
    config.ensure_directories()

    media_types = []
    if videos:
        media_types.append(MediaType.VIDEO)
    if images:
        media_types.append(MediaType.IMAGE)

    async def _run():
        app = await _get_app(config)
        client = app["client"]

        try:
            await _start_client(client, config)
            console.print("[green]Connected to Telegram[/green]")

            target = _parse_chat_id(chat_id)

            # Resolve media
            console.print(f"Scanning [cyan]{chat_id}[/cyan] for media...")
            resolver = app["resolver"]
            items = await resolver.resolve_chat(
                chat_id=target,
                media_types=media_types,
                limit=limit,
                min_file_size=min_size,
                max_file_size=max_size,
            )

            if not items:
                console.print("[yellow]No media found[/yellow]")
                return

            console.print(f"Found [green]{len(items)}[/green] media items")

            # Enqueue and download
            queue = app["queue"]

            task_ids = await queue.enqueue_many(items)
            console.print(f"Enqueued [green]{len(task_ids)}[/green] new items "
                         f"({len(items) - len(task_ids)} duplicates skipped)")

            if task_ids:
                progress = Progress(
                    TextColumn("[bold]{task.fields[media_type]}"),
                    TextColumn("{task.description}"),
                    BarColumn(),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    console=console,
                )
                progress_tasks: dict[str, int] = {}  # task_id -> progress task id

                def _on_progress(p):
                    if p.task_id not in progress_tasks:
                        tid = progress.add_task(
                            p.file_name or "unknown",
                            total=p.total_bytes or 0,
                            media_type=p.media_type.value,
                        )
                        progress_tasks[p.task_id] = tid
                    progress.update(
                        progress_tasks[p.task_id],
                        completed=p.downloaded_bytes,
                    )

                queue.on_progress(_on_progress)

                with progress:
                    results = await queue.process_queue()

                completed = sum(1 for r in results if r.status == DownloadStatus.COMPLETED)
                failed = sum(1 for r in results if r.status == DownloadStatus.FAILED)
                console.print(
                    f"\nDone: [green]{completed} completed[/green], "
                    f"[red]{failed} failed[/red]"
                )
        finally:
            await app["db"].close()
            await client.disconnect()

    run_async(_run())


@cli.command()
@click.argument("chat_id")
@click.option("--videos/--no-videos", default=True, help="Download videos")
@click.option("--images/--no-images", default=True, help="Download images")
@click.option("--min-size", default=None, type=int, help="Min file size in bytes")
@click.option("--max-size", default=None, type=int, help="Max file size in bytes")
@click.pass_context
def subscribe(ctx, chat_id, videos, images, min_size, max_size):
    """Subscribe to a channel or chat for auto-download.

    CHAT_ID can be a numeric ID or @username.
    """
    config = ctx.obj["config"]

    media_types = []
    if videos:
        media_types.append(MediaType.VIDEO)
    if images:
        media_types.append(MediaType.IMAGE)

    async def _run():
        app = await _get_app(config)
        client = app["client"]

        try:
            await _start_client(client, config)
            sub_mgr = app["subscription"]

            target = _parse_chat_id(chat_id)
            sub = await sub_mgr.add(
                target,
                media_types=media_types,
                min_file_size=min_size,
                max_file_size=max_size,
            )
            console.print(
                f"[green]Subscribed to {sub.chat_title}[/green] "
                f"(id={sub.chat_id}, types={[mt.value for mt in sub.media_types]})"
            )
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
        finally:
            await app["db"].close()
            await client.disconnect()

    run_async(_run())


@cli.command()
@click.argument("chat_id")
@click.pass_context
def unsubscribe(ctx, chat_id):
    """Unsubscribe from a channel or chat."""
    config = ctx.obj["config"]

    async def _run():
        app = await _get_app(config)
        client = app["client"]

        try:
            await _start_client(client, config)
            sub_mgr = app["subscription"]

            target = _parse_chat_id(chat_id)
            removed = await sub_mgr.remove(target)
            if removed:
                console.print(f"[green]Unsubscribed from {chat_id}[/green]")
            else:
                console.print(f"[yellow]Not subscribed to {chat_id}[/yellow]")
        finally:
            await app["db"].close()
            await client.disconnect()

    run_async(_run())


@cli.command()
@click.argument("chat_id")
@click.pass_context
def pause(ctx, chat_id):
    """Pause a subscription (stop checking for new media)."""
    config = ctx.obj["config"]

    async def _run():
        app = await _get_app(config)

        try:
            target = _parse_chat_id(chat_id)
            numeric_id = target if isinstance(target, int) else None

            if numeric_id is None:
                client = app["client"]
                await _start_client(client, config)
                from src.resolver.resolver import MediaResolver
                resolver = MediaResolver(client)
                info = await resolver.get_chat_info(target)
                if not info:
                    console.print(f"[red]Chat not found: {chat_id}[/red]")
                    return
                numeric_id = info["id"]

            sub_mgr = app["subscription"]
            sub = await sub_mgr.get(numeric_id)
            if not sub:
                console.print(f"[yellow]Not subscribed to {chat_id}[/yellow]")
                return

            await sub_mgr.pause(numeric_id)
            console.print(f"[yellow]Paused subscription: {sub.chat_title or chat_id}[/yellow]")
        finally:
            await app["db"].close()
            if app.get("client") and app["client"].is_connected():
                await app["client"].disconnect()

    run_async(_run())


@cli.command()
@click.argument("chat_id")
@click.pass_context
def resume(ctx, chat_id):
    """Resume a paused subscription."""
    config = ctx.obj["config"]

    async def _run():
        app = await _get_app(config)

        try:
            target = _parse_chat_id(chat_id)
            numeric_id = target if isinstance(target, int) else None

            if numeric_id is None:
                client = app["client"]
                await _start_client(client, config)
                from src.resolver.resolver import MediaResolver
                resolver = MediaResolver(client)
                info = await resolver.get_chat_info(target)
                if not info:
                    console.print(f"[red]Chat not found: {chat_id}[/red]")
                    return
                numeric_id = info["id"]

            sub_mgr = app["subscription"]
            sub = await sub_mgr.get(numeric_id)
            if not sub:
                console.print(f"[yellow]Not subscribed to {chat_id}[/yellow]")
                return

            await sub_mgr.resume(numeric_id)
            console.print(f"[green]Resumed subscription: {sub.chat_title or chat_id}[/green]")
        finally:
            await app["db"].close()
            if app.get("client") and app["client"].is_connected():
                await app["client"].disconnect()

    run_async(_run())


@cli.command(name="list")
@click.pass_context
def list_subs(ctx):
    """List all subscriptions."""
    config = ctx.obj["config"]

    async def _run():
        app = await _get_app(config)

        try:
            sub_mgr = app["subscription"]
            subs = await sub_mgr.list_all()

            if not subs:
                console.print("[yellow]No subscriptions[/yellow]")
                return

            table = Table(title="Subscriptions")
            table.add_column("Chat ID", style="cyan")
            table.add_column("Title")
            table.add_column("Username")
            table.add_column("Status")
            table.add_column("Media Types")
            table.add_column("Last Checked")

            for sub in subs:
                status_style = {
                    "active": "green",
                    "paused": "yellow",
                    "error": "red",
                }.get(sub.status.value, "white")

                table.add_row(
                    str(sub.chat_id),
                    sub.chat_title or "-",
                    f"@{sub.chat_username}" if sub.chat_username else "-",
                    f"[{status_style}]{sub.status.value}[/{status_style}]",
                    ", ".join(mt.value for mt in sub.media_types),
                    str(sub.last_checked_message_id or "-"),
                )

            console.print(table)
        finally:
            await app["db"].close()

    run_async(_run())


@cli.command()
@click.pass_context
def status(ctx):
    """Show download statistics."""
    config = ctx.obj["config"]

    async def _run():
        app = await _get_app(config)

        try:
            db = app["db"]
            total = await db.get_download_count()
            completed = await db.get_download_count(status=DownloadStatus.COMPLETED)
            failed = await db.get_download_count(status=DownloadStatus.FAILED)

            subs = await db.get_all_subscriptions()
            active_subs = sum(1 for s in subs if s.status == SubscriptionStatus.ACTIVE)

            table = Table(title="Status")
            table.add_column("Metric", style="cyan")
            table.add_column("Value")

            table.add_row("Total downloads", str(total))
            table.add_row("Completed", f"[green]{completed}[/green]")
            table.add_row("Failed", f"[red]{failed}[/red]")
            table.add_row("Subscriptions (active/total)", f"{active_subs}/{len(subs)}")
            table.add_row("Download path", str(config.download_path))

            console.print(table)
        finally:
            await app["db"].close()

    run_async(_run())


@cli.command()
@click.pass_context
def run(ctx):
    """Start the scheduler daemon for auto-downloading.

    Runs continuously, checking subscriptions at the configured interval.
    Press Ctrl+C to stop.
    """
    config = ctx.obj["config"]
    config.ensure_directories()

    async def _run():
        app = await _get_app(config)
        client = app["client"]

        try:
            await _start_client(client, config)
            console.print("[green]Connected to Telegram[/green]")

            scheduler = app["scheduler"]
            queue = app["queue"]

            console.print(
                f"Starting scheduler (interval={config.check_interval}s)... "
                "Press Ctrl+C to stop."
            )

            await scheduler.start()

            # Process queue continuously
            while scheduler.is_running:
                results = await queue.process_queue()
                if results:
                    completed = sum(
                        1 for r in results if r.status == DownloadStatus.COMPLETED
                    )
                    console.print(f"Processed {len(results)} items ({completed} completed)")
                await asyncio.sleep(5)

        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping...[/yellow]")
        finally:
            if app.get("scheduler"):
                await app["scheduler"].stop()
            await app["db"].close()
            await client.disconnect()
            console.print("[green]Stopped[/green]")

    run_async(_run())


@cli.command()
@click.option("--chat-id", default=None, help="Filter by chat ID")
@click.option("--type", "media_type", default=None, type=click.Choice(["video", "image"]),
              help="Filter by media type")
@click.option("--limit", "-l", default=20, type=int, help="Number of records to show")
@click.option("--export", "export_fmt", default=None, type=click.Choice(["csv", "json"]),
              help="Export format (csv or json)")
@click.option("--output", "-o", default=None, type=click.Path(), help="Export file path")
@click.pass_context
def history(ctx, chat_id, media_type, limit, export_fmt, output):
    """View download history with optional export."""
    config = ctx.obj["config"]

    async def _run():
        app = await _get_app(config)

        try:
            db = app["db"]
            filter_chat = int(chat_id) if chat_id and chat_id.lstrip("-").isdigit() else None
            filter_type = MediaType(media_type) if media_type else None

            downloads = await db.get_downloads(
                chat_id=filter_chat,
                media_type=filter_type,
                limit=limit,
            )

            if not downloads:
                console.print("[yellow]No download history[/yellow]")
                return

            # Export mode
            if export_fmt:
                _export_downloads(downloads, export_fmt, output)
                return

            # Table display
            table = Table(title=f"Download History (showing {len(downloads)})")
            table.add_column("Date", style="dim")
            table.add_column("Chat ID", style="cyan")
            table.add_column("Sender")
            table.add_column("Type")
            table.add_column("File")
            table.add_column("Size")
            table.add_column("Status")

            for dl in downloads:
                date_str = dl["created_at"][:19] if dl.get("created_at") else "-"
                size = dl.get("file_size", 0) or 0
                size_str = _format_size(size)

                status_val = dl.get("status", "unknown")
                status_style = {"completed": "green", "failed": "red"}.get(status_val, "white")

                table.add_row(
                    date_str,
                    str(dl.get("chat_id", "-")),
                    dl.get("sender_name") or str(dl.get("sender_id") or "-"),
                    dl.get("media_type", "-"),
                    dl.get("file_name") or "-",
                    size_str,
                    f"[{status_style}]{status_val}[/{status_style}]",
                )

            console.print(table)
        finally:
            await app["db"].close()

    run_async(_run())


def _format_size(size_bytes: int) -> str:
    """Format file size to human readable string."""
    if size_bytes == 0:
        return "-"
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _export_downloads(downloads: list[dict], fmt: str, output_path: str | None) -> None:
    """Export download records to CSV or JSON."""
    if fmt == "json":
        content = json.dumps(downloads, indent=2, ensure_ascii=False, default=str)
    else:
        buf = io.StringIO()
        if downloads:
            writer = csv.DictWriter(buf, fieldnames=downloads[0].keys())
            writer.writeheader()
            writer.writerows(downloads)
        content = buf.getvalue()

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        console.print(f"[green]Exported {len(downloads)} records to {output_path}[/green]")
    else:
        console.print(content)


@cli.command()
def config():
    """Show current configuration."""
    cfg = Config.from_env()

    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("API ID", str(cfg.api_id) if cfg.api_id else "[red]not set[/red]")
    table.add_row("API Hash", "****" if cfg.api_hash else "[red]not set[/red]")
    table.add_row("Phone", cfg.phone or "[dim]not set[/dim]")
    table.add_row("Download path", str(cfg.download_path))
    table.add_row("DB path", str(cfg.db_path))
    table.add_row("Max concurrent", str(cfg.max_concurrent_downloads))
    table.add_row("Check interval", f"{cfg.check_interval}s")
    table.add_row("Log level", cfg.log_level)

    console.print(table)


if __name__ == "__main__":
    cli()
