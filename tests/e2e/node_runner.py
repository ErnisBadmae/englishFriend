"""Node Runner Framework for E2E Business Logic Tests.

Executes tests sequentially by nodes with pretty reporting.
When a node fails, subsequent dependent nodes are marked as SKIPPED.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional


def _setup_console_encoding():
    """Setup console for UTF-8 output on Windows."""
    if sys.platform == "win32":
        try:
            # Try to set console to UTF-8
            os.system("chcp 65001 > nul 2>&1")
            # Reconfigure stdout for UTF-8
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


# Setup encoding at module import
_setup_console_encoding()


class NodeStatus(Enum):
    """Status of a test node."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class NodeResult:
    """Result of a single node test."""
    name: str
    status: NodeStatus
    duration_ms: float = 0.0
    error: Optional[str] = None
    error_details: Optional[str] = None
    data: dict = field(default_factory=dict)


@dataclass
class TestNode:
    """Definition of a test node."""
    name: str
    test_func: Callable[..., Coroutine[Any, Any, dict]]
    depends_on: list[str] = field(default_factory=list)
    description: str = ""
    skip_on_dependency_fail: bool = True


class NodeRunner:
    """Runner for sequential node-based tests."""

    # ANSI color codes
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    # Symbols (with ASCII fallbacks)
    SYM_PASS = "+"   # Was: ✓
    SYM_FAIL = "X"   # Was: ✗
    SYM_SKIP = "o"   # Was: ○
    SYM_RUN = ">"    # Was: ►

    def __init__(self, title: str = "BUSINESS FLOW TEST"):
        self.title = title
        self.nodes: list[TestNode] = []
        self.results: list[NodeResult] = []
        self.context: dict[str, Any] = {}
        self._failed_nodes: set[str] = set()

    def add_node(
        self,
        name: str,
        test_func: Callable[..., Coroutine[Any, Any, dict]],
        depends_on: Optional[list[str]] = None,
        description: str = "",
        skip_on_dependency_fail: bool = True,
    ) -> None:
        """Add a test node to the runner."""
        self.nodes.append(TestNode(
            name=name,
            test_func=test_func,
            depends_on=depends_on or [],
            description=description,
            skip_on_dependency_fail=skip_on_dependency_fail,
        ))

    def _should_skip(self, node: TestNode) -> tuple[bool, Optional[str]]:
        """Check if node should be skipped due to failed dependencies."""
        if not node.skip_on_dependency_fail:
            return False, None

        for dep in node.depends_on:
            if dep in self._failed_nodes:
                return True, dep

        return False, None

    async def _run_node(self, node: TestNode, index: int) -> NodeResult:
        """Execute a single test node."""
        total = len(self.nodes)

        # Check dependencies
        should_skip, failed_dep = self._should_skip(node)
        if should_skip:
            return NodeResult(
                name=node.name,
                status=NodeStatus.SKIPPED,
                error=f"dependency failed: {failed_dep}",
            )

        # Run the test
        start_time = time.perf_counter()
        try:
            result_data = await node.test_func(self.context)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Update context with result data
            self.context.update(result_data)

            return NodeResult(
                name=node.name,
                status=NodeStatus.PASSED,
                duration_ms=duration_ms,
                data=result_data,
            )

        except AssertionError as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._failed_nodes.add(node.name)
            return NodeResult(
                name=node.name,
                status=NodeStatus.FAILED,
                duration_ms=duration_ms,
                error=str(e) or "Assertion failed",
                error_details=traceback.format_exc(),
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._failed_nodes.add(node.name)
            return NodeResult(
                name=node.name,
                status=NodeStatus.FAILED,
                duration_ms=duration_ms,
                error=f"{type(e).__name__}: {str(e)}",
                error_details=traceback.format_exc(),
            )

    async def run(self) -> list[NodeResult]:
        """Run all test nodes sequentially."""
        self.results = []
        self._failed_nodes = set()
        self.context = {}

        for i, node in enumerate(self.nodes):
            result = await self._run_node(node, i)
            self.results.append(result)

        return self.results

    def _status_symbol(self, status: NodeStatus) -> str:
        """Get symbol for status."""
        if status == NodeStatus.PASSED:
            return f"{self.GREEN}{self.SYM_PASS}{self.RESET}"
        elif status == NodeStatus.FAILED:
            return f"{self.RED}{self.SYM_FAIL}{self.RESET}"
        elif status == NodeStatus.SKIPPED:
            return f"{self.YELLOW}{self.SYM_SKIP}{self.RESET}"
        elif status == NodeStatus.RUNNING:
            return f"{self.CYAN}{self.SYM_RUN}{self.RESET}"
        return " "

    def _status_text(self, status: NodeStatus) -> str:
        """Get colored status text."""
        if status == NodeStatus.PASSED:
            return f"{self.GREEN}PASSED{self.RESET}"
        elif status == NodeStatus.FAILED:
            return f"{self.RED}FAILED{self.RESET}"
        elif status == NodeStatus.SKIPPED:
            return f"{self.YELLOW}SKIPPED{self.RESET}"
        return status.value.upper()

    def print_report(self) -> None:
        """Print formatted test report."""
        line_width = 60
        separator = "=" * line_width
        thin_sep = "-" * line_width

        print()
        print(separator)
        print(f"{self.BOLD}{self.title} REPORT{self.RESET}".center(line_width + 10))
        print(separator)

        total = len(self.results)
        for i, result in enumerate(self.results, 1):
            symbol = self._status_symbol(result.status)
            status = self._status_text(result.status)

            # Format timing
            if result.duration_ms > 0:
                timing = f"({result.duration_ms:.2f}ms)"
            else:
                timing = ""

            # Main line
            node_text = f"  [{i}/{total}] {result.name}"
            status_timing = f"{status} {timing}"
            padding = line_width - len(node_text) - len(status_timing) + 20  # account for ANSI
            print(f"{node_text}{' ' * max(1, padding)}{symbol} {status_timing}")

            # Error details if failed
            if result.status == NodeStatus.FAILED and result.error:
                print(f"        → Error: {result.error}")

            # Skip reason if skipped
            if result.status == NodeStatus.SKIPPED and result.error:
                print(f"        → {result.error}")

        print(thin_sep)

        # Summary
        passed = sum(1 for r in self.results if r.status == NodeStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == NodeStatus.FAILED)
        skipped = sum(1 for r in self.results if r.status == NodeStatus.SKIPPED)

        summary_parts = []
        summary_parts.append(f"Total: {total}")
        summary_parts.append(f"{self.GREEN}Passed: {passed}{self.RESET}")
        if failed > 0:
            summary_parts.append(f"{self.RED}Failed: {failed}{self.RESET}")
        if skipped > 0:
            summary_parts.append(f"{self.YELLOW}Skipped: {skipped}{self.RESET}")

        print(" | ".join(summary_parts))
        print(separator)
        print()

    def get_summary(self) -> dict:
        """Get test summary as dict."""
        passed = sum(1 for r in self.results if r.status == NodeStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == NodeStatus.FAILED)
        skipped = sum(1 for r in self.results if r.status == NodeStatus.SKIPPED)

        return {
            "total": len(self.results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "success": failed == 0,
        }


def run_e2e_tests(runner: NodeRunner) -> int:
    """Run E2E tests and return exit code."""
    asyncio.run(runner.run())
    runner.print_report()
    summary = runner.get_summary()
    return 0 if summary["success"] else 1
