"""
Puente PTY <-> WebSocket asíncrono para sesiones interactivas reales dentro de Podman.
Permite usar vim, nano, top, autocompletado Tab, Ctrl+C y redimensionado SIGWINCH.
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pty
import signal
import struct
import subprocess
import termios
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from .runtime import RUNTIME


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    rows = max(10, min(rows, 200))
    cols = max(30, min(cols, 400))
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def build_exec_cmd(node_info: dict[str, Any], ps1: str, exec_args: list[str]) -> list[str]:
    """Comando `exec` de la terminal del jugador; abre en `workdir` si el nodo lo declara."""
    cmd = [RUNTIME, "exec", "-it", "--user", node_info.get("default_user", "root")]
    if node_info.get("workdir"):
        cmd.extend(["-w", node_info["workdir"]])
    cmd.extend([
        "-e", "TERM=xterm-256color",
        "-e", "COLORTERM=truecolor",
        "-e", f"PS1={ps1}",
        node_info["container"],
        *exec_args,
    ])
    return cmd


async def stream_container_pty(
    websocket: WebSocket,
    node_info: dict[str, Any],
    on_command_line=None,
) -> None:
    await websocket.accept()

    container = node_info["container"]
    role = node_info["role"]
    shell = node_info.get("shell", "/bin/sh")
    user = node_info.get("default_user", "root")

    master_fd, slave_fd = pty.openpty()
    _set_winsize(master_fd, 28, 110)

    # Configurar prompt limpio e informativo
    if "bash" in shell:
        ps1 = f"\\[\\e[1;36m\\][chaos:{role}]\\[\\e[0m\\] \\[\\e[1;33m\\]\\u\\w\\[\\e[0m\\]# "
        exec_args = [shell, "--rcfile", "/etc/bash.bashrc", "-i"]
    else:
        ps1 = f"[chaos:{role}] \\w # "
        exec_args = [shell, "-i"]

    cmd = build_exec_cmd(node_info, ps1, exec_args)

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid,
            close_fds=True,
        )
    except Exception as exc:
        os.close(master_fd)
        os.close(slave_fd)
        await websocket.send_text(
            json.dumps({"type": "output", "data": f"\r\n\x1b[31mError abriendo PTY: {exc}\x1b[0m\r\n"})
        )
        await websocket.close()
        return

    os.close(slave_fd)
    os.set_blocking(master_fd, False)

    loop = asyncio.get_running_loop()
    out_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    def _on_master_readable() -> None:
        try:
            data = os.read(master_fd, 8192)
            if not data:
                loop.remove_reader(master_fd)
                out_queue.put_nowait(None)
            else:
                out_queue.put_nowait(data)
        except BlockingIOError:
            pass
        except OSError:
            try:
                loop.remove_reader(master_fd)
            except Exception:
                pass
            out_queue.put_nowait(None)

    loop.add_reader(master_fd, _on_master_readable)

    async def _pty_to_ws() -> None:
        banner = (
            f"\x1b[1;38;5;45m⚡ Conectado a nodo \x1b[1;97m{role}\x1b[1;38;5;45m "
            f"({node_info.get('ip', 'local')}) · imagen {node_info.get('image', '')}\x1b[0m\r\n"
        )
        await websocket.send_text(json.dumps({"type": "output", "data": banner}))
        while True:
            chunk = await out_queue.get()
            if chunk is None:
                await websocket.send_text(
                    json.dumps({"type": "output", "data": "\r\n\x1b[33m[Sesión de terminal finalizada]\x1b[0m\r\n"})
                )
                break
            text = chunk.decode("utf-8", errors="replace")
            await websocket.send_text(json.dumps({"type": "output", "data": text}))

    line_buf: list[str] = []

    async def _ws_to_pty() -> None:
        while True:
            raw_msg = await websocket.receive_text()
            try:
                msg = json.loads(raw_msg)
            except Exception:
                continue

            mtype = msg.get("type")
            if mtype == "input":
                data: str = msg.get("data", "")
                if not data:
                    continue
                os.write(master_fd, data.encode("utf-8", errors="replace"))

                # Captura ligera de comandos tecleados para Post-Mortem / Mentor
                if on_command_line is not None:
                    for ch in data:
                        if ch in ("\r", "\n"):
                            cmd_str = "".join(line_buf).strip()
                            line_buf.clear()
                            if cmd_str and len(cmd_str) <= 240:
                                on_command_line(role, cmd_str)
                        elif ch in ("\x7f", "\b"):
                            if line_buf:
                                line_buf.pop()
                        elif ch == "\x03":
                            line_buf.clear()
                        elif ch >= " " and len(line_buf) < 250:
                            line_buf.append(ch)

            elif mtype == "resize":
                cols = int(msg.get("cols", 100))
                rows = int(msg.get("rows", 28))
                try:
                    _set_winsize(master_fd, rows, cols)
                    if proc.poll() is None:
                        os.killpg(os.getpgid(proc.pid), signal.SIGWINCH)
                except Exception:
                    pass

    sender_task = asyncio.create_task(_pty_to_ws())
    receiver_task = asyncio.create_task(_ws_to_pty())

    try:
        done, pending = await asyncio.wait(
            {sender_task, receiver_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        try:
            loop.remove_reader(master_fd)
        except Exception:
            pass
        try:
            os.close(master_fd)
        except OSError:
            pass
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                proc.terminate()
            try:
                proc.wait(timeout=1.5)
            except Exception:
                proc.kill()
