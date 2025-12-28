#!/usr/bin/env python3
"""
Video Sampling and Concatenation Tool

Samples intervals from .ts video files and concatenates them into a single MP4 output.
"""

import argparse
import random
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil

import av


@dataclass
class VideoFile:
    """Represents a discovered video file with its metadata."""
    path: Path
    filename: str
    file_timestamp: datetime
    duration: float
    timeline_start: float = 0.0
    timeline_end: float = 0.0


@dataclass
class Interval:
    """Represents a time interval in the output video."""
    interval_id: int
    start_time: float
    end_time: float
    video_files: list["VideoFile"] = None

    def __post_init__(self):
        if self.video_files is None:
            self.video_files = []


@dataclass
class Sample:
    """Represents a sample to be extracted from a video file."""
    interval_id: int
    timeline_start: float
    source_file: "VideoFile"
    file_offset: float
    duration: float


FFMPEG_PATH = "ffmpeg"


def find_ffmpeg() -> str | None:
    """Find FFmpeg executable, checking common locations on Windows."""
    common_paths = [
        "ffmpeg",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ]

    for path in common_paths:
        try:
            result = subprocess.run(
                [path, "-version"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            if result.returncode == 0:
                return path
        except FileNotFoundError:
            continue

    return None


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Sample and concatenate video files into a single MP4 output."
    )
    parser.add_argument(
        "path",
        type=str,
        help="Directory containing .ts video files"
    )
    parser.add_argument(
        "interval_duration",
        type=float,
        help="Duration of each sample interval (in seconds)"
    )
    parser.add_argument(
        "total_duration",
        type=float,
        help="Total duration of output video (in seconds)"
    )
    return parser.parse_args()


def parse_filename_timestamp(filename: str) -> datetime:
    """
    Parse timestamp from filename format: xxx_YYMMDD-HHMMSSx
    Extracts YY (year), MM (month), DD (day), HH (hour), MM (minute), SS (second).
    """
    pattern = r'_(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})'
    match = re.search(pattern, filename)

    if not match:
        raise ValueError(f"Could not parse timestamp from filename: {filename}")

    year = 2000 + int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    hour = int(match.group(4))
    minute = int(match.group(5))
    second = int(match.group(6))

    return datetime(year, month, day, hour, minute, second)


def get_video_duration(filepath: Path) -> float:
    """Get video duration in seconds using PyAV."""
    with av.open(str(filepath)) as container:
        if container.duration is not None:
            return container.duration / av.time_base
        video_stream = next((s for s in container.streams if s.type == 'video'), None)
        if video_stream and video_stream.duration:
            return float(video_stream.duration * video_stream.time_base)
    return 0.0


def discover_video_files(directory: Path) -> list[VideoFile]:
    """Scan directory for .ts video files and read their metadata."""
    video_files = []

    ts_files = list(directory.glob("*.ts"))

    if not ts_files:
        print(f"No .ts files found in {directory}")
        return video_files

    for filepath in ts_files:
        try:
            file_timestamp = parse_filename_timestamp(filepath.name)
            duration = get_video_duration(filepath)

            video_file = VideoFile(
                path=filepath,
                filename=filepath.name,
                file_timestamp=file_timestamp,
                duration=duration
            )
            video_files.append(video_file)
        except Exception as e:
            print(f"Warning: Could not read {filepath.name}: {e}")

    return video_files


def format_duration(seconds: float) -> str:
    """Format duration in seconds to HH:MM:SS.mmm format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def build_timeline_index(video_files: list[VideoFile]) -> list[VideoFile]:
    """Sort video files by timestamp and assign timeline positions."""
    sorted_files = sorted(video_files, key=lambda vf: vf.file_timestamp)

    current_time = 0.0
    for vf in sorted_files:
        vf.timeline_start = current_time
        vf.timeline_end = current_time + vf.duration
        current_time = vf.timeline_end

    return sorted_files


def create_intervals(total_video_duration: float, interval_duration: float, total_output_duration: float) -> list[
    Interval]:
    """Create interval structure based on video timeline."""
    num_intervals = int(total_output_duration / interval_duration)
    source_interval_duration = total_video_duration / num_intervals

    intervals = []
    for i in range(num_intervals):
        interval = Interval(
            interval_id=i,
            start_time=i * source_interval_duration,
            end_time=(i + 1) * source_interval_duration
        )
        intervals.append(interval)

    return intervals


def map_videos_to_intervals(video_files: list[VideoFile], intervals: list[Interval]) -> None:
    """Map which video files fall into each interval."""
    for interval in intervals:
        for vf in video_files:
            if vf.timeline_end > interval.start_time and vf.timeline_start < interval.end_time:
                interval.video_files.append(vf)


def display_discovery_results(video_files: list[VideoFile], total_duration: float) -> None:
    """Display formatted output of discovered files."""
    print("\n" + "=" * 70)
    print("VIDEO FILE DISCOVERY RESULTS")
    print("=" * 70)

    print(f"\n{'#':<4} {'Filename':<40} {'Duration':<15} {'Timestamp'}")
    print("-" * 70)

    for i, vf in enumerate(video_files, 1):
        timestamp = vf.file_timestamp.strftime("%Y-%m-%d %H:%M:%S")
        print(f"{i:<4} {vf.filename:<40} {format_duration(vf.duration):<15} {timestamp}")

    print("-" * 70)
    print(f"{'Total files:':<45} {len(video_files)}")
    print(f"{'Total duration:':<45} {format_duration(total_duration)}")
    print("=" * 70 + "\n")


def find_file_at_timeline_position(video_files: list[VideoFile], position: float) -> VideoFile | None:
    """Find the video file that contains the given timeline position."""
    for vf in video_files:
        if vf.timeline_start <= position < vf.timeline_end:
            return vf
    return None


def create_sampling_plan(intervals: list[Interval], video_files: list[VideoFile], sample_duration: float) -> list[
    Sample]:
    """Create a sampling plan by picking random samples from each interval."""
    samples = []

    for interval in intervals:
        if not interval.video_files:
            print(f"Warning: No video files in interval {interval.interval_id}")
            continue

        valid_sample_found = False
        max_attempts = 100

        for _ in range(max_attempts):
            max_start = interval.end_time - sample_duration
            if max_start < interval.start_time:
                max_start = interval.start_time

            sample_start = random.uniform(interval.start_time, max_start)
            sample_end = sample_start + sample_duration

            source_file = find_file_at_timeline_position(video_files, sample_start)
            if source_file is None:
                continue

            if sample_end <= source_file.timeline_end:
                file_offset = sample_start - source_file.timeline_start
                sample = Sample(
                    interval_id=interval.interval_id,
                    timeline_start=sample_start,
                    source_file=source_file,
                    file_offset=file_offset,
                    duration=sample_duration
                )
                samples.append(sample)
                valid_sample_found = True
                break

        if not valid_sample_found:
            print(f"Warning: Could not find valid sample for interval {interval.interval_id}")

    return samples


def display_sampling_plan(samples: list[Sample]) -> None:
    """Display the sampling plan."""
    print("\n" + "=" * 100)
    print("SAMPLING PLAN")
    print("=" * 100)

    print(f"\n{'#':<6} {'Timeline Start':<18} {'File Offset':<18} {'Duration':<12} {'Source File'}")
    print("-" * 100)

    for sample in samples:
        print(
            f"{sample.interval_id:<6} {format_duration(sample.timeline_start):<18} {format_duration(sample.file_offset):<18} {format_duration(sample.duration):<12} {sample.source_file.filename}")

    print("-" * 100)
    print(f"Total samples: {len(samples)}")
    print("=" * 100 + "\n")


def display_timeline(intervals: list[Interval], interval_duration: float) -> None:
    """Display the timeline structure with all intervals."""
    print("\n" + "=" * 80)
    print("TIMELINE STRUCTURE")
    print("=" * 80)

    print(f"\nNumber of intervals: {len(intervals)}")
    print(f"Sample duration per interval: {interval_duration} seconds")
    print(
        f"Source duration per interval: {format_duration(intervals[0].end_time - intervals[0].start_time) if intervals else 'N/A'}")

    print(f"\n{'#':<6} {'Start Time':<18} {'End Time':<18} {'Files':<8} {'File Names'}")
    print("-" * 80)

    for interval in intervals:
        file_names = ", ".join(vf.filename[:20] for vf in interval.video_files[:3])
        if len(interval.video_files) > 3:
            file_names += "..."
        print(
            f"{interval.interval_id:<6} {format_duration(interval.start_time):<18} {format_duration(interval.end_time):<18} {len(interval.video_files):<8} {file_names}")

    print("=" * 80 + "\n")


def extract_samples(samples: list[Sample], temp_dir: Path) -> list[Path]:
    """Extract each sample segment using FFmpeg."""
    print("\n" + "=" * 80)
    print("EXTRACTING SAMPLES")
    print("=" * 80 + "\n")

    extracted_files = []

    for i, sample in enumerate(samples):
        output_file = temp_dir / f"sample_{i:03d}.mp4"

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", str(sample.source_file.path),
            "-ss", str(sample.file_offset),
            "-t", str(sample.duration),
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
            "-tune", "zerolatency",
            "-x264-params", "bframes=0",
            "-c:a", "aac",
            "-shortest",
            "-fflags", "+genpts",
            "-avoid_negative_ts", "make_zero",
            str(output_file)
        ]

        print(f"Extracting sample {i}: {sample.source_file.filename} @ {format_duration(sample.file_offset)}")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"  ERROR: {result.stderr[:200]}")
            continue

        if output_file.exists():
            try:
                with av.open(str(output_file)) as container:
                    duration = container.duration / av.time_base if container.duration else 0
                    print(f"  OK: {output_file.name} ({format_duration(duration)})")
                extracted_files.append(output_file)
            except Exception as e:
                print(f"  ERROR verifying: {e}")
        else:
            print(f"  ERROR: Output file not created")

    print(f"\nExtracted {len(extracted_files)} / {len(samples)} samples")
    print("=" * 80 + "\n")

    return extracted_files


def concatenate_samples(extracted_files: list[Path], temp_dir: Path, output_path: Path) -> bool:
    """Concatenate all extracted samples into final MP4."""
    print("\n" + "=" * 80)
    print("CONCATENATING SAMPLES")
    print("=" * 80 + "\n")

    concat_file = temp_dir / "concat.txt"
    with open(concat_file, "w") as f:
        for file in extracted_files:
            f.write(f"file '{file}'\n")

    print(f"Created concat file with {len(extracted_files)} entries")

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        "-fflags", "+genpts",
        str(output_path)
    ]

    print(f"Concatenating to: {output_path}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR: {result.stderr[:500]}")
        return False

    print("Concatenation complete")
    print("=" * 80 + "\n")
    return True


def display_output_info(output_path: Path) -> None:
    """Display information about the final output file."""
    print("\n" + "=" * 80)
    print("OUTPUT INFORMATION")
    print("=" * 80 + "\n")

    if not output_path.exists():
        print("ERROR: Output file does not exist")
        return

    file_size = output_path.stat().st_size
    size_mb = file_size / (1024 * 1024)

    try:
        with av.open(str(output_path)) as container:
            duration = container.duration / av.time_base if container.duration else 0
            print(f"Output file:    {output_path}")
            print(f"Duration:       {format_duration(duration)}")
            print(f"File size:      {size_mb:.2f} MB")
    except Exception as e:
        print(f"ERROR reading output: {e}")

    print("=" * 80 + "\n")


def main() -> int:
    """Main entry point."""
    args = parse_arguments()

    global FFMPEG_PATH
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("Error: FFmpeg is not installed or not found.")
        print("Please install FFmpeg: https://ffmpeg.org/download.html")
        return 1
    FFMPEG_PATH = ffmpeg
    print(f"Using FFmpeg: {FFMPEG_PATH}")

    directory = Path(args.path)
    if not directory.exists():
        print(f"Error: Path does not exist: {args.path}")
        return 1
    if not directory.is_dir():
        print(f"Error: Path is not a directory: {args.path}")
        return 1

    print(f"\nScanning for .ts files in: {directory.absolute()}")
    print(f"Interval duration: {args.interval_duration} seconds")
    print(f"Target output duration: {args.total_duration} seconds")

    video_files = discover_video_files(directory)

    if not video_files:
        print("Error: No video files found.")
        return 1

    total_duration = sum(vf.duration for vf in video_files)

    display_discovery_results(video_files, total_duration)

    # Stage 2: Build timeline index and create intervals
    video_files = build_timeline_index(video_files)
    intervals = create_intervals(total_duration, args.interval_duration, args.total_duration)
    map_videos_to_intervals(video_files, intervals)
    display_timeline(intervals, args.interval_duration)

    # Stage 3: Create sampling plan
    samples = create_sampling_plan(intervals, video_files, args.interval_duration)
    display_sampling_plan(samples)

    if len(samples) != len(intervals):
        print(f"Warning: Only {len(samples)} samples created for {len(intervals)} intervals")

    # Stage 4 & 5: Extract samples and concatenate
    temp_dir = Path(tempfile.mkdtemp(prefix="videin_"))
    output_path = directory / "output.mp4"

    try:
        extracted_files = extract_samples(samples, temp_dir)

        if not extracted_files:
            print("Error: No samples were extracted.")
            return 1

        success = concatenate_samples(extracted_files, temp_dir, output_path)

        if success:
            display_output_info(output_path)
        else:
            print("Error: Concatenation failed.")
            return 1
    finally:
        print(f"Cleaning up temp directory: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
