import asyncio
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Tuple, Optional, Union

from src.skills.game_development import WORKSPACE


class Sandbox:
    """
    安全的代码执行沙盒（基于 Docker 容器）
    支持 Python 和 Bash 代码，资源受限，自动清理。
    可额外挂载一个固定的宿主机工作空间，使容器内的代码能访问该空间的所有文件。
    """

    def __init__(
            self,
            image_python: str = "python:3.11-slim",
            image_bash: str = "python:3.11-slim",
            memory_limit_mb: int = 256,
            cpu_limit: float = 1.0,
            network_enabled: bool = False,
            timeout_sec: int = 30,
            workspace_host_path: Optional[Union[str, Path]] = None,  # 新增：宿主机工作空间路径
            workspace_readonly: bool = True,  # 工作空间是否只读挂载
    ):
        self.images = {
            "python": image_python,
            "bash": image_bash,
        }
        self.memory_limit_mb = memory_limit_mb
        self.cpu_limit = cpu_limit
        self.network_enabled = network_enabled
        self.timeout_sec = timeout_sec
        self.workspace_readonly = workspace_readonly

        # 处理工作空间路径
        if workspace_host_path:
            self.workspace_path = Path(workspace_host_path).resolve()
            if not self.workspace_path.exists():
                raise FileNotFoundError(f"工作空间路径不存在: {self.workspace_path}")
        else:
            self.workspace_path = None

        self.container_id = None
        self.temp_dir = None  # 用于存放动态生成的代码文件（位于工作空间内或系统临时目录）
        self.workdir = None  # 容器内代码文件所在的目录（在容器中的路径）

    def __enter__(self):
        if self.workspace_path:
            # 在工作空间内部创建一个临时子目录（前缀 .sandbox_），用于存放本次执行的代码文件
            # 这样代码文件位于工作空间内，但执行完会被自动删除
            self.temp_dir = tempfile.TemporaryDirectory(
                dir=self.workspace_path,
                prefix=".sandbox_"
            )
            self.workdir = Path(self.temp_dir.name)  # 宿主机上的临时目录路径
        else:
            # 原有模式：创建完全独立的临时工作目录
            self.temp_dir = tempfile.TemporaryDirectory()
            self.workdir = Path(self.temp_dir.name) / "workspace"
            self.workdir.mkdir()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup_container()
        if self.temp_dir:
            self.temp_dir.cleanup()

    def _start_container(self, language: str) -> str:
        """启动一个后台运行的容器（保持存活），返回容器 ID"""
        image = self.images[language]
        container_name = f"sandbox-{uuid.uuid4().hex[:12]}"

        docker_run_cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--read-only",
            "--network", "none" if not self.network_enabled else "bridge",
            f"--memory={self.memory_limit_mb}m",
            f"--cpus={self.cpu_limit}",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "-u", "1000:1000",  # 若失败会回退到 nobody
        ]

        # ---------- 挂载卷配置 ----------
        if self.workspace_path:
            # 挂载整个工作空间到容器的 /workspace
            mount_spec = f"{self.workspace_path}:/workspace"
            if self.workspace_readonly:
                mount_spec += ":ro"
            docker_run_cmd.extend(["-v", mount_spec])
            # 注意：代码文件所在的 self.workdir 是 workspace 的子目录，因此无需额外挂载
            # 容器内代码文件路径为：/workspace/{临时子目录名}/script.py
        else:
            # 原有模式：挂载临时目录到 /workspace（只读）
            docker_run_cmd.extend(["-v", f"{self.workdir.absolute()}:/workspace:ro"])

        docker_run_cmd.extend([
            image,
            "sleep", "infinity"
        ])

        # 处理用户权限问题（回退到 nobody 或 root）
        result = subprocess.run(docker_run_cmd, capture_output=True, text=True, encoding='utf-8')
        if result.returncode != 0:
            # 尝试使用 nobody 用户 (uid 65534)
            idx = docker_run_cmd.index("-u") if "-u" in docker_run_cmd else -1
            if idx != -1:
                docker_run_cmd[idx + 1] = "65534:65534"
                result = subprocess.run(docker_run_cmd, capture_output=True, text=True, encoding='utf-8')
                if result.returncode != 0:
                    raise RuntimeError(f"启动容器失败: {result.stderr}")
            else:
                raise RuntimeError(f"启动容器失败: {result.stderr}")

        container_id = result.stdout.strip()
        return container_id

    def _cleanup_container(self):
        if self.container_id:
            subprocess.run(["docker", "rm", "-f", self.container_id],
                           capture_output=True, check=False)
            self.container_id = None

    def _write_code_file(self, language: str, code: str) -> Path:
        """将代码写入临时文件（位于工作空间内部或独立临时目录）"""
        filename = "script.py" if language == "python" else "script.sh"
        script_path = self.workdir / filename
        script_path.write_text(code, encoding='utf-8')
        if language == "bash":
            script_path.chmod(0o755)
        return script_path

    def _exec_in_container(self, cmd: list) -> Tuple[str, str, Optional[int]]:
        if not self.container_id:
            raise RuntimeError("容器未启动，请先调用 _start_container")
        exec_cmd = ["docker", "exec", self.container_id] + cmd
        try:
            result = subprocess.run(
                exec_cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=self.timeout_sec,
                check=False
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", f"Execution exceeded timeout ({self.timeout_sec}s)", None

    def execute(self, language: str, code: str) -> Tuple[str, str, Optional[int]]:
        if language not in ("python", "bash"):
            raise ValueError("language 必须是 'python' 或 'bash'")

        # 1. 写入代码文件
        script_path = self._write_code_file(language, code)

        # 2. 启动容器（如果尚未启动）
        if not self.container_id:
            self.container_id = self._start_container(language)

        # 3. 构造容器内执行命令
        # 容器内代码文件的路径：
        if self.workspace_path:
            # 工作空间模式：代码文件位于 /workspace/{临时子目录名}/script.py
            container_script_path = f"/workspace/{script_path.parent.name}/{script_path.name}"
        else:
            # 原有模式：代码文件位于 /workspace/script.py
            container_script_path = f"/workspace/{script_path.name}"

        if language == "python":
            exec_cmd = ["python", "-u", container_script_path]
        else:  # bash
            exec_cmd = ["bash", container_script_path]

        stdout, stderr, exit_code = self._exec_in_container(exec_cmd)
        return stdout, stderr, exit_code


def run_in_sandbox(
        language: str,
        code: str,
        workspace_path: Optional[Union[str, Path]] = WORKSPACE,
        workspace_readonly: bool = True,
        **kwargs
) -> Tuple[str, str, Optional[int]]:
    """
    便捷函数：在沙盒中执行代码，可挂载固定的宿主机工作空间。

    参数:
        language: "python" 或 "bash"
        code: 要执行的代码字符串
        workspace_path: 宿主机工作空间路径，挂载后容器内可通过 /workspace 访问其中所有文件
        workspace_readonly: 工作空间是否只读挂载（默认 True，安全）
        **kwargs: 其他 Sandbox 参数 (memory_limit_mb, cpu_limit, network_enabled, timeout_sec)
    """
    with Sandbox(workspace_host_path=workspace_path, workspace_readonly=workspace_readonly, **kwargs) as sandbox:
        return sandbox.execute(language, code)

