"""Process adapter for executing a validated single-VM QEMU LaunchPlan."""
from __future__ import annotations

import os
from typing import Mapping, NoReturn

from boot_provider import ContractError, LaunchPlan


class QemuRuntimeError(RuntimeError):
    """A LaunchPlan cannot be started by this runtime adapter."""


def exec_launch_plan(plan: LaunchPlan, environment: Mapping[str, str] | None = None) -> NoReturn:
    """Replace the current process with the exact argv from a QEMU LaunchPlan.

    Using exec preserves QEMU's exit status and signal behavior and never
    interprets argv through a shell. The caller remains responsible for
    constructing a trusted plan with the appropriate provider.
    """
    if not isinstance(plan, LaunchPlan):
        raise ContractError("QEMU runtime requires a validated LaunchPlan")
    if plan.runtime_adapter != "qemu-process":
        raise ContractError("LaunchPlan does not target the qemu-process runtime")
    env = None if environment is None else dict(environment)
    try:
        os.execvpe(plan.qemu_argv[0], plan.qemu_argv, env)
    except OSError as error:
        raise QemuRuntimeError(f"cannot execute QEMU from LaunchPlan: {error}") from error
