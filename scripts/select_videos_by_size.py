#!/usr/bin/env python3
"""Select videos from a folder based on file size distribution.

This script selects 5 videos from each of the following size ranges:
- Bottom 20% (smallest files)
- Middle 20% (40%-60% range)
- Top 20% (largest files)

Usage:
    python select_videos_by_size.py <input_folder> [output_file]

Args:
    input_folder: Path to the folder containing video files.
    output_file: Optional. Path to the output txt file. Default: selected_videos.txt
"""

import sys
from pathlib import Path

# Common video file extensions
VIDEO_EXTENSIONS = {
    '.mp4', '.mkv', '.mov', '.avi', '.wmv', '.flv', '.webm',
    '.m4v', '.mpeg', '.mpg', '.3gp', '.ts', '.mts', '.m2ts'
}


def get_video_files(folder_path):
    """Get all video files in the folder with their sizes.

    Args:
        folder_path: Path to the folder to scan.

    Returns:
        List of tuples (file_path, file_size) sorted by size ascending.
    """
    folder = Path(folder_path)
    if not folder.exists():
        raise ValueError(f"Folder does not exist: {folder_path}")
    if not folder.is_dir():
        raise ValueError(f"Path is not a directory: {folder_path}")

    video_files = []
    for file_path in folder.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS:
            file_size = file_path.stat().st_size
            video_files.append((file_path.resolve(), file_size))

    # Sort by file size ascending
    video_files.sort(key=lambda x: x[1])
    return video_files


def compute_indices(total, count):
    """Compute evenly distributed indices.

    Args:
        total: Total number of items.
        count: Number of items to select.

    Returns:
        List of indices to select.
    """
    if count <= 0 or total <= 0:
        return []
    if count >= total:
        return list(range(total))
    if count == 1:
        return [total // 2]

    # Evenly spaced indices including first and last
    step = (total - 1) / (count - 1)
    return [int(round(i * step)) for i in range(count)]


def select_from_range(video_files, start_percent, end_percent, count):
    """Select videos evenly distributed from a specific percentage range.

    Args:
        video_files: List of (path, size) tuples, sorted by size ascending.
        start_percent: Start of the range (0-100).
        end_percent: End of the range (0-100).
        count: Number of videos to select.

    Returns:
        List of file paths selected from the range (evenly distributed).
    """
    total = len(video_files)
    if total == 0:
        return []

    start_idx = int(total * start_percent / 100)
    end_idx = int(total * end_percent / 100)

    # Ensure valid range
    start_idx = max(0, min(start_idx, total - 1))
    end_idx = max(start_idx + 1, min(end_idx, total))

    range_files = video_files[start_idx:end_idx]
    range_count = len(range_files)

    # Compute indices and select
    indices = compute_indices(range_count, count)
    return [range_files[i][0] for i in indices]


def main():
    if len(sys.argv) < 2:
        print("Usage: python select_videos_by_size.py <input_folder> [output_file]")
        print("Example: python select_videos_by_size.py /path/to/videos selected.txt")
        sys.exit(1)

    input_folder = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "selected_videos.txt"

    try:
        video_files = get_video_files(input_folder)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    total_videos = len(video_files)
    print(f"Found {total_videos} video files in {input_folder}")

    if total_videos == 0:
        print("No video files found.")
        sys.exit(0)

    if total_videos < 15:
        print(f"Warning: Only {total_videos} videos found, need at least 15 for ideal selection.")
        print("Will select as many as possible from each range.")

    # Select from each range (evenly distributed within each range)
    # Bottom 20%: 0-20%
    # Middle 20%: 40-60%
    # Top 20%: 80-100%
    bottom_20 = select_from_range(video_files, 0, 20, 5)
    middle_20 = select_from_range(video_files, 40, 60, 5)
    top_20 = select_from_range(video_files, 80, 100, 5)

    print(f"Selected from bottom 20%: {len(bottom_20)} videos")
    print(f"Selected from middle 20%: {len(middle_20)} videos")
    print(f"Selected from top 20%: {len(top_20)} videos")

    # Combine all selected videos
    all_selected = bottom_20 + middle_20 + top_20

    # Write to output file
    output_path = Path(output_file)
    with open(output_path, 'w', encoding='utf-8') as f:
        for video_path in all_selected:
            f.write(f"{video_path}\n")

    print(f"\nTotal selected: {len(all_selected)} videos")
    print(f"Output written to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
