"""CL Client CLI - Main command-line interface."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich import print as rprint

from cl_client import ComputeClient
from cl_client.models import JobResponse

console = Console()


class JobProgressTracker:
    """Track job progress with Rich progress bar."""

    def __init__(self, job_id: str, description: str):
        self.job_id = job_id
        self.description = description
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        )
        self.task_id = None
        self.completed = asyncio.Event()
        self.final_job: Optional[JobResponse] = None

    def __enter__(self):
        self.progress.start()
        self.task_id = self.progress.add_task(self.description, total=100)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.progress.stop()

    def on_progress(self, job: JobResponse):
        """Update progress bar."""
        if self.task_id is not None:
            self.progress.update(
                self.task_id,
                completed=job.progress,
                description=f"{self.description} [{job.status}]"
            )

    def on_complete(self, job: JobResponse):
        """Handle job completion."""
        self.final_job = job
        if self.task_id is not None:
            self.progress.update(
                self.task_id,
                completed=100,
                description=f"{self.description} [{job.status}]"
            )
        self.completed.set()

    async def wait(self, timeout: float = 60.0):
        """Wait for job completion."""
        try:
            await asyncio.wait_for(self.completed.wait(), timeout=timeout)
            return self.final_job
        except asyncio.TimeoutError:
            console.print(f"[red]Job {self.job_id} timed out after {timeout}s[/red]")
            return None


def print_job_result(job: JobResponse):
    """Print job result in a nice table."""
    table = Table(title=f"Job {job.job_id}")
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    table.add_row("Job ID", job.job_id)
    table.add_row("Task Type", job.task_type)
    table.add_row("Status", job.status)
    table.add_row("Progress", f"{job.progress}%")

    if job.task_output:
        table.add_row("Output", str(job.task_output))

    if job.error_message:
        table.add_row("Error", job.error_message)

    console.print(table)


@click.group()
@click.version_option()
def cli():
    """CL Client CLI - Command-line interface for compute operations.

    Examples:
      cl-client clip-embedding embed image.jpg --watch
      cl-client media-thumbnail generate video.mp4 -w 256 -h 256
      cl-client hash compute image.jpg
      cl-client download <job-id> output/result.npy result.npy
    """
    pass


@cli.command()
@click.argument("job_id", type=str)
@click.argument("file_path", type=str)
@click.argument("destination", type=click.Path(path_type=Path), required=False)
def download(job_id: str, file_path: str, destination: Optional[Path]):
    """Download output file from a completed job.

    Args:
        job_id: Job ID (UUID)
        file_path: Relative path to file (e.g., "output/embedding.npy")
        destination: Local path to save file (optional, defaults to filename)

    Examples:
        cl-client download abc123 output/clip_embedding.npy embedding.npy
        cl-client download abc123 output/thumbnail.jpg ./result.jpg
    """
    async def run():
        # Default destination to just the filename
        dest = destination or Path(file_path).name

        async with ComputeClient() as client:
            with console.status(f"[bold green]Downloading {file_path}..."):
                await client.download_job_file(job_id, file_path, dest)

            console.print(f"[green]✓ Downloaded to {dest}[/green]")
            console.print(f"  Job ID: {job_id}")
            console.print(f"  File: {file_path}")
            console.print(f"  Size: {dest.stat().st_size} bytes")

    asyncio.run(run())


# CLIP Embedding Commands


@cli.group()
def clip_embedding():
    """CLIP image embedding operations."""
    pass


@clip_embedding.command()
@click.argument("image", type=click.Path(exists=True, path_type=Path))
@click.option("--watch", "-w", is_flag=True, help="Watch progress in real-time")
@click.option("--timeout", "-t", default=60.0, help="Timeout in seconds")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Download embedding to this file")
def embed(image: Path, watch: bool, timeout: float, output: Optional[Path]):
    """Generate CLIP embedding for an image.

    Returns 512-dimensional embedding vector.

    Examples:
        cl-client clip-embedding embed image.jpg --output embedding.npy
        cl-client clip-embedding embed image.jpg --watch -o result.npy
    """
    async def run():
        async with ComputeClient() as client:
            if watch:
                # Real-time progress with MQTT
                tracker = JobProgressTracker(
                    job_id="pending",
                    description=f"CLIP embedding: {image.name}"
                )
                with tracker:
                    job = await client.clip_embedding.embed_image(
                        image=image,
                        on_progress=tracker.on_progress,
                        on_complete=tracker.on_complete,
                    )
                    tracker.job_id = job.job_id
                    final_job = await tracker.wait(timeout=timeout)

                if final_job and final_job.status == "completed":
                    console.print(f"[green]✓ Embedding generated successfully[/green]")
                    print_job_result(final_job)

                    # Download if output specified
                    if output and final_job.params and "output_path" in final_job.params:
                        output_path = final_job.params["output_path"]
                        await client.download_job_file(final_job.job_id, str(output_path), output)
                        console.print(f"[green]✓ Downloaded to {output}[/green]")

                elif final_job:
                    console.print(f"[red]✗ Job failed: {final_job.error_message}[/red]")
                    sys.exit(1)
            else:
                # Simple polling
                with console.status(f"[bold green]Processing {image.name}..."):
                    job = await client.clip_embedding.embed_image(
                        image=image,
                        wait=True,
                        timeout=timeout,
                    )

                if job.status == "completed":
                    console.print(f"[green]✓ Completed[/green]")
                    print_job_result(job)

                    # Download if output specified
                    if output and job.params and "output_path" in job.params:
                        output_path = job.params["output_path"]
                        await client.download_job_file(job.job_id, str(output_path), output)
                        console.print(f"[green]✓ Downloaded to {output}[/green]")

                else:
                    console.print(f"[red]✗ Failed: {job.error_message}[/red]")
                    sys.exit(1)

    asyncio.run(run())


# Media Thumbnail Commands


@cli.group()
def media_thumbnail():
    """Media thumbnail generation."""
    pass


@media_thumbnail.command()
@click.argument("media", type=click.Path(exists=True, path_type=Path))
@click.option("--width", "-w", type=int, required=True, help="Thumbnail width")
@click.option("--height", "-h", type=int, required=True, help="Thumbnail height")
@click.option("--watch", is_flag=True, help="Watch progress in real-time")
@click.option("--timeout", "-t", default=60.0, help="Timeout in seconds")
def generate(media: Path, width: int, height: int, watch: bool, timeout: float):
    """Generate thumbnail for image or video.

    Examples:
      cl-client media-thumbnail generate video.mp4 -w 256 -h 256
      cl-client media-thumbnail generate image.jpg -w 128 -h 128 --watch
    """
    async def run():
        async with ComputeClient() as client:
            if watch:
                tracker = JobProgressTracker(
                    job_id="pending",
                    description=f"Thumbnail: {media.name} ({width}x{height})"
                )
                with tracker:
                    job = await client.media_thumbnail.generate(
                        media=media,
                        width=width,
                        height=height,
                        on_progress=tracker.on_progress,
                        on_complete=tracker.on_complete,
                    )
                    tracker.job_id = job.job_id
                    final_job = await tracker.wait(timeout=timeout)

                if final_job and final_job.status == "completed":
                    console.print(f"[green]✓ Thumbnail generated[/green]")
                    print_job_result(final_job)
                elif final_job:
                    console.print(f"[red]✗ Failed: {final_job.error_message}[/red]")
                    sys.exit(1)
            else:
                with console.status(f"[bold green]Generating thumbnail..."):
                    job = await client.media_thumbnail.generate(
                        media=media,
                        width=width,
                        height=height,
                        wait=True,
                        timeout=timeout,
                    )

                if job.status == "completed":
                    console.print(f"[green]✓ Completed[/green]")
                    print_job_result(job)
                else:
                    console.print(f"[red]✗ Failed: {job.error_message}[/red]")
                    sys.exit(1)

    asyncio.run(run())


# Hash Commands


@cli.group()
def hash():
    """Perceptual image hashing."""
    pass


@hash.command()
@click.argument("image", type=click.Path(exists=True, path_type=Path))
@click.option("--watch", is_flag=True, help="Watch progress in real-time")
@click.option("--timeout", "-t", default=30.0, help="Timeout in seconds")
def compute(image: Path, watch: bool, timeout: float):
    """Compute perceptual hash for an image.

    Returns phash, dhash, and other hash values.
    """
    async def run():
        async with ComputeClient() as client:
            if watch:
                tracker = JobProgressTracker(
                    job_id="pending",
                    description=f"Hashing: {image.name}"
                )
                with tracker:
                    job = await client.hash.compute(
                        image=image,
                        on_progress=tracker.on_progress,
                        on_complete=tracker.on_complete,
                    )
                    tracker.job_id = job.job_id
                    final_job = await tracker.wait(timeout=timeout)

                if final_job and final_job.status == "completed":
                    console.print(f"[green]✓ Hash computed[/green]")
                    print_job_result(final_job)
                elif final_job:
                    console.print(f"[red]✗ Failed: {final_job.error_message}[/red]")
                    sys.exit(1)
            else:
                with console.status(f"[bold green]Computing hash..."):
                    job = await client.hash.compute(
                        image=image,
                        wait=True,
                        timeout=timeout,
                    )

                if job.status == "completed":
                    console.print(f"[green]✓ Completed[/green]")
                    print_job_result(job)
                else:
                    console.print(f"[red]✗ Failed: {job.error_message}[/red]")
                    sys.exit(1)

    asyncio.run(run())


# EXIF Commands


@cli.group()
def exif():
    """EXIF metadata extraction."""
    pass


@exif.command()
@click.argument("image", type=click.Path(exists=True, path_type=Path))
@click.option("--watch", is_flag=True, help="Watch progress in real-time")
@click.option("--timeout", "-t", default=30.0, help="Timeout in seconds")
def extract(image: Path, watch: bool, timeout: float):
    """Extract EXIF metadata from an image."""
    async def run():
        async with ComputeClient() as client:
            if watch:
                tracker = JobProgressTracker(
                    job_id="pending",
                    description=f"EXIF extraction: {image.name}"
                )
                with tracker:
                    job = await client.exif.extract(
                        image=image,
                        on_progress=tracker.on_progress,
                        on_complete=tracker.on_complete,
                    )
                    tracker.job_id = job.job_id
                    final_job = await tracker.wait(timeout=timeout)

                if final_job and final_job.status == "completed":
                    console.print(f"[green]✓ EXIF extracted[/green]")
                    print_job_result(final_job)
                elif final_job:
                    console.print(f"[red]✗ Failed: {final_job.error_message}[/red]")
                    sys.exit(1)
            else:
                with console.status(f"[bold green]Extracting EXIF..."):
                    job = await client.exif.extract(
                        image=image,
                        wait=True,
                        timeout=timeout,
                    )

                if job.status == "completed":
                    console.print(f"[green]✓ Completed[/green]")
                    print_job_result(job)
                else:
                    console.print(f"[red]✗ Failed: {job.error_message}[/red]")
                    sys.exit(1)

    asyncio.run(run())


# Face Detection Commands


@cli.group()
def face_detection():
    """Face detection operations."""
    pass


@face_detection.command()
@click.argument("image", type=click.Path(exists=True, path_type=Path))
@click.option("--watch", is_flag=True, help="Watch progress in real-time")
@click.option("--timeout", "-t", default=30.0, help="Timeout in seconds")
def detect(image: Path, watch: bool, timeout: float):
    """Detect faces in an image."""
    async def run():
        async with ComputeClient() as client:
            if watch:
                tracker = JobProgressTracker(
                    job_id="pending",
                    description=f"Face detection: {image.name}"
                )
                with tracker:
                    job = await client.face_detection.detect(
                        image=image,
                        on_progress=tracker.on_progress,
                        on_complete=tracker.on_complete,
                    )
                    tracker.job_id = job.job_id
                    final_job = await tracker.wait(timeout=timeout)

                if final_job and final_job.status == "completed":
                    console.print(f"[green]✓ Faces detected[/green]")
                    print_job_result(final_job)
                elif final_job:
                    console.print(f"[red]✗ Failed: {final_job.error_message}[/red]")
                    sys.exit(1)
            else:
                with console.status(f"[bold green]Detecting faces..."):
                    job = await client.face_detection.detect(
                        image=image,
                        wait=True,
                        timeout=timeout,
                    )

                if job.status == "completed":
                    console.print(f"[green]✓ Completed[/green]")
                    print_job_result(job)
                else:
                    console.print(f"[red]✗ Failed: {job.error_message}[/red]")
                    sys.exit(1)

    asyncio.run(run())


# Image Conversion Commands


@cli.group()
def image_conversion():
    """Image format conversion."""
    pass


@image_conversion.command()
@click.argument("image", type=click.Path(exists=True, path_type=Path))
@click.option("--format", "-f", "output_format", required=True,
              type=click.Choice(["png", "jpg", "jpeg", "webp", "gif", "bmp", "tiff"]),
              help="Output format")
@click.option("--quality", "-q", type=int, default=85, help="Quality (1-100)")
@click.option("--watch", is_flag=True, help="Watch progress in real-time")
@click.option("--timeout", "-t", default=60.0, help="Timeout in seconds")
def convert(image: Path, output_format: str, quality: int, watch: bool, timeout: float):
    """Convert image to different format.

    Examples:
      cl-client image-conversion convert photo.png -f jpg -q 90
      cl-client image-conversion convert image.jpg -f webp --watch
    """
    async def run():
        async with ComputeClient() as client:
            if watch:
                tracker = JobProgressTracker(
                    job_id="pending",
                    description=f"Converting {image.name} to {output_format}"
                )
                with tracker:
                    job = await client.image_conversion.convert(
                        image=image,
                        output_format=output_format,
                        quality=quality,
                        on_progress=tracker.on_progress,
                        on_complete=tracker.on_complete,
                    )
                    tracker.job_id = job.job_id
                    final_job = await tracker.wait(timeout=timeout)

                if final_job and final_job.status == "completed":
                    console.print(f"[green]✓ Conversion completed[/green]")
                    print_job_result(final_job)
                elif final_job:
                    console.print(f"[red]✗ Failed: {final_job.error_message}[/red]")
                    sys.exit(1)
            else:
                with console.status(f"[bold green]Converting..."):
                    job = await client.image_conversion.convert(
                        image=image,
                        output_format=output_format,
                        quality=quality,
                        wait=True,
                        timeout=timeout,
                    )

                if job.status == "completed":
                    console.print(f"[green]✓ Completed[/green]")
                    print_job_result(job)
                else:
                    console.print(f"[red]✗ Failed: {job.error_message}[/red]")
                    sys.exit(1)

    asyncio.run(run())


if __name__ == "__main__":
    cli()


# DINO Embedding Commands


@cli.group()
def dino_embedding():
    """DINO image embedding operations."""
    pass


@dino_embedding.command()
@click.argument("image", type=click.Path(exists=True, path_type=Path))
@click.option("--watch", "-w", is_flag=True, help="Watch progress in real-time")
@click.option("--timeout", "-t", default=60.0, help="Timeout in seconds")
def embed(image: Path, watch: bool, timeout: float):
    """Generate DINO embedding for an image.

    Returns 384-dimensional embedding vector.
    """
    async def run():
        async with ComputeClient() as client:
            if watch:
                tracker = JobProgressTracker(
                    job_id="pending",
                    description=f"DINO embedding: {image.name}"
                )
                with tracker:
                    job = await client.dino_embedding.embed_image(
                        image=image,
                        on_progress=tracker.on_progress,
                        on_complete=tracker.on_complete,
                    )
                    tracker.job_id = job.job_id
                    final_job = await tracker.wait(timeout=timeout)

                if final_job and final_job.status == "completed":
                    console.print(f"[green]✓ Embedding generated[/green]")
                    print_job_result(final_job)
                elif final_job:
                    console.print(f"[red]✗ Failed: {final_job.error_message}[/red]")
                    sys.exit(1)
            else:
                with console.status(f"[bold green]Processing..."):
                    job = await client.dino_embedding.embed_image(
                        image=image,
                        wait=True,
                        timeout=timeout,
                    )

                if job.status == "completed":
                    console.print(f"[green]✓ Completed[/green]")
                    print_job_result(job)
                else:
                    console.print(f"[red]✗ Failed: {job.error_message}[/red]")
                    sys.exit(1)

    asyncio.run(run())


# Face Embedding Commands


@cli.group()
def face_embedding():
    """Face embedding operations."""
    pass


@face_embedding.command()
@click.argument("image", type=click.Path(exists=True, path_type=Path))
@click.option("--watch", is_flag=True, help="Watch progress in real-time")
@click.option("--timeout", "-t", default=60.0, help="Timeout in seconds")
def embed(image: Path, watch: bool, timeout: float):
    """Generate face embeddings for an image."""
    async def run():
        async with ComputeClient() as client:
            if watch:
                tracker = JobProgressTracker(
                    job_id="pending",
                    description=f"Face embedding: {image.name}"
                )
                with tracker:
                    job = await client.face_embedding.embed_faces(
                        image=image,
                        on_progress=tracker.on_progress,
                        on_complete=tracker.on_complete,
                    )
                    tracker.job_id = job.job_id
                    final_job = await tracker.wait(timeout=timeout)

                if final_job and final_job.status == "completed":
                    console.print(f"[green]✓ Embeddings generated[/green]")
                    print_job_result(final_job)
                elif final_job:
                    console.print(f"[red]✗ Failed: {final_job.error_message}[/red]")
                    sys.exit(1)
            else:
                with console.status(f"[bold green]Processing..."):
                    job = await client.face_embedding.embed_faces(
                        image=image,
                        wait=True,
                        timeout=timeout,
                    )

                if job.status == "completed":
                    console.print(f"[green]✓ Completed[/green]")
                    print_job_result(job)
                else:
                    console.print(f"[red]✗ Failed: {job.error_message}[/red]")
                    sys.exit(1)

    asyncio.run(run())


# HLS Streaming Commands


@cli.group()
def hls_streaming():
    """HLS manifest generation for video streaming."""
    pass


@hls_streaming.command()
@click.argument("video", type=click.Path(exists=True, path_type=Path))
@click.option("--watch", is_flag=True, help="Watch progress in real-time")
@click.option("--timeout", "-t", default=120.0, help="Timeout in seconds")
def generate_manifest(video: Path, watch: bool, timeout: float):
    """Generate HLS manifest for a video file.

    Creates master playlist and variant playlists for adaptive streaming.
    """
    async def run():
        async with ComputeClient() as client:
            if watch:
                tracker = JobProgressTracker(
                    job_id="pending",
                    description=f"HLS manifest: {video.name}"
                )
                with tracker:
                    job = await client.hls_streaming.generate_manifest(
                        video=video,
                        on_progress=tracker.on_progress,
                        on_complete=tracker.on_complete,
                    )
                    tracker.job_id = job.job_id
                    final_job = await tracker.wait(timeout=timeout)

                if final_job and final_job.status == "completed":
                    console.print(f"[green]✓ HLS manifest generated[/green]")
                    print_job_result(final_job)
                elif final_job:
                    console.print(f"[red]✗ Failed: {final_job.error_message}[/red]")
                    sys.exit(1)
            else:
                with console.status(f"[bold green]Generating HLS manifest..."):
                    job = await client.hls_streaming.generate_manifest(
                        video=video,
                        wait=True,
                        timeout=timeout,
                    )

                if job.status == "completed":
                    console.print(f"[green]✓ Completed[/green]")
                    print_job_result(job)
                else:
                    console.print(f"[red]✗ Failed: {job.error_message}[/red]")
                    sys.exit(1)

    asyncio.run(run())
