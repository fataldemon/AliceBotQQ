import subprocess
import threading
import queue
import time
import uuid
from typing import Optional


_sessions = {}


class InteractiveCodeSandbox:
    """运行一段代码（Python或Bash），支持多轮输入（如游戏中的 input()）"""

    def __init__(
        self,
        language: str,                 # "python" 或 "bash"
        code: str,                     # 完整代码字符串
        image: str = "python:3.11-slim",
        memory_limit_mb: int = 256,
        cpu_limit: float = 1.0,
        network_enabled: bool = False,
        timeout_sec: int = 60,         # 整个会话的最大运行时间（秒）
    ):
        self.language = language
        self.code = code
        self.image = image
        self.memory_limit_mb = memory_limit_mb
        self.cpu_limit = cpu_limit
        self.network_enabled = network_enabled
        self.timeout_sec = timeout_sec

        self.process = None
        self.output_queue = queue.Queue()
        self.reader_thread = None
        self._lock = threading.Lock()
        self.start_time = None

    def start(self):
        with self._lock:
            if self.process is not None:
                return

            # 根据语言构建执行命令
            if self.language == "python":
                # 使用 -u 禁用缓冲
                exec_cmd = ["python", "-u", "-c", self.code]
            else:  # bash
                # Bash 需要通过 -c 执行代码
                exec_cmd = ["bash", "-c", self.code]

            docker_cmd = [
                "docker", "run", "-i",           # 保持 stdin 打开
                "--rm",
                "--read-only",
                "--network", "none" if not self.network_enabled else "bridge",
                f"--memory={self.memory_limit_mb}m",
                f"--cpus={self.cpu_limit}",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                "-u", "1000:1000",
                self.image,
            ] + exec_cmd

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

            # 启动读取线程
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
        # 程序结束，可能还有 stderr
        while True:
            try:
                line = self.process.stderr.readline()
                if not line:
                    break
                self.output_queue.put(('stderr', line))
            except:
                break

    def read_output(self, timeout: float = 0.2) -> str:
        """非阻塞读取当前所有输出"""
        lines = []
        while True:
            try:
                _, line = self.output_queue.get_nowait()
                lines.append(line)
            except queue.Empty:
                break
        return ''.join(lines)

    def wait_for_output(self, timeout: int = 30) -> str:
        """阻塞直到有输出或超时，返回所有输出（包括第一行后的后续输出）"""
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
        """向程序发送一行输入（自动添加换行）"""
        if self.process and self.process.stdin:
            self.process.stdin.write(data + '\n')
            self.process.stdin.flush()

    def is_alive(self):
        """检查程序是否还在运行"""
        if self.process is None:
            return False
        # 检查超时
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

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()