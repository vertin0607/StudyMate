"""在本机把 users.id=1 初始化为正式账号，并删除 users.id=2。

在 backend 目录执行：

    python -m app.scripts.initialize_owner

命令会读取当前配置的数据库。不要设置 DATABASE_PATH 指向测试库。
正式用户名必须输入「夜临」。密码只通过交互式输入读取，不会写入参数或输出。
id=2 的业务数据会被删除，不会并入 id=1。
"""

import getpass
import os
import sys

from app.config import settings
from app.services.owner_init import TARGET_USERNAME, OwnerInitError, initialize_owner, preview_owner_init


def main(argv: list[str] | None = None) -> int:
    if argv:
        print("这个命令不接收账号或密码参数。")
        return 1
    path = settings.database_path
    print(f"数据库：{path}")
    if path.name == "_test_studymate.db":
        print("当前配置指向自动测试数据库，已停止。")
        return 1
    if not path.is_file():
        print("没有找到数据库文件，已停止。")
        return 1

    username = input("正式用户名：").strip()
    if username != TARGET_USERNAME:
        print("正式用户名需要是夜临，已停止。")
        return 1
    email = input("邮箱（可直接回车跳过）：")
    nickname = input("昵称：")
    password = _read_secret("密码：")
    confirm_password = _read_secret("确认密码：")
    if password != confirm_password:
        print("两次输入的密码不一致，已停止。")
        return 1

    try:
        preview = preview_owner_init(path)
    except OwnerInitError as exc:
        print(str(exc))
        return 1

    print("即将保留 users.id=1，并把用户名改为夜临。")
    print(f"邮箱：{email.strip() or '（不设置）'}")
    print(f"昵称：{nickname.strip() or TARGET_USERNAME}")
    print(f"创建时间保持为 {preview.created_at}。")
    print("将删除 users.id=2 及其关联数据。这些数据不会并入 id=1。")
    visible = {name: len(rows) for name, rows in preview.removed.items() if rows}
    if visible:
        for name, count in visible.items():
            print(f"  {name}: {count}")
    else:
        print("  id=2 没有关联业务数据。")
    print("密码不会显示，也不会写入报告。")
    if input("输入 YES 继续：").strip() != "YES":
        print("已取消，数据库没有修改。")
        return 1

    try:
        result = initialize_owner(
            path,
            username=username,
            email=email,
            nickname=nickname,
            password=password,
            confirm_password=confirm_password,
        )
    except OwnerInitError as exc:
        print(str(exc))
        return 1
    except Exception:
        print("初始化失败，修改已回滚。")
        return 1

    print(f"初始化完成。用户 id={result.user_id}，用户名={result.username}。")
    print(f"创建时间保持为 {result.created_at}。")
    print(f"备份：{result.backup_path}")
    return 0


def _read_secret(prompt: str) -> str:
    """读取密码且不回显。Windows 不把中文提示交给 getpass，避免 PowerShell 里直接失败。"""
    if os.name == "nt" and sys.stdin.isatty() and getattr(getpass.getpass, "__module__", None) == "getpass":
        try:
            return _windows_console_secret(prompt)
        except OSError:
            print()
            print("无法读取密码。请在 PowerShell 窗口中直接运行这条命令后重试。")
            raise SystemExit(1) from None
    print(prompt, end="", flush=True)
    return getpass.getpass("")


def _windows_console_secret(prompt: str) -> str:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel32.GetStdHandle.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.ReadConsoleW.argtypes = [
        wintypes.HANDLE,
        ctypes.c_wchar_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    handle = kernel32.GetStdHandle(wintypes.DWORD(-10))
    invalid = ctypes.c_void_p(-1).value
    owns_handle = False
    mode = wintypes.DWORD()
    if not handle or handle == invalid or not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        handle = kernel32.CreateFileW(
            "CONIN$",
            0x80000000 | 0x40000000,
            0x00000001 | 0x00000002,
            None,
            3,
            0,
            None,
        )
        owns_handle = True
        if not handle or handle == invalid or not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            if owns_handle and handle and handle != invalid:
                kernel32.CloseHandle(handle)
            raise OSError("控制台输入不可用")

    enable_line_input = 0x0002
    enable_echo_input = 0x0004
    enable_processed_input = 0x0001
    hidden = (mode.value | enable_line_input | enable_processed_input) & ~enable_echo_input
    if not kernel32.SetConsoleMode(handle, hidden):
        if owns_handle:
            kernel32.CloseHandle(handle)
        raise OSError("无法关闭密码回显")
    try:
        print(prompt, end="", flush=True)
        buffer = ctypes.create_unicode_buffer(1025)
        read = wintypes.DWORD()
        if not kernel32.ReadConsoleW(handle, buffer, 1024, ctypes.byref(read), None):
            raise OSError("读取密码失败")
        print()
        return buffer.value.replace("\r", "").replace("\n", "")
    finally:
        kernel32.SetConsoleMode(handle, mode.value)
        if owns_handle:
            kernel32.CloseHandle(handle)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
