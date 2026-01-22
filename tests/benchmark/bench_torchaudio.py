"""Benchmark for torchaudio StreamReader: CPU vs CUDA decoding"""
import time
import argparse
import torch
import torchaudio
from torchaudio.io import StreamReader

parser = argparse.ArgumentParser("TorchAudio StreamReader benchmark")
parser.add_argument('--file', type=str, required=True, help='Test video path')
parser.add_argument('--chunk-size', type=int, default=5, help='Frames per chunk')
parser.add_argument('--repeat', type=int, default=3, help='Number of repeats')
parser.add_argument('--gpu', type=int, default=0, help='GPU device id')

args = parser.parse_args()


def benchmark_stream(src, config, name):
    """Benchmark StreamReader with given config."""
    times = []

    for run in range(args.repeat):
        s = StreamReader(src)
        s.add_video_stream(args.chunk_size, **config)

        t0 = time.perf_counter()
        num_frames = 0
        for i, (chunk,) in enumerate(s.stream()):
            num_frames += chunk.shape[0]
        elapsed = time.perf_counter() - t0
        times.append(elapsed)

        if run == 0:
            print(f"[{name}] Frames: {num_frames}, Chunk shape: {chunk.shape}")

        print(f"  Run {run+1}: {elapsed:.4f}s ({num_frames/elapsed:.2f} fps)")

    avg = sum(times) / len(times)
    print(f"  Average: {avg:.4f}s ({num_frames/avg:.2f} fps)\n")
    return avg, num_frames


if __name__ == "__main__":
    print(f"PyTorch: {torch.__version__}")
    print(f"TorchAudio: {torchaudio.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    print(f"Video: {args.file}\n")

    # CPU config
    cpu_conf = {"decoder": "h264"}

    # CUDA config
    cuda_conf = {
        "decoder": "h264_cuvid",
        "hw_accel": f"cuda:{args.gpu}",
    }

    # CPU benchmark
    print("=" * 50)
    print("CPU Decoding (h264)")
    print("=" * 50)
    cpu_time, num_frames = benchmark_stream(args.file, cpu_conf, "CPU")

    # GPU benchmark
    print("=" * 50)
    print(f"CUDA Decoding (h264_cuvid, cuda:{args.gpu})")
    print("=" * 50)
    try:
        cuda_time, _ = benchmark_stream(args.file, cuda_conf, "CUDA")

        print("=" * 50)
        print("Summary")
        print("=" * 50)
        print(f"  CPU:  {cpu_time:.4f}s ({num_frames/cpu_time:.2f} fps)")
        print(f"  CUDA: {cuda_time:.4f}s ({num_frames/cuda_time:.2f} fps)")
        if cuda_time < cpu_time:
            print(f"  CUDA is {cpu_time/cuda_time:.2f}x faster")
        else:
            print(f"  CPU is {cuda_time/cpu_time:.2f}x faster")
    except Exception as e:
        print(f"CUDA decoding failed: {e}")
        print("Make sure h264_cuvid decoder is available in your FFmpeg build.")
