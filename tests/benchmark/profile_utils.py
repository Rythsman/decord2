"""PyTorch Profiler Wrapper for easy timeline profiling."""
import os
import gzip
import functools
from contextlib import contextmanager
from typing import Optional, Callable, Any

import torch
from torch.profiler import profile, ProfilerActivity, schedule, tensorboard_trace_handler


def export_chrome_trace_gzip(prof, path: str):
    """Export Chrome trace as gzip compressed JSON.

    Chrome's chrome://tracing can directly load .json.gz files.

    Args:
        prof: PyTorch profiler object
        path: Output path (should end with .json.gz)
    """
    # Get the trace as string
    if not path.endswith('.gz'):
        path = path + '.gz'

    # Export to a temporary string first, then compress
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=True) as tmp:
        tmp_path = tmp.name

    # Export to temp file
    prof.export_chrome_trace(tmp_path)

    # Read and compress
    with open(tmp_path, 'rb') as f_in:
        with gzip.open(path, 'wb', compresslevel=6) as f_out:
            f_out.writelines(f_in)

    # Clean up temp file
    os.remove(tmp_path)

    return path


def profile_function(
    func: Optional[Callable] = None,
    *,
    output_dir: str = "./profiler_output",
    trace_name: Optional[str] = None,
    activities: Optional[list] = None,
    with_stack: bool = True,
    with_shapes: bool = True,
    with_flops: bool = False,
    record_shapes: bool = True,
    profile_memory: bool = True,
    warmup: int = 1,
    active: int = 3,
    repeat: int = 1,
    export_chrome_trace: bool = True,
    export_stacks: bool = False,
    use_gzip: bool = True,
):
    """
    Decorator to profile a function and export timeline.

    Usage:
        @profile_function(output_dir="./my_profile")
        def my_func():
            ...

        # Or with more options
        @profile_function(warmup=2, active=5, with_flops=True)
        def my_func():
            ...

    Args:
        output_dir: Directory to save profiler output
        trace_name: Name for the trace file (default: function name)
        activities: List of activities to profile (default: CPU + CUDA)
        with_stack: Record Python call stack
        with_shapes: Record tensor shapes
        with_flops: Estimate FLOPs (requires with_shapes=True)
        record_shapes: Record input shapes
        profile_memory: Profile memory usage
        warmup: Number of warmup iterations
        active: Number of active profiling iterations
        repeat: Number of profiling cycles
        export_chrome_trace: Export Chrome trace JSON
        export_stacks: Export flame graph stacks
        use_gzip: Compress trace file with gzip (default: True)
    """
    if activities is None:
        activities = [ProfilerActivity.CPU]
        if torch.cuda.is_available():
            activities.append(ProfilerActivity.CUDA)

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> Any:
            name = trace_name or fn.__name__
            os.makedirs(output_dir, exist_ok=True)

            result = None
            with profile(
                activities=activities,
                schedule=schedule(
                    wait=0,
                    warmup=warmup,
                    active=active,
                    repeat=repeat,
                ),
                on_trace_ready=tensorboard_trace_handler(output_dir),
                record_shapes=record_shapes,
                profile_memory=profile_memory,
                with_stack=with_stack,
                with_flops=with_flops,
            ) as prof:
                for _ in range(warmup + active * repeat):
                    result = fn(*args, **kwargs)
                    prof.step()

            # Export Chrome trace
            if export_chrome_trace:
                if use_gzip:
                    trace_path = os.path.join(output_dir, f"{name}_trace.json.gz")
                    export_chrome_trace_gzip(prof, trace_path)
                else:
                    trace_path = os.path.join(output_dir, f"{name}_trace.json")
                    prof.export_chrome_trace(trace_path)
                print(f"Chrome trace saved to: {trace_path}")

            # Export stacks for flame graph
            if export_stacks:
                stack_path = os.path.join(output_dir, f"{name}_stacks.txt")
                prof.export_stacks(stack_path, "self_cuda_time_total")
                print(f"Stacks saved to: {stack_path}")

            # Print summary
            print(f"\n{'='*60}")
            print(f"Profile Summary: {name}")
            print('='*60)
            print(prof.key_averages().table(
                sort_by="cuda_time_total" if torch.cuda.is_available() else "cpu_time_total",
                row_limit=20
            ))

            return result
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


@contextmanager
def profile_context(
    name: str = "profile",
    output_dir: str = "./profiler_output",
    activities: Optional[list] = None,
    with_stack: bool = True,
    profile_memory: bool = True,
    export_chrome_trace: bool = True,
    use_gzip: bool = True,
):
    """
    Context manager for profiling a code block.

    Usage:
        with profile_context("my_operation", output_dir="./profiles"):
            # code to profile
            result = some_function()
            model(input)

    Args:
        name: Name for the trace file
        output_dir: Directory to save profiler output
        activities: List of activities to profile
        with_stack: Record Python call stack
        profile_memory: Profile memory usage
        export_chrome_trace: Export Chrome trace JSON
        use_gzip: Compress trace file with gzip (default: True)
    """
    if activities is None:
        activities = [ProfilerActivity.CPU]
        if torch.cuda.is_available():
            activities.append(ProfilerActivity.CUDA)

    os.makedirs(output_dir, exist_ok=True)

    with profile(
        activities=activities,
        record_shapes=True,
        profile_memory=profile_memory,
        with_stack=with_stack,
    ) as prof:
        yield prof

    # Export Chrome trace
    if export_chrome_trace:
        if use_gzip:
            trace_path = os.path.join(output_dir, f"{name}_trace.json.gz")
            export_chrome_trace_gzip(prof, trace_path)
        else:
            trace_path = os.path.join(output_dir, f"{name}_trace.json")
            prof.export_chrome_trace(trace_path)
        print(f"Chrome trace saved to: {trace_path}")

    # Print summary
    print(f"\n{'='*60}")
    print(f"Profile Summary: {name}")
    print('='*60)
    print(prof.key_averages().table(
        sort_by="cuda_time_total" if torch.cuda.is_available() else "cpu_time_total",
        row_limit=20
    ))


def profile_once(
    fn: Callable,
    *args,
    name: Optional[str] = None,
    output_dir: str = "./profiler_output",
    **kwargs
) -> Any:
    """
    Profile a single function call.

    Usage:
        result = profile_once(my_func, arg1, arg2, name="my_func_profile")

    Args:
        fn: Function to profile
        *args: Positional arguments for the function
        name: Name for the trace file (default: function name)
        output_dir: Directory to save profiler output
        **kwargs: Keyword arguments for the function

    Returns:
        The return value of the profiled function
    """
    name = name or fn.__name__

    with profile_context(name, output_dir):
        result = fn(*args, **kwargs)

    return result


# Example usage
if __name__ == "__main__":
    import time

    # Example 1: Using decorator
    @profile_function(output_dir="./test_profile", warmup=1, active=2)
    def example_matmul():
        a = torch.randn(1000, 1000)
        b = torch.randn(1000, 1000)
        if torch.cuda.is_available():
            a, b = a.cuda(), b.cuda()
        c = torch.matmul(a, b)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        return c

    # Example 2: Using context manager
    def example_with_context():
        with profile_context("custom_block", output_dir="./test_profile"):
            a = torch.randn(500, 500)
            if torch.cuda.is_available():
                a = a.cuda()
            for _ in range(10):
                a = torch.matmul(a, a)
            if torch.cuda.is_available():
                torch.cuda.synchronize()

    # Example 3: Using profile_once
    def some_computation(size):
        x = torch.randn(size, size)
        if torch.cuda.is_available():
            x = x.cuda()
        return torch.svd(x)

    print("Running profiling examples...")
    print("\n1. Decorator example:")
    example_matmul()

    print("\n2. Context manager example:")
    example_with_context()

    print("\n3. Profile once example:")
    profile_once(some_computation, 200, name="svd_computation", output_dir="./test_profile")

    print("\nDone! Check ./test_profile for trace files.")
    print("View traces in Chrome: chrome://tracing")
    print("Or use TensorBoard: tensorboard --logdir=./test_profile")
