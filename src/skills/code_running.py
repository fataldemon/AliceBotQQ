import subprocess
import tempfile
import uuid
import os
from pathlib import Path
from typing import Tuple, Optional


class Sandbox:
    """
    安全的代码执行沙盒（基于 Docker 容器）
    支持 Python 和 Bash 代码，资源受限，自动清理
    """

    def __init__(
            self,
            image_python: str = "python:3.11-slim",
            image_bash: str = "bash:5.2",
            memory_limit_mb: int = 256,
            cpu_limit: float = 1.0,
            network_enabled: bool = False,
            timeout_sec: int = 30,
    ):
        self.images = {
            "python": image_python,
            "bash": image_bash,
        }
        self.memory_limit_mb = memory_limit_mb
        self.cpu_limit = cpu_limit
        self.network_enabled = network_enabled
        self.timeout_sec = timeout_sec

        self.container_id = None
        self.temp_dir = None
        self.workdir = None

    def __enter__(self):
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
            "-u", "1000:1000",  # 注意：某些镜像可能没有 1000 用户，会导致容器启动失败
            "-v", f"{self.workdir.absolute()}:/workspace:ro",
            image,
            "sleep", "infinity"
        ]

        # 如果镜像内没有 uid 1000，可以回退到 root（安全性降低）或使用 nobody(65534)
        # 这里简单捕获错误并尝试使用 nobody
        result = subprocess.run(docker_run_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # 尝试使用 nobody 用户 (uid 65534)
            docker_run_cmd[docker_run_cmd.index("-u") + 1] = "65534:65534"
            result = subprocess.run(docker_run_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"启动容器失败: {result.stderr}")

        container_id = result.stdout.strip()
        return container_id

    def _cleanup_container(self):
        if self.container_id:
            subprocess.run(["docker", "rm", "-f", self.container_id],
                           capture_output=True, check=False)
            self.container_id = None

    def _write_code_file(self, language: str, code: str) -> Path:
        filename = "script.py" if language == "python" else "script.sh"
        script_path = self.workdir / filename
        script_path.write_text(code, encoding='utf-8')  # 写入用 UTF-8
        if language == "bash":
            script_path.chmod(0o755)
        return script_path

    def _exec_in_container(self, cmd: list) -> Tuple[str, str, Optional[int]]:
        if not self.container_id:
            raise RuntimeError("容器未启动")
        exec_cmd = ["docker", "exec", self.container_id] + cmd
        try:
            result = subprocess.run(
                exec_cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',  # 输出解码用 UTF-8
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
        # print(code)
        # 2. 启动容器（如果尚未启动）
        if not self.container_id:
            self.container_id = self._start_container(language)

        # 3. 在容器内执行脚本
        if language == "python":
            exec_cmd = ["python", "-u", f"/workspace/{script_path.name}"]
        else:  # bash
            exec_cmd = ["bash", f"/workspace/{script_path.name}"]

        stdout, stderr, exit_code = self._exec_in_container(exec_cmd)
        return stdout, stderr, exit_code


def run_in_sandbox(language: str, code: str, **kwargs) -> Tuple[str, str, Optional[int]]:
    with Sandbox(**kwargs) as sandbox:
        return sandbox.execute(language, code)


if __name__ == "__main__":
    # 示例 1: 执行 Python 代码
    stdout, stderr, exitcode = run_in_sandbox(
        "python",
        "print('Hello from Python')\nimport sys; sys.exit(0)",
        memory_limit_mb=128,
        timeout_sec=5
    )
    print("=== Python ===")
    print(f"stdout: {stdout}")
    print(f"stderr: {stderr}")
    print(f"exitcode: {exitcode}")

    # 示例 2: 执行 Bash 代码（禁止网络）
    stdout, stderr, exitcode = run_in_sandbox(
        "bash",
        "echo 'Hello from Bash'\nls -la /workspace",
        network_enabled=False
    )
    print("\n=== Bash ===")
    print(f"stdout: {stdout}")
    print(f"stderr: {stderr}")
    print(f"exitcode: {exitcode}")

    # 示例 3: 使用显式的 with 块（可多次执行同一容器）
    with Sandbox() as sandbox:
        out1, err1, code1 = sandbox.execute("python", "print(1+1)")
        out2, err2, code2 = sandbox.execute("bash", "echo 'second run'")
        print("\n=== 复用容器 ===")
        print(f"First: {out1.strip()}")
        print(f"Second: {out2.strip()}")