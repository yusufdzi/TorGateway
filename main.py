#!/usr/bin/env python3
import tkinter as tk
from tkinter import scrolledtext, font as tkfont
import threading, queue, socket, struct, random, time, os, sys, subprocess
import requests

BG, PANEL   = "#0a0e0a", "#101710"
FG, ACCENT  = "#00ff41", "#00cc33"
DIM, DIMTXT = "#0a5c22", "#1f6b35"
WARN, RED   = "#ffcc00", "#ff3333"

SOCKS_PORT, CONTROL_PORT, GATEWAY_PORT = 9050, 9051, 8888
TOR_PATHS = [
    r"C:\Tor Browser",
    r"C:\Tor Browser\Browser\TorBrowser\Tor\tor.exe",
    os.path.expanduser(r"~\Desktop\Tor\Tor\tor.exe"),
    r"C:\Tools\Tor\tor.exe",
]
TORRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ghost_torrc")

TOR_SOCKS = {"http": f"socks5h://127.0.0.1:{SOCKS_PORT}",
             "https": f"socks5h://127.0.0.1:{SOCKS_PORT}"}

class TorManager:
    proc = None

    @classmethod
    def find_tor(cls):
        for p in TOR_PATHS:
            if os.path.isfile(p): return p
        return None

    @classmethod
    def start(cls, ui):
        if cls.proc and cls.proc.poll() is None:
            ui.write("[i] Tor is already running.\n", WARN); return True
        exe = cls.find_tor()
        if not exe:
            ui.write("[!] tor.exe not found! Unpack Tor Expert Bundle to:\n", RED)
            for p in TOR_PATHS: ui.write(f"      {p}\n", DIMTXT)
            ui.write("    Or adjust TOR_PATHS at the top of the script.\n", DIMTXT)
            return False
        with open(TORRC, "w") as f:
            f.write(f"""SocksPort 127.0.0.1:{SOCKS_PORT}
ControlPort 127.0.0.1:{CONTROL_PORT}
CookieAuthentication 1
SafeLogging 1
""")
        cls.proc = subprocess.Popen(
            [exe, "-f", TORRC],
            cwd=os.path.dirname(exe),
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ui.write("[*] Tor daemon starting (bootstrap ~10-20s)...\n", WARN)
        for i in range(30):
            time.sleep(1)
            try:
                s = socket.create_connection(("127.0.0.1", SOCKS_PORT), timeout=2)
                s.close()
                ui.write("[✓] TOR RUNTIME ACTIVE (SOCKS5 127.0.0.1:%d)\n" % SOCKS_PORT, ACCENT)
                return True
            except OSError:
                pass
        ui.write("[!] Tor did not respond — check console.\n", RED)
        return False

    @classmethod
    def stop(cls, ui):
        if cls.proc and cls.proc.poll() is None:
            cls.proc.terminate()
            ui.write("[✓] Tor daemon stopped.\n", WARN)
        cls.proc = None

    @classmethod
    def alive(cls):
        try:
            s = socket.create_connection(("127.0.0.1", SOCKS_PORT), timeout=2)
            s.close(); return True
        except OSError:
            return False

class SystemProxy:
    KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings"

    @classmethod
    def on(cls, ui):
        if not cls._admin(ui): return
        for cmd in [
            f'reg add "{cls.KEY}" /v ProxyEnable /t REG_DWORD /d 1 /f',
            f'reg add "{cls.KEY}" /v ProxyServer /t REG_SZ /d 127.0.0.1:{GATEWAY_PORT} /f',
            f'reg add "{cls.KEY}" /v ProxyOverride /t REG_SZ /d "<local>" /f',
        ]:
            subprocess.run(cmd, shell=True, capture_output=True)
        subprocess.run("taskkill /im explorer.exe /f & start explorer.exe",
                       shell=True, capture_output=True)
        ui.write("[✓] WHOLE-PC MODE ON — Windows system proxy → Gateway:8888 → Tor\n", ACCENT)
        ui.write("    (Browser, Store, Updates etc. using the system proxy go through Tor)\n", DIMTXT)

    @classmethod
    def off(cls, ui):
        subprocess.run(f'reg add "{cls.KEY}" /v ProxyEnable /t REG_DWORD /d 0 /f',
                       shell=True, capture_output=True)
        ui.write("[✓] System proxy OFF — normal traffic restored.\n", WARN)

    @staticmethod
    def _admin(ui):
        try:
            import ctypes
            if ctypes.windll.shell32.IsUserAnAdmin(): return True
        except Exception: pass
        ui.write("[!] Admin rights required → Run Python 'As Administrator'.\n", RED)
        return False

import urllib.parse, ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

def socks5_connect(ip, port):
    s = socket.create_connection(("127.0.0.1", SOCKS_PORT), timeout=20)
    s.sendall(b"\x05\x01\x00")
    if s.recv(2) != b"\x05\x00": raise OSError("SOCKS5 handshake failed")
    host = ip.encode()
    s.sendall(b"\x05\x01\x00\x03" + bytes([len(host)]) + host +
              struct.pack(">H", port))
    r = s.recv(10)
    if len(r) < 2 or r[1] != 0:
        s.close(); raise OSError(f"SOCKS5 connection refused (code {r[1:2]})")
    return s

def doh_fallback_resolve(host):
    try: return socket.gethostbyname(host)
    except OSError: return None

class GatewayHandler(BaseHTTPRequestHandler):
    ui = None
    def log_message(self, *a): pass

    def do_CONNECT(self):
        host, _, p = self.path.partition(":")
        port = int(p or 443)
        try:
            remote = socks5_connect(host, port)
            self.connection.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            stop = threading.Event()
            def pump(a, b):
                try:
                    while not stop.is_set():
                        d = a.recv(65536)
                        if not d: break
                        b.sendall(d)
                except OSError: pass
                stop.set()
                try: b.shutdown(socket.SHUT_RDWR)
                except OSError: pass
            threading.Thread(target=pump, args=(self.connection, remote), daemon=True).start()
            pump(remote, self.connection)
        except Exception as e:
            try: self.send_error(502, f"Tor tunnel failed: {e}")
            except Exception: pass
        if self.ui: self.ui.write(f"  [tor-tunnel] {host}:{port}\n", DIMTXT)

    def do_GET(self):  self.relay_plain()
    def do_POST(self): self.relay_plain()

    def relay_plain(self):
        try:
            data = self.rfile.read(int(self.headers.get("Content-Length", 0))) \
                   if self.command == "POST" else None
            h = {k: v for k, v in self.headers.items()
                 if k.lower() not in ("referer", "x-forwarded-for", "via",
                                      "x-client-data", "sec-ch-ua")}
            r = requests.request(self.command, self.path, data=data,
                                 headers=h, proxies=TOR_SOCKS, timeout=30,
                                 allow_redirects=False)
            self.send_response(r.status_code)
            for k, v in r.headers.items():
                if k.lower() in ("transfer-encoding", "connection"): continue
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(r.content)
            if self.ui: self.ui.write(f"  [tor-http] {self.path[:60]} [{r.status_code}]\n", DIMTXT)
        except Exception as e:
            try: self.send_error(502, str(e))
            except Exception: pass

class UI:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        root.title("GHOSTMODE v2.0 — SYSTEM TOR")
        root.configure(bg=BG)
        root.geometry("1020x700")

        f     = tkfont.Font(family="Consolas", size=10)
        f_btn = tkfont.Font(family="Consolas", size=10, weight="bold")
        f_big = tkfont.Font(family="Consolas", size=17, weight="bold")

        header = tk.Frame(root, bg=PANEL, highlightthickness=1, highlightbackground=DIM)
        header.pack(fill="x")
        tk.Label(header, text="☠ GHOSTMODE", fg=FG, bg=PANEL, font=f_big).pack(side="left", padx=16, pady=10)
        tk.Label(header, text="// system-wide Tor · own gateway · no Tor Browser",
                 fg=DIMTXT, bg=PANEL, font=f).pack(side="left")
        self.dot = tk.Label(header, text="●", fg=DIM, bg=PANEL, font=f_btn)
        self.dot.pack(side="right", padx=16)
        self.dotlabel = tk.Label(header, text="TOR: OFF", fg=DIM, bg=PANEL, font=f)
        self.dotlabel.pack(side="right")

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=10)

        side = tk.Frame(body, bg=PANEL, highlightthickness=1, highlightbackground=DIM)
        side.pack(side="left", fill="y", padx=(0, 12))
        tk.Label(side, text="── CONTROL ──", fg=DIMTXT, bg=PANEL, font=f).pack(pady=(10, 6))

        for label, cmd, col in [
            ("START TOR DAEMON",      self.tor_start, ACCENT),
            ("STOP TOR DAEMON",       self.tor_stop,  ACCENT),
            ("START GATEWAY",         self.gw_start,  ACCENT),
            ("★ WHOLE-PC MODE ON",    self.pc_on,     WARN),
            ("★ WHOLE-PC MODE OFF",   self.pc_off,    WARN),
            ("NEW TOR IDENTITY",      self.new_nym,   ACCENT),
            ("IP CHECK (VIA TOR)",    self.check_ip,  ACCENT),
            ("HELP",                  self.help,      DIMTXT),
        ]:
            tk.Button(side, text="> " + label, command=cmd, bg=PANEL, fg=col,
                      activebackground="#00330f", activeforeground=FG, font=f_btn,
                      anchor="w", relief="flat", highlightthickness=1,
                      highlightbackground=DIM, padx=14, pady=8, width=25
                      ).pack(fill="x", padx=8, pady=4)

        tk.Button(side, text="> EXIT (clean shutdown)", command=self.exit_app,
                  bg=PANEL, fg=RED, activebackground="#330a0a", font=f_btn,
                  anchor="w", relief="flat", highlightthickness=1,
                  highlightbackground=DIM, padx=14, pady=8, width=25
                  ).pack(fill="x", padx=8, pady=4)

        self.status = tk.Label(side, text="STATUS: READY", fg=DIM, bg=PANEL,
                               font=f, anchor="w", wraplength=190, justify="left")
        self.status.pack(side="bottom", fill="x", padx=12, pady=10)

        lf = tk.Frame(body, bg=DIM, highlightthickness=1, highlightbackground=DIM)
        lf.pack(side="left", fill="both", expand=True)
        tk.Label(lf, text="┌─ GHOST CONSOLE ─────────────────────┐",
                 fg=DIMTXT, bg=BG, font=f, anchor="w").pack(fill="x", padx=8, pady=(6, 0))
        self.log = scrolledtext.ScrolledText(lf, bg=BG, fg=FG, font=f,
                    insertbackground=FG, state="disabled", wrap="word",
                    relief="flat", padx=10, pady=6, borderwidth=0)
        self.log.pack(fill="both", expand=True, padx=6, pady=(0, 8))
        self._put("[✓] GHOSTMODE v2.0 ready. Order: START TOR → START GATEWAY.\n", DIM)

        self.pulse(); self.blink()
        self.srv = None

    def _put(self, msg, color): self.q.put((msg, color))
    def write(self, msg, color=FG): self._put(msg, color)
    def pulse(self):
        try:
            while True:
                msg, color = self.q.get_nowait()
                self.log.configure(state="normal")
                self.log.tag_config(color, foreground=color)
                self.log.insert("end", msg, color)
                self.log.see("end")
                self.log.configure(state="disabled")
        except queue.Empty: pass
        self.root.after(100, self.pulse)

    def blink(self):
        tor_up = TorManager.alive()
        on = self.dot.cget("fg") == DIM
        self.dot.configure(fg=FG if tor_up else (DIM if on else "#0a3d18"))
        self.dotlabel.configure(text="TOR: OFF" if not tor_up else "TOR: LIVE",
                                fg=ACCENT if tor_up else DIM)
        self.root.after(800, self.blink)

    def bg(self, fn, label="WORKING..."):
        def w():
            self.root.after(0, lambda: self.status.configure(text="STATUS: " + label, fg=WARN))
            try: fn()
            except Exception as e: self.write(f"[!] {e}\n", RED)
            self.root.after(0, lambda: self.status.configure(text="STATUS: READY", fg=DIM))
        threading.Thread(target=w, daemon=True).start()

    def tor_start(self):
        self.bg(lambda: TorManager.start(self), "STARTING TOR")
    def tor_stop(self):
        self.bg(lambda: TorManager.stop(self), "STOPPING TOR")
    def gw_start(self):
        def job():
            if self.srv: self.write("[i] Gateway already running.\n", WARN); return
            if not TorManager.alive():
                self.write("[!] Start TOR DAEMON first!\n", RED); return
            GatewayHandler.ui = self
            self.srv = ThreadingHTTPServer(("127.0.0.1", GATEWAY_PORT), GatewayHandler)
            threading.Thread(target=self.srv.serve_forever, daemon=True).start()
            self.write(f"[✓] GHOST-GATEWAY active: 127.0.0.1:{GATEWAY_PORT} → Tor-SOCKS:{SOCKS_PORT}\n", ACCENT)
            self.write("    DNS is resolved by TOR (no DNS leak possible).\n", DIMTXT)
        self.bg(job, "STARTING GATEWAY")
    def pc_on(self):
        if not self.srv: self.write("[!] Start GATEWAY first, then Whole-PC mode!\n", RED); return
        SystemProxy.on(self)
    def pc_off(self): SystemProxy.off(self)
    def new_nym(self):
        def job():
            try:
                import socks  # noqa
            except ImportError:
                self.write("[!] pip install pysocks\n", RED); return
            try:
                import ssl
                s = socket.create_connection(("127.0.0.1", CONTROL_PORT), timeout=5)
                cookie = open(self._control_cookie(), "rb").read() \
                    if os.path.exists(self._control_cookie()) else b""
                s.sendall(b"AUTHENTICATE \"%s\"\r\n" % cookie.replace(b'"', b'\\"'))
                s.recv(1024)
                s.sendall(b"SIGNAL NEWNYM\r\n")
                resp = s.recv(1024)
                self.write("[✓] New Tor identity!" if b"250" in resp
                           else f"[!] Response: {resp}\n", ACCENT)
                s.close()
            except Exception:
                self.write("[!] ControlPort not reachable. Restart Tor.\n", RED)
        self.bg(job)
    @staticmethod
    def _control_cookie():
        base = os.path.dirname(TorManager.find_tor() or "")
        for cand in [os.path.join(base, "..", "Data", "Tor", "control_auth_cookie"),
                     os.path.join(os.path.dirname(TORRC), "control_auth_cookie"),
                     os.path.expandvars(r"%APPDATA%\tor\control_auth_cookie")]:
            if os.path.exists(cand): return cand
        return ""

    def check_ip(self):
        def job():
            try:
                ip = requests.get("https://api.ipify.org", proxies=TOR_SOCKS, timeout=25).text
                info = requests.get(f"http://ip-api.com/json/{ip}", proxies=TOR_SOCKS, timeout=25).json()
                self.write(f"[✓] TOR-EXIT-IP : {ip}  |  {info.get('country','?')} ({info.get('isp','?')})\n", ACCENT)
            except Exception:
                self.write("[!] No Tor connection. Start TOR + GATEWAY first.\n", RED)
            try:
                real = requests.get("https://api.ipify.org", timeout=8).text
                self.write(f"[i] Your real IP (control only): {real}\n", WARN)
            except Exception: pass
        self.bg(job, "CHECKING TOR IP")
    def help(self):
        self.write("""
=== GHOSTMODE v2.0 — SYSTEM-TOR GUIDE ======================
 1. Once: download Tor Expert Bundle, unpack to C:\\Tor
    (tor.exe → C:\\Tor Browser) — NO Tor Browser needed!
 2. > START TOR DAEMON   (wait until TOR: LIVE glows above)
 3. > START GATEWAY      (127.0.0.1:8888, DNS via Tor)
 4. ★ WHOLE-PC MODE ON   → sets Windows system proxy to the
    gateway. The WHOLE PC traffic then runs:
       [YOUR PC] → GATEWAY:8888 → TOR (3 HOPS) → INTERNET
    Apps using the Windows proxy (browser, store, most
    programs) automatically go through Tor.
 5. > NEW TOR IDENTITY   → complete new IP + circuit
 6. ★ OFF switches everything back to normal.

 WHAT YOUR ISP/NETWORK STILL SEES:
  Only encrypted connections to Tor entry nodes.
  WHICH SITES you visit: NOTHING (DNS runs through Tor).
  WHAT SITES KNOW ABOUT YOU: Tor exit IP, not yours.

 NOTE: Programs that IGNORE the system proxy (e.g. some
 games/CLI tools) run directly — forcing 100% would need
 a firewall rule.
===========================================================
""", DIMTXT)

    def exit_app(self):
        SystemProxy.off(self) if self.srv else None
        if self.srv: self.srv.shutdown()
        TorManager.stop(self)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    UI(root)
    root.mainloop()
