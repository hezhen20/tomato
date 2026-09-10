"""单实例进程守卫与窗口激活通信。"""
import hashlib
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QLockFile, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def default_instance_key() -> str:
    """为当前用户生成稳定、无敏感路径内容的本地服务名。"""
    user_scope = str(Path.home().resolve()).casefold().encode("utf-8")
    digest = hashlib.sha256(user_scope).hexdigest()[:16]
    return f"TomatoTimer-{digest}"


class SingleInstance(QObject):
    """使用文件锁判定主实例，并用本地 socket 唤醒已有窗口。"""

    activation_requested = Signal()

    def __init__(self, instance_key: str = None, parent=None):
        super().__init__(parent)
        self.instance_key = instance_key or default_instance_key()
        lock_path = Path(tempfile.gettempdir()) / f"{self.instance_key}.lock"
        self._lock = QLockFile(str(lock_path))
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._handle_new_connection)
        self._owns_lock = False

    def acquire_or_notify(self) -> bool:
        """成为主实例，或通知已经运行的实例并返回 False。"""
        if self._lock.tryLock(0):
            return self._start_server()

        if self._notify_existing():
            return False

        # 崩溃可能留下锁文件；Qt 只会删除确认已失效的锁。
        if self._lock.removeStaleLockFile() and self._lock.tryLock(0):
            return self._start_server()

        # 主实例可能刚拿到锁、服务仍在启动，最后再尝试一次通知。
        self._notify_existing(connect_timeout_ms=800)
        return False

    def close(self):
        self._server.close()
        if self._owns_lock:
            self._lock.unlock()
            self._owns_lock = False

    def _start_server(self) -> bool:
        self._owns_lock = True
        QLocalServer.removeServer(self.instance_key)
        if self._server.listen(self.instance_key):
            return True

        self.close()
        raise RuntimeError(f"无法创建单实例通信服务: {self._server.errorString()}")

    def _notify_existing(self, connect_timeout_ms: int = 300) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self.instance_key)
        if not socket.waitForConnected(connect_timeout_ms):
            socket.abort()
            return False

        socket.write(b"activate")
        socket.flush()
        socket.waitForBytesWritten(connect_timeout_ms)
        socket.disconnectFromServer()
        return True

    def _handle_new_connection(self):
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is not None:
                socket.disconnectFromServer()
                socket.deleteLater()
            self.activation_requested.emit()
