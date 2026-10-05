#!/usr/bin/env python3
# ╔══════════════════════════════════════════════════╗
# ║  G H O S T M O D E  v2.0 — System-Tor Edition    ║
# ║  Ganzer PC über Tor · kein Tor Browser nötig     ║
# ╚══════════════════════════════════════════════════╝
import tkinter as tk
from tkinter import scrolledtext, font as tkfont
import threading, queue, socket, struct, random, time, os, sys, subprocess
import requests

BG, PANEL   = "#0a0e0a", "#101710"
FG, ACCENT  = "#00ff41", "#00cc33"
DIM, DIMTXT = "#0a5c22", "#1f6b35"
WARN, RED   = "#ffcc00", "#ff3333"

SOCKS_PORT, CONTROL_PORT, GATEWAY_PORT = 9050, 9051, 8888
TOR_PATHS = [  # wo tor.exe gesucht wird
    r"C:\Tor Browser",
    r"C:\Program Files\Tor\Tor\tor.exe",
    os.path.expanduser(r"~\Desktop\Tor\Tor\tor.exe"),
    r"C:\Tools\Tor\tor.exe",
]
TORRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ghost_torrc")

TOR_SOCKS = {"http": f"socks5h://127.0.0.1:{SOCKS_PORT}",
             "https": f"socks5h://127.0.0.1:{SOCKS_PORT}"}

# ─────────── Tor-Daemon-Manager ───────────
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
            ui.write("[i] Tor läuft bereits.\n", WARN); return True
        exe = cls.find_tor()
        if not exe:
            ui.write("[!] tor.exe nicht gefunden! Tor Expert Bundle entpacken nach:\n", RED)
            for p in TOR_PATHS: ui.write(f"      {p}\n", DIMTXT)
            ui.write("    Oder TOR_PATHS im Script oben anpassen.\n", DIMTXT)
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
        ui.write("[*] Tor-Daemon startet (Bootstrap ~10-20s)...\n", WARN)
        for i in range(30):
            time.sleep(1)
            try:
                s = socket.create_connection(("127.0.0.1", SOCKS_PORT), timeout=2)
                s.close()
                ui.write("[✓] TOR-LAUFZEIT AKTIV (SOCKS5 127.0.0.1:%d)\n" % SOCKS_PORT, ACCENT)
                return True
            except OSError:
                pass
        ui.write("[!] Tor hat nicht geantwortet — Konsole prüfen.\n", RED)
        return False

    @classmethod
    def stop(cls, ui):
        if cls.proc and cls.proc.poll() is None:
            cls.proc.terminate()
            ui.write("[✓] Tor-Daemon gestoppt.\n", WARN)
        cls.proc = None

    @classmethod
    def alive(cls):
        try:
            s = socket.create_connection(("127.0.0.1", SOCKS_PORT), timeout=2)
            s.close(); return True
        except OSError:
            return False

# ─────────── Systemweiter Proxy (ganzer PC) ───────────
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
                       shell=True, capture_output=True)  # Proxy-Refresh
        ui.write("[✓] GANZER-PC-MODUS AN — Windows-Systemproxy → Gateway:8888 → Tor\n", ACCENT)
        ui.write("    (Browser, Store, Updates etc. die den Systemproxy nutzen, gehen über Tor)\n", DIMTXT)

    @classmethod
    def off(cls, ui):
        subprocess.run(f'reg add "{cls.KEY}" /v ProxyEnable /t REG_DWORD /d 0 /f',
                       shell=True, capture_output=True)
        ui.write("[✓] Systemproxy AUS — normaler Traffic wiederhergestellt.\n", WARN)

    @staticmethod
    def _admin(ui):
        try:
            import ctypes
            if ctypes.windll.shell32.IsUserAnAdmin(): return True
        except Exception: pass
        ui.write("[!] Admin-Rechte nötig → Python 'Als Administrator ausführen'.\n", RED)
        return False

# ─────────── Gateway: leitet HTTP/S nach Tor ───────────
import urllib.parse, ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

def socks5_connect(ip, port):
    """Minimaler SOCKS5-Client — keine Zusatzlibs nötig."""
    s = socket.create_connection(("127.0.0.1", SOCKS_PORT), timeout=20)
    s.sendall(b"\x05\x01\x00")                 # Greeting: no auth
    if s.recv(2) != b"\x05\x00": raise OSError("SOCKS5-Handshake fehlgeschlagen")
    host = ip.encode()
    s.sendall(b"\x05\x01\x00\x03" + bytes([len(host)]) + host +
              struct.pack(">H", port))         # CONNECT per Hostname (DNS durch Tor!)
    r = s.recv(10)
    if len(r) < 2 or r[1] != 0:
        s.close(); raise OSError(f"SOCKS5-Verbindung abgelehnt (code {r[1:2]})")
    return s

def doh_fallback_resolve(host):  # nur falls SOCKS direkte IP braucht
    try: return socket.gethostbyname(host)
    except OSError: return None

class GatewayHandler(BaseHTTPRequestHandler):
    ui = None
    def log_message(self, *a): pass

    def do_CONNECT(self):
        """HTTPS-Tunnel: Browser → Gateway → SOCKS5(Tor)."""
        host, _, p = self.path.partition(":")
        port = int(p or 443)
        try:
            remote = socks5_connect(host, port)   # Hostname → Tor löst DNS (kein Leak!)
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
            try: self.send_error(502, f"Tor-Tunnel fehlgeschlagen: {e}")
            except Exception: pass
        if self.ui: self.ui.write(f"  [tor-tunnel] {host}:{port}\n", DIMTXT)

    def do_GET(self):  self.relay_plain()
    def do_POST(self): self.relay_plain()

    def relay_plain(self):
        """Klartext-HTTP über requests mit socks5h (DNS über Tor)."""
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

# ─────────── GUI ───────────
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
        tk.Label(header, text="// systemweites Tor · eigener Gateway · kein Tor Browser",
                 fg=DIMTXT, bg=PANEL, font=f).pack(side="left")
        self.dot = tk.Label(header, text="●", fg=DIM, bg=PANEL, font=f_btn)
        self.dot.pack(side="right", padx=16)
        self.dotlabel = tk.Label(header, text="TOR: AUS", fg=DIM, bg=PANEL, font=f)
        self.dotlabel.pack(side="right")

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=10)

        side = tk.Frame(body, bg=PANEL, highlightthickness=1, highlightbackground=DIM)
        side.pack(side="left", fill="y", padx=(0, 12))
        tk.Label(side, text="── STEUERUNG ──", fg=DIMTXT, bg=PANEL, font=f).pack(pady=(10, 6))

        for label, cmd, col in [
            ("TOR-DAEMON STARTEN",   self.tor_start, ACCENT),
            ("TOR-DAEMON STOPPEN",   self.tor_stop,  ACCENT),
            ("GATEWAY STARTEN",      self.gw_start,  ACCENT),
            ("★ GANZER-PC-MODUS AN", self.pc_on,     WARN),
            ("★ GANZER-PC-MODUS AUS", self.pc_off,   WARN),
            ("NEUE TOR-IDENTITÄT",   self.new_nym,   ACCENT),
            ("IP-PRÜFUNG (ÜBER TOR)",self.check_ip,   ACCENT),
            ("ANLEITUNG",            self.help,      DIMTXT),
        ]:
            tk.Button(side, text="> " + label, command=cmd, bg=PANEL, fg=col,
                      activebackground="#00330f", activeforeground=FG, font=f_btn,
                      anchor="w", relief="flat", highlightthickness=1,
                      highlightbackground=DIM, padx=14, pady=8, width=25
                      ).pack(fill="x", padx=8, pady=4)

        tk.Button(side, text="> EXIT (alles sauber beenden)", command=self.exit_app,
                  bg=PANEL, fg=RED, activebackground="#330a0a", font=f_btn,
                  anchor="w", relief="flat", highlightthickness=1,
                  highlightbackground=DIM, padx=14, pady=8, width=25
                  ).pack(fill="x", padx=8, pady=4)

        self.status = tk.Label(side, text="STATUS: BEREIT", fg=DIM, bg=PANEL,
                               font=f, anchor="w", wraplength=190, justify="left")
        self.status.pack(side="bottom", fill="x", padx=12, pady=10)

        lf = tk.Frame(body, bg=DIM, highlightthickness=1, highlightbackground=DIM)
        lf.pack(side="left", fill="both", expand=True)
        tk.Label(lf, text="┌─ GHOST-KONSOLE ─────────────────────┐",
                 fg=DIMTXT, bg=BG, font=f, anchor="w").pack(fill="x", padx=8, pady=(6, 0))
        self.log = scrolledtext.ScrolledText(lf, bg=BG, fg=FG, font=f,
                    insertbackground=FG, state="disabled", wrap="word",
                    relief="flat", padx=10, pady=6, borderwidth=0)
        self.log.pack(fill="both", expand=True, padx=6, pady=(0, 8))
        self._put("[✓] GHOSTMODE v2.0 bereit. Reihenfolge: TOR STARTEN → GATEWAY STARTEN.\n", DIM)

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
        self.dotlabel.configure(text="TOR: AUS" if not tor_up else "TOR: LIVE",
                                fg=ACCENT if tor_up else DIM)
        self.root.after(800, self.blink)

    def bg(self, fn, label="ARBEITE..."):
        def w():
            self.root.after(0, lambda: self.status.configure(text="STATUS: " + label, fg=WARN))
            try: fn()
            except Exception as e: self.write(f"[!] {e}\n", RED)
            self.root.after(0, lambda: self.status.configure(text="STATUS: BEREIT", fg=DIM))
        threading.Thread(target=w, daemon=True).start()

    # ── Aktionen ──
    def tor_start(self):
        self.bg(lambda: TorManager.start(self), "STARTE TOR")
    def tor_stop(self):
        self.bg(lambda: TorManager.stop(self), "STOPPE TOR")
    def gw_start(self):
        def job():
            if self.srv: self.write("[i] Gateway läuft bereits.\n", WARN); return
            if not TorManager.alive():
                self.write("[!] Erst TOR-DAEMON STARTEN!\n", RED); return
            GatewayHandler.ui = self
            self.srv = ThreadingHTTPServer(("127.0.0.1", GATEWAY_PORT), GatewayHandler)
            threading.Thread(target=self.srv.serve_forever, daemon=True).start()
            self.write(f"[✓] GHOST-GATEWAY aktiv: 127.0.0.1:{GATEWAY_PORT} → Tor-SOCKS:{SOCKS_PORT}\n", ACCENT)
            self.write("    DNS wird von TOR aufgelöst (kein DNS-Leak möglich).\n", DIMTXT)
        self.bg(job, "STARTE GATEWAY")
    def pc_on(self):
        if not self.srv: self.write("[!] Erst GATEWAY STARTEN, dann Ganzer-PC-Modus!\n", RED); return
        SystemProxy.on(self)
    def pc_off(self): SystemProxy.off(self)
    def new_nym(self):
        def job():
            try:
                import socks  # noqa
            except ImportError:
                self.write("[!] pip install pysocks\n", RED); return
            try:
                # Newnym über ControlPort (Cookie-Auth)
                import ssl
                s = socket.create_connection(("127.0.0.1", CONTROL_PORT), timeout=5)
                cookie = open(self._control_cookie(), "rb").read() \
                    if os.path.exists(self._control_cookie()) else b""
                s.sendall(b"AUTHENTICATE \"%s\"\r\n" % cookie.replace(b'"', b'\\"'))
                s.recv(1024)
                s.sendall(b"SIGNAL NEWNYM\r\n")
                resp = s.recv(1024)
                self.write("[✓] Neue Tor-Identität!" if b"250" in resp
                           else f"[!] Antwort: {resp}\n", ACCENT)
                s.close()
            except Exception:
                self.write("[!] ControlPort nicht erreichbar. Tor neustarten.\n", RED)
        self.bg(job)
    @staticmethod
    def _control_cookie():
        # Cookie liegt im Data-Verzeichnis des Tor-Daemons
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
                self.write("[!] Keine Tor-Verbindung. Erst TOR + GATEWAY starten.\n", RED)
            try:
                real = requests.get("https://api.ipify.org", timeout=8).text
                self.write(f"[i] Deine reale IP (nur zur Kontrolle): {real}\n", WARN)
            except Exception: pass
        self.bg(job, "PRÜFE TOR-IP")
    def help(self):
        self.write("""
=== GHOSTMODE v2.0 — SYSTEM-TOR ANLEITUNG ==================
 1. Einmalig: Tor Expert Bundle laden, entpacken nach C:\\Tor
    (tor.exe → C:\Tor Browser) — KEIN Tor Browser nötig!
 2. > TOR-DAEMON STARTEN   (warte bis TOR: LIVE oben leuchtet)
 3. > GATEWAY STARTEN      (127.0.0.1:8888, DNS über Tor)
 4. ★ GANZER-PC-MODUS AN   → setzt Windows-Systemproxy auf das
    Gateway. Der GANZE PC-Traffic läuft dann:
       [DEIN PC] → GATEWAY:8888 → TOR (3 Hops) → INTERNET
    Apps, die den Windows-Proxy nutzen (Browser, Store,
    die meisten Programme), gehen automatisch über Tor.
 5. > NEUE TOR-IDENTITÄT   → komplette neue IP + Circuit
 6. ★ AUS schaltet alles zurück auf normal.

 WAS DEIN ISP/NETZWERK NOCH SIEHT:
  Nur verschlüsselte Verbindungen zu Tor-Entry-Nodes.
  WELCHE SEITEN du besuchst: NICHTS (DNS läuft durch Tor).
  WAS SEITEN ÜBER DICH WISSEN: Tor-Exit-IP, nicht deine.

 HINWEIS: Programme die den Systemproxy IGNORIEREN (z.B.
 manche Spiele/CLI-Tools) laufen direkt — für 100% erzwingen
 wäre eine Firewall-Regel nötig. 
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