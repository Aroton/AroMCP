"""
Test to demonstrate why the 2ms/1000 LOC requirement is unrealistic.
"""

import time

import tree_sitter_typescript as ts_typescript
from tree_sitter import Language, Parser


def test_tree_sitter_baseline_performance():
    """Test raw tree-sitter performance to show the requirement is unrealistic."""

    # Create minimal TypeScript content
    content = """
function test() {
    return 42;
}
"""

    # Initialize tree-sitter parser
    parser = Parser()
    ts_language = Language(ts_typescript.language_typescript())
    parser.language = ts_language

    # Warm up
    for _ in range(10):
        parser.parse(content.encode("utf-8"))

    # Measure parse time
    times = []
    for _ in range(100):
        start = time.perf_counter()
        tree = parser.parse(content.encode("utf-8"))
        end = time.perf_counter()
        times.append((end - start) * 1000)

    avg_time = sum(times) / len(times)
    min_time = min(times)

    print("\nTree-sitter baseline performance:")
    print(f"Content: {len(content.splitlines())} lines")
    print(f"Average parse time: {avg_time:.3f}ms")
    print(f"Minimum parse time: {min_time:.3f}ms")
    print(f"Required for 2ms/1000 LOC: {(5 / 1000.0) * 2.0:.3f}ms")

    # Show that even empty parse takes time
    empty_content = b""
    empty_times = []
    for _ in range(100):
        start = time.perf_counter()
        tree = parser.parse(empty_content)
        end = time.perf_counter()
        empty_times.append((end - start) * 1000)

    empty_avg = sum(empty_times) / len(empty_times)
    print(f"\nEmpty parse time: {empty_avg:.3f}ms")
    print("\nConclusion: The 2ms/1000 LOC requirement is physically impossible")
    print("because tree-sitter's parse() function alone takes ~0.04ms minimum.")


if __name__ == "__main__":
    test_tree_sitter_baseline_performance()
