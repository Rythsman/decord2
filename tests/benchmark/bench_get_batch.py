"""Benchmark for get_batch with uniform sampling (real-world scenario)"""
import time
import sys
import os
import argparse
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../python'))
import decord as de

parser = argparse.ArgumentParser("Decord get_batch benchmark")
parser.add_argument('--file', type=str, required=True, help='Test video path')
parser.add_argument('--nframes', type=int, default=32, help='Number of frames to sample')
parser.add_argument('--repeat', type=int, default=5, help='Number of repeats')
parser.add_argument('--width', type=int, default=-1, help='Resize width (-1 for original)')
parser.add_argument('--height', type=int, default=-1, help='Resize height (-1 for original)')

args = parser.parse_args()


def benchmark_get_batch(ctx, ctx_name):
    """Benchmark get_batch with uniform sampling."""
    vr = de.VideoReader(args.file, ctx, width=args.width, height=args.height)
    nframes = len(vr)
    fps = vr.get_avg_fps()

    # Uniform sampling indices (same as your code)
    final_nframes = min(args.nframes, nframes)
    indices = np.linspace(0, nframes - 1, final_nframes).round().astype(int).tolist()

    print(f"\n[{ctx_name}] Video: {nframes} frames @ {fps:.2f} fps, sampling {final_nframes} frames")

    times = []
    for i in range(args.repeat):
        vr.seek(0)
        tic = time.perf_counter()
        frames = vr.get_batch(indices)
        elapsed = time.perf_counter() - tic
        times.append(elapsed)
        print(f"  Run {i+1}: {elapsed:.4f}s")

    avg_time = np.mean(times)
    std_time = np.std(times)
    print(f"  Average: {avg_time:.4f}s ± {std_time:.4f}s")
    print(f"  Throughput: {final_nframes / avg_time:.2f} frames/s")

    return avg_time


if __name__ == "__main__":
    print(f"Testing: {args.file}")
    print(f"Sampling {args.nframes} frames, repeating {args.repeat} times")

    # CPU benchmark
    cpu_time = benchmark_get_batch(de.cpu(), "CPU")

    # GPU benchmark
    try:
        gpu_time = benchmark_get_batch(de.gpu(0), "GPU")
        print(f"\n[Comparison] CPU/GPU ratio: {cpu_time/gpu_time:.2f}x")
        if gpu_time < cpu_time:
            print(f"GPU is {cpu_time/gpu_time:.2f}x faster")
        else:
            print(f"CPU is {gpu_time/cpu_time:.2f}x faster")
    except Exception as e:
        print(f"\n[GPU] Failed: {e}")
