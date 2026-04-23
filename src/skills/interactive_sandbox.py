import subprocess
import threading
import queue
import time
import uuid
from pathlib import Path
from typing import Optional
from src.skills.game_development import WORKSPACE


_sessions = {}
_last_activity = {}          # session_id -> 最后活动时间戳
_CLEANUP_INTERVAL = 60      # 每60秒检查一次
_SESSION_TIMEOUT = 300      # 5分钟无活动则关闭


class InteractiveCodeSandbox:
    """
    运行一段代码（Python或Bash），支持多轮输入，自动回收超时未活动的会话。
    如果设置了 WORKSPACE，会自动挂载到容器的 /workspace 并设为工作目录。
    """

    # 类级别：管理所有实例的最后活动时间和清理线程
    _instances = {}
    _last_activity = {}
    _cleanup_thread_started = False
    _cleanup_interval = 60      # 每60秒检查一次
    _session_timeout = 300      # 5分钟无活动自动关闭

    def __init__(
        self,
        language: str,
        code: str,
        image: str = "python:3.11-slim",
        memory_limit_mb: int = 256,
        cpu_limit: float = 1.0,
        network_enabled: bool = False,
        timeout_sec: int = 60,
        workspace_host_path: Optional[str] = WORKSPACE,   # 使用模块级 WORKSPACE 作为默认值
        workspace_readonly: bool = True,
    ):
        self.language = language
        self.code = code
        self.image = image
        self.memory_limit_mb = memory_limit_mb
        self.cpu_limit = cpu_limit
        self.network_enabled = network_enabled
        self.timeout_sec = timeout_sec
        self.workspace_host_path = Path(workspace_host_path).resolve() if workspace_host_path else None
        self.workspace_readonly = workspace_readonly

        self.process = None
        self.output_queue = queue.Queue()
        self.reader_thread = None
        self._lock = threading.Lock()
        self.start_time = None
        self._id = str(uuid.uuid4())

        # 注册到类字典
        with threading.Lock():
            self._instances[self._id] = self
            self._update_activity()
            self._start_cleanup_thread()

    def _update_activity(self):
        with threading.Lock():
            self._last_activity[self._id] = time.time()

    @classmethod
    def _start_cleanup_thread(cls):
        if cls._cleanup_thread_started:
            return
        cls._cleanup_thread_started = True
        thread = threading.Thread(target=cls._cleanup_loop, daemon=True)
        thread.start()

    @classmethod
    def _cleanup_loop(cls):
        while True:
            time.sleep(cls._cleanup_interval)
            now = time.time()
            to_close = []
            with threading.Lock():
                for sid, last_ts in list(cls._last_activity.items()):
                    if now - last_ts > cls._session_timeout:
                        to_close.append(sid)
            for sid in to_close:
                sandbox = cls._instances.pop(sid, None)
                if sandbox:
                    try:
                        sandbox.close()
                    except:
                        pass
                with threading.Lock():
                    cls._last_activity.pop(sid, None)

    def start(self):
        with self._lock:
            if self.process is not None:
                return
            self._update_activity()

            docker_cmd = [
                "docker", "run", "-i",
                "--rm",
                "--read-only",
                "--network", "none" if not self.network_enabled else "bridge",
                f"--memory={self.memory_limit_mb}m",
                f"--cpus={self.cpu_limit}",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                "-u", "1000:1000",
            ]

            # 挂载工作空间（如果指定）
            if self.workspace_host_path:
                if not self.workspace_host_path.exists():
                    raise FileNotFoundError(f"工作空间路径不存在: {self.workspace_host_path}")
                mount_spec = f"{self.workspace_host_path}:/workspace"
                if self.workspace_readonly:
                    mount_spec += ":ro"
                docker_cmd.extend(["-v", mount_spec])
                docker_cmd.extend(["-w", "/workspace"])   # 设置工作目录

            docker_cmd.append(self.image)

            # 执行代码
            if self.language == "python":
                docker_cmd.extend(["python", "-u", "-c", self.code])
            else:  # bash
                docker_cmd.extend(["bash", "-c", self.code])

            self.process = subprocess.Popen(
                docker_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                bufsize=1,
            )
            self.start_time = time.time()

            self.reader_thread = threading.Thread(target=self._read_output, daemon=True)
            self.reader_thread.start()

    def _read_output(self):
        while True:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                self.output_queue.put(('stdout', line))
            except:
                break
        while True:
            try:
                line = self.process.stderr.readline()
                if not line:
                    break
                self.output_queue.put(('stderr', line))
            except:
                break

    def read_output(self, timeout: float = 0.2) -> str:
        self._update_activity()
        lines = []
        while True:
            try:
                _, line = self.output_queue.get_nowait()
                lines.append(line)
            except queue.Empty:
                break
        return ''.join(lines)

    def wait_for_output(self, timeout: int = 30) -> str:
        self._update_activity()
        start = time.time()
        first_line = None
        while time.time() - start < timeout:
            try:
                _, line = self.output_queue.get(timeout=0.2)
                first_line = line
                break
            except queue.Empty:
                continue
        if first_line is None:
            return ""
        lines = [first_line]
        while True:
            try:
                _, line = self.output_queue.get_nowait()
                lines.append(line)
            except queue.Empty:
                break
        return ''.join(lines)

    def send_input(self, data: str):
        self._update_activity()
        if self.process and self.process.stdin:
            self.process.stdin.write(data + '\n')
            self.process.stdin.flush()

    def is_alive(self):
        if self.process is None:
            return False
        if self.start_time and (time.time() - self.start_time) > self.timeout_sec:
            self.close()
            return False
        return self.process.poll() is None

    def close(self):
        with self._lock:
            if self.process:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                self.process = None
            # 从类字典中移除自己
            with threading.Lock():
                self._instances.pop(self._id, None)
                self._last_activity.pop(self._id, None)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
