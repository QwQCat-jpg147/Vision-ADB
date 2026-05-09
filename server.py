import sys
import os
import subprocess
import queue
import threading
import signal
import json as json_lib
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context

# ── 編碼修復 ──
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# ── 路徑：相容開發 / PyInstaller 打包 ──
BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) \
           else os.path.dirname(os.path.abspath(__file__))

ADB      = os.path.join(BASE_DIR, "platform-tools", "adb.exe")
FASTBOOT = os.path.join(BASE_DIR, "platform-tools", "fastboot.exe")

app = Flask(__name__)

ALLOWED = {
    "adb_devices":           [ADB, "devices"],
    "adb_reboot_bootloader": [ADB, "reboot", "bootloader"],
    "adb_reboot_recovery":   [ADB, "reboot", "recovery"],
    "adb_reboot":            [ADB, "reboot"],
    "adb_version":           [ADB, "shell", "getprop", "ro.build.version.release"],
    "adb_model":             [ADB, "shell", "getprop", "ro.product.model"],
    "adb_serial":            [ADB, "shell", "getprop", "ro.serialno"],
    "adb_cpu":               [ADB, "shell", "getprop", "ro.product.cpu.abi"],
    "adb_battery":           [ADB, "shell", "dumpsys", "battery"],
    "adb_storage":           [ADB, "shell", "df", "-h", "/data"],
    "fb_devices":            [FASTBOOT, "devices"],
    "fb_reboot":             [FASTBOOT, "reboot"],
    "fb_reboot_recovery":    [FASTBOOT, "reboot", "recovery"],
    "fb_reboot_bootloader":  [FASTBOOT, "reboot", "bootloader"],
    "fb_getvar":             [FASTBOOT, "getvar", "all"],
    "fb_unlock":             [FASTBOOT, "flashing", "unlock"],
    "fb_lock":               [FASTBOOT, "flashing", "lock"],
    "fb_erase_userdata":     [FASTBOOT, "erase", "userdata"],
    "fb_erase_cache":        [FASTBOOT, "erase", "cache"],
}

ALLOWED_PARTITIONS = {"boot", "recovery", "system", "vendor", "dtbo", "vbmeta"}

# ─────────────────────────────────────────────
#  ★ 全域程序追蹤（支援取消）
# ─────────────────────────────────────────────
_current_proc      = None
_current_proc_lock = threading.Lock()

def _set_proc(proc):
    global _current_proc
    with _current_proc_lock:
        _current_proc = proc

def _clear_proc():
    global _current_proc
    with _current_proc_lock:
        _current_proc = None

def _kill_current():
    global _current_proc
    with _current_proc_lock:
        proc = _current_proc
        _current_proc = None
    if proc is None:
        return False
    try:
        if proc.poll() is None:          # 還在跑
            if os.name == 'nt':
                # Windows：直接 kill 整個程序樹
                subprocess.call(
                    ['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        pass
    return True


# ─────────────────────────────────────────────
#  一次性執行（用於 /api/status 等快速指令）
# ─────────────────────────────────────────────
def run(cmd, timeout=30):
    try:
        kwargs = {
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "ignore",
            "timeout": timeout
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        result = subprocess.run(cmd, **kwargs)
        output = (result.stdout + result.stderr).strip()
        return output if output else "(無輸出)"
    except FileNotFoundError:
        return f"[錯誤] 找不到執行檔：{cmd[0]}"
    except subprocess.TimeoutExpired:
        return f"[錯誤] 指令執行逾時（{timeout}秒）"
    except Exception as e:
        return f"[錯誤] {e}"


# ─────────────────────────────────────────────
#  串流執行：邊跑邊 yield 每一行
#  ★ 加入程序追蹤，讓 /api/cancel 可以中止
# ─────────────────────────────────────────────
def run_stream(cmd, timeout=180):
    try:
        kwargs = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        if os.name == 'nt':
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        else:
            kwargs['start_new_session'] = True   # 讓 killpg 可以殺整個群組

        proc = subprocess.Popen(cmd, **kwargs)
    except FileNotFoundError:
        yield f"__ERR__ 找不到執行檔：{cmd[0]}"
        return
    except Exception as e:
        yield f"__ERR__ {e}"
        return

    _set_proc(proc)   # ★ 登記目前程序

    q    = queue.Queue()
    _END = object()

    def _reader(stream):
        try:
            for line in stream:
                q.put(line.rstrip("\r\n"))
        finally:
            q.put(_END)

    threading.Thread(target=_reader, args=(proc.stdout,), daemon=True).start()
    threading.Thread(target=_reader, args=(proc.stderr,), daemon=True).start()

    import time
    finished = 0
    deadline = time.time() + timeout
    is_cancelled = False # 用來追蹤是否被手動取消

    try:
        while finished < 2:
            remaining = deadline - time.time()
            if remaining <= 0:
                _kill_current()
                yield "__ERR__ 指令執行逾時"
                return
            try:
                item = q.get(timeout=min(remaining, 0.5))
                if item is _END:
                    finished += 1
                elif item:
                    yield item
            except queue.Empty:
                pass
    finally:
        is_cancelled = (_current_proc is None)
        _clear_proc()   # 清除登記

    proc.wait()
    
    # 迴圈結束後，如果是被取消的，才 yield 取消訊號
    if is_cancelled:
        yield "__CANCELLED__"


# ─────────────────────────────────────────────
#  SSE 工具
# ─────────────────────────────────────────────
def sse(data: dict) -> str:
    return f"data: {json_lib.dumps(data, ensure_ascii=False)}\n\n"

def sse_err(msg: str):
    def _gen():
        yield sse({"error": msg})
    return Response(stream_with_context(_gen()),
                    content_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ─────────────────────────────────────────────
#  靜態頁面
# ─────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


# ─────────────────────────────────────────────
#  ★ 取消目前指令
# ─────────────────────────────────────────────
@app.route("/api/cancel", methods=["POST"])
def cancel():
    killed = _kill_current()
    return jsonify({"ok": killed, "msg": "已中止" if killed else "沒有執行中的指令"})


# ─────────────────────────────────────────────
#  環境 + 裝置狀態
# ─────────────────────────────────────────────
@app.route("/api/status")
def status():
    adb_ok  = os.path.exists(ADB)
    fb_ok   = os.path.exists(FASTBOOT)
    adb_raw = run([ADB, "devices"], timeout=5) if adb_ok else ""
    fb_raw  = run([FASTBOOT, "devices"], timeout=5) if fb_ok else ""

    adb_count = sum(1 for l in adb_raw.splitlines() if "\t" in l and not l.startswith("List"))
    fb_count  = sum(1 for l in fb_raw.splitlines()  if l.strip() and "\t" in l)

    return jsonify({
        "adb": adb_ok, "fastboot": fb_ok,
        "adb_raw": adb_raw, "fb_raw": fb_raw,
        "adb_count": adb_count, "fb_count": fb_count,
    })

@app.route("/api/check")
def check():
    return jsonify({"adb": os.path.exists(ADB), "fastboot": os.path.exists(FASTBOOT)})


# ─────────────────────────────────────────────
#  串流：預設指令 (GET)
# ─────────────────────────────────────────────
@app.route("/api/run/stream/<cmd_key>")
def run_preset_stream(cmd_key):
    if cmd_key not in ALLOWED:
        return sse_err("不允許的指令")
    cmd = ALLOWED[cmd_key]

    def _gen():
        yield sse({"cmd": " ".join(cmd)})
        for line in run_stream(cmd, timeout=30):
            if line == "__CANCELLED__":
                yield sse({"cancelled": True})
            elif line.startswith("__ERR__"):
                yield sse({"error": line[7:].strip()})
            else:
                yield sse({"line": line})
        yield sse({"done": True})

    return Response(stream_with_context(_gen()),
                    content_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/api/run/<cmd_key>")
def run_preset(cmd_key):
    if cmd_key not in ALLOWED:
        return jsonify({"error": "不允許的指令"}), 400
    return jsonify({"cmd": " ".join(ALLOWED[cmd_key]), "output": run(ALLOWED[cmd_key])})


# ─────────────────────────────────────────────
#  串流：刷機 (POST)
# ─────────────────────────────────────────────
@app.route("/api/flash/stream", methods=["POST"])
def flash_stream():
    data      = request.get_json(silent=True) or {}
    partition = data.get("partition", "")
    img_path  = data.get("path", "")

    if partition not in ALLOWED_PARTITIONS:
        return sse_err(f"不允許的分區：{partition}")
    if not img_path:
        return sse_err("未提供鏡像路徑")
    img_path = os.path.normpath(img_path)
    if not os.path.isfile(img_path):
        return sse_err(f"找不到檔案：{img_path}")

    cmd = [FASTBOOT, "flash", partition, img_path]

    def _gen():
        yield sse({"cmd": " ".join(cmd)})
        for line in run_stream(cmd, timeout=600):
            if line == "__CANCELLED__":
                yield sse({"cancelled": True})
            elif line.startswith("__ERR__"):
                yield sse({"error": line[7:].strip()})
            else:
                yield sse({"line": line})
        yield sse({"done": True})

    return Response(stream_with_context(_gen()),
                    content_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/api/flash", methods=["POST"])
def flash():
    data      = request.get_json(silent=True) or {}
    partition = data.get("partition", "")
    img_path  = data.get("path", "")
    if partition not in ALLOWED_PARTITIONS:
        return jsonify({"error": f"不允許的分區：{partition}"}), 400
    if not img_path:
        return jsonify({"error": "未提供鏡像路徑"}), 400
    img_path = os.path.normpath(img_path)
    if not os.path.isfile(img_path):
        return jsonify({"error": f"找不到檔案：{img_path}"}), 400
    cmd = [FASTBOOT, "flash", partition, img_path]
    return jsonify({"cmd": " ".join(cmd), "output": run(cmd, timeout=600)})


# ─────────────────────────────────────────────
#  串流：Sideload (POST)
# ─────────────────────────────────────────────
@app.route("/api/sideload/stream", methods=["POST"])
def sideload_stream():
    data     = request.get_json(silent=True) or {}
    zip_path = data.get("path", "")

    if not zip_path:
        return sse_err("未提供 ZIP 路徑")
    zip_path = os.path.normpath(zip_path)
    
    # 👑 加入防護：防止中文路徑造成 ADB 發生未知的中斷
    if not zip_path.isascii():
        return sse_err("為了避免 ADB 發生錯誤，請勿將刷機包放在包含中文或特殊符號的路徑下（例如桌面）。請移至 C:\\ 根目錄下再試。")

    if not os.path.isfile(zip_path):
        return sse_err(f"找不到檔案：{zip_path}")
    if not zip_path.lower().endswith(".zip"):
        return sse_err("只接受 .zip 格式")

    cmd = [ADB, "sideload", zip_path]

    def _gen():
        yield sse({"cmd": " ".join(cmd)})
        for line in run_stream(cmd, timeout=600):
            if line == "__CANCELLED__":
                yield sse({"cancelled": True})
            elif line.startswith("__ERR__"):
                yield sse({"error": line[7:].strip()})
            else:
                yield sse({"line": line})
        yield sse({"done": True})

    return Response(stream_with_context(_gen()),
                    content_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/api/sideload", methods=["POST"])
def sideload():
    data     = request.get_json(silent=True) or {}
    zip_path = data.get("path", "")
    if not zip_path:
        return jsonify({"error": "未提供 ZIP 路徑"}), 400
    zip_path = os.path.normpath(zip_path)
    
    # 👑 加入防護
    if not zip_path.isascii():
        return jsonify({"error": "為了避免 ADB 發生錯誤，請勿將刷機包放在包含中文或特殊符號的路徑下。"}), 400

    if not os.path.isfile(zip_path):
        return jsonify({"error": f"找不到檔案：{zip_path}"}), 400
    if not zip_path.lower().endswith(".zip"):
        return jsonify({"error": "只接受 .zip 格式"}), 400
    cmd = [ADB, "sideload", zip_path]
    return jsonify({"cmd": " ".join(cmd), "output": run(cmd, timeout=600)})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=54321, debug=False, threaded=True)
