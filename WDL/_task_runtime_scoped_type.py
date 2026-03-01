"""
WDL 1.2 task-scoped runtime info helpers
"""

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING, cast

from . import Type, Value, Expr, Error
from ._util import parse_byte_size

if TYPE_CHECKING:  # pragma: no cover
    from .Tree import Task
    from .runtime import config
    from .runtime.task_container import TaskContainer


class TaskRuntimeScopedType:
    """
    Build task-scoped runtime info types and values used by WDL 1.2+.
    """

    @staticmethod
    def _normalize_task_runtime_info(info: Dict[str, Any]) -> Dict[str, Any]:
        normalized = {}
        for key, value in info.items():
            normalized[key] = value.json if isinstance(value, Value.Base) else value
        return normalized

    @staticmethod
    def build_type(task: "Task") -> Type.StructInstance:
        def meta_object_type(d: Dict[str, Any], name_prefix: str) -> Type.StructInstance:
            meta_json = Expr._meta_value_to_json(d)
            meta_value = Value._infer_from_json(
                meta_json, struct_types=True, struct_prefix=f"__{name_prefix}"
            )
            assert isinstance(meta_value.type, Type.StructInstance)
            return meta_value.type

        meta_ty = meta_object_type(task.meta or {}, "task_meta")
        parameter_meta_ty = meta_object_type(task.parameter_meta or {}, "task_parameter_meta")
        task_ty = Type.StructInstance("__task")
        task_ty.members = {
            "name": Type.String(),
            "id": Type.String(),
            "container": Type.String(optional=True),
            "cpu": Type.Float(),
            "memory": Type.Int(),
            "gpu": Type.Array(Type.String()),
            "fpga": Type.Array(Type.String()),
            "disks": Type.Map((Type.String(), Type.Int())),
            "attempt": Type.Int(),
            "end_time": Type.Int(optional=True),
            "return_code": Type.Int(optional=True),
            "meta": meta_ty,
            "parameter_meta": parameter_meta_ty,
        }
        return task_ty

    @staticmethod
    def build_value(
        cfg: "config.Loader",
        logger: logging.Logger,
        run_id: str,
        task: "Task",
        container: "TaskContainer",
        runtime_eval: Dict[str, Value.Base],
        return_code: Optional[int],
    ) -> Value.Struct:
        task_type = TaskRuntimeScopedType.build_type(task)
        container_overrides = TaskRuntimeScopedType._normalize_task_runtime_info(
            container.task_runtime_info(logger, runtime_eval)
        )

        host_limits = None

        def get_host_limits() -> Dict[str, int]:
            nonlocal host_limits
            if host_limits is None:
                host_limits = container.detect_resource_limits(cfg, logger)
            return host_limits

        def _runtime_string(value: Value.Base) -> str:
            if isinstance(value, Value.Array) and value.value:
                value = value.value[0]
            return value.coerce(Type.String()).value

        if "cpu" in container.runtime_values:
            cpu_value = float(container.runtime_values["cpu"])
        elif "cpu" in runtime_eval:
            cpu_value = runtime_eval["cpu"].coerce(Type.Float()).value
        else:
            cpu_value = float(max(1, get_host_limits().get("cpu", 1)))

        if "memory_reservation" in container.runtime_values:
            memory_value = int(container.runtime_values["memory_reservation"])
        elif "memory" in runtime_eval:
            memory_str = runtime_eval["memory"].coerce(Type.String()).value
            memory_value = parse_byte_size(memory_str)
        else:
            memory_value = int(max(1, get_host_limits().get("mem_bytes", 1)))

        container_value = None
        if "docker" in container.runtime_values:
            container_value = container.runtime_values["docker"]
        elif "container" in runtime_eval:
            container_value = _runtime_string(runtime_eval["container"])
        elif "docker" in runtime_eval:
            container_value = _runtime_string(runtime_eval["docker"])

        task_info = {
            "name": task.name,
            "id": run_id,
            "container": container_value,
            "cpu": cpu_value,
            "memory": memory_value,
            "gpu": [],
            "fpga": [],
            "disks": {},
            # NOTE: attempt is currently not updated for retries, since the command isn't
            # re-interpolated per attempt.
            "attempt": max(0, container.try_counter - 1),
            "end_time": None,
            "return_code": return_code,
            "meta": Expr._meta_value_to_json(task.meta),
            "parameter_meta": Expr._meta_value_to_json(task.parameter_meta),
        }
        task_info.update(container_overrides)
        task_value = Value.from_json(task_type, task_info)
        try:
            task_value.coerce(task_type)
        except Error.InputError as ex:
            raise AssertionError("task-scoped runtime info failed typecheck") from ex
        return cast(Value.Struct, task_value)
