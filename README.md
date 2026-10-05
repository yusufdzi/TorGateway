👻 GhostRoute
Windows · Tor · Local Gateway · Privacy Tool

⚠️ IMPORTANT: GhostRoute is not a VPN and does not guarantee system-wide Tor routing or anonymity. Applications that bypass the Windows system proxy may connect directly to the Internet.

🚀 Overview

GhostRoute is a lightweight Windows GUI for routing supported application traffic through a local Tor SOCKS5 daemon.

It provides a simple interface for:

🧅 Starting and stopping the Tor daemon

🌐 Running a local HTTP/HTTPS gateway

🔒 Routing supported traffic through Tor

🛡️ Configuring the Windows system proxy

🔍 Checking the current Tor exit IP

🔄 Requesting a new Tor circuit

📡 Monitoring Tor connectivity

Traffic flow
┌──────────────────────┐
│     Application      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ GhostRoute Gateway   │
│     127.0.0.1:8888  │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│    Tor SOCKS5        │
│     127.0.0.1:9050  │
└──────────┬───────────┘
           │
           ▼
     🧅 Tor Network
           │
           ▼
        Internet

✨ Features
Feature	Status
Tor daemon management	✅
Local SOCKS5 support	✅
HTTP proxy gateway	✅
HTTPS CONNECT tunneling	✅
SOCKS5 hostname resolution	✅
Windows system proxy	✅
Tor exit-IP check	✅
Tor NEWNYM	✅
Tkinter GUI	✅
External Python proxy libraries required	❌
⚙️ Requirements

Windows

Python 3

Tor Expert Bundle

Python package:

pip install requests


tkinter is normally included with standard Windows Python installations.

🧅 Tor Setup

Download Tor from an official Tor Project distribution.

Place tor.exe somewhere accessible, for example:

C:\Tor\


Then adjust TOR_PATHS in the Python script if necessary:

TOR_PATHS = [
    r"C:\Tor\tor.exe",
    r"C:\Program Files\Tor\Tor\tor.exe",
]

▶️ Usage

Start the application:

python ghostroute.py


Then:

Start Tor

Wait until Tor is connected

Start Gateway

Optionally enable System Proxy

Verify the Tor exit IP

Recommended order
TOR START
    ↓
GATEWAY START
    ↓
SYSTEM PROXY ON
    ↓
VERIFY TOR EXIT IP

⚠️ Security & Privacy
🚨 READ THIS BEFORE USING GHOSTROUTE

GhostRoute does not provide guaranteed anonymity.

The Windows system proxy only affects applications that actually respect the Windows proxy configuration.

Some applications may completely bypass it.

GhostRoute does NOT guarantee:

❌ All PC traffic goes through Tor

❌ All applications use the proxy

❌ No direct connections are possible

❌ Complete anonymity

❌ Protection against browser fingerprinting

❌ Protection against cookies or logged-in accounts

❌ Protection against application-level identification

❌ A network-level kill switch

Applications may bypass the proxy

Examples can include:

Games

Some command-line applications

Custom networking applications

Security software

Applications using their own networking stack

Software configured to ignore system proxy settings

Never assume that enabling System Proxy means every connection on the computer is using Tor.

🌐 DNS & Tor

GhostRoute uses SOCKS5 hostname connections where possible so that hostname resolution can be performed through Tor.

However:

⚠️ This does not guarantee that every application on the computer is protected against DNS leaks.

An application that bypasses the GhostRoute gateway may perform its own DNS resolution directly.

🔐 HTTPS

GhostRoute tunnels HTTPS connections through Tor using the HTTP CONNECT method.

The general path is:

Application
    ↓
GhostRoute
    ↓
Tor
    ↓
Tor Exit Node
    ↓
HTTPS Website


HTTPS encryption between the client and the destination remains important.

However, Tor does not magically encrypt ordinary HTTP traffic end-to-end.

Unencrypted traffic can be visible to the destination network and potentially to the Tor exit node.

🖥️ Local Ports

GhostRoute uses the following local ports:

Service	Address
Tor SOCKS5	127.0.0.1:9050
Tor ControlPort	127.0.0.1:9051
GhostRoute Gateway	127.0.0.1:8888

These services should remain bound to:

127.0.0.1


⚠️ Do not expose the SOCKS5 proxy, HTTP gateway, or Tor ControlPort to your LAN or the public Internet unless you fully understand the security implications.

🔑 Administrator Privileges

Changing the Windows system proxy may require administrator privileges depending on the environment.

Review the source code before running GhostRoute with elevated privileges.

Never run modified or untrusted versions of this software as Administrator.

🛑 Important Disclaimer

GhostRoute is a privacy/networking utility, not a security guarantee.

The software is provided "AS IS", without warranties of any kind.

The authors and contributors are not responsible for:

Network configuration problems

IP or DNS leaks

Applications bypassing the proxy

Loss of connectivity

Incorrect Tor configuration

Data loss

Privacy failures

Misuse of the software

Damage resulting from use of the software

You are responsible for understanding and verifying your own network configuration.

⚖️ Responsible Use

GhostRoute is intended for:

✅ Privacy research

✅ Networking experiments

✅ Development

✅ Security education

✅ Testing

✅ Legitimate privacy use

Users are responsible for complying with:

Applicable laws

Network policies

Organizational rules

Service Terms of Use

Do not use GhostRoute to bypass access controls, violate network policies, or conduct unauthorized activity.

🔄 NEWNYM

GhostRoute can request a new Tor identity through the Tor ControlPort.

⚠️ NEWNYM does not mean that every existing connection immediately receives a completely new identity.

Existing connections may continue using their current circuits.

🧪 Testing

Before relying on GhostRoute for privacy-sensitive activity, verify:

Your application actually uses the system proxy.

Your public IP is the expected Tor exit IP.

DNS behavior is appropriate for your application.

Applications that matter to you are not bypassing the proxy.

Your firewall and operating-system configuration behave as expected.

Do not assume. Verify.

📁 Project Structure
GhostRoute/
│
├── ghostroute.py
├── ghost_torrc
├── README.md
├── LICENSE
└── .gitignore

📜 License

GhostRoute is released under the MIT License.

See LICENSE for the complete license text.

👤 Author

Created as an open-source privacy and networking project.

Contributions, bug reports, and security reviews are welcome.

⚠️ Security Issues

Please do not publicly disclose serious security vulnerabilities before giving the maintainer an opportunity to investigate them.

For security-sensitive reports, use GitHub's private vulnerability reporting functionality when available.

⭐ Disclaimer in One Sentence

GhostRoute can route supported proxy-aware applications through Tor, but it is NOT a VPN, NOT a guaranteed system-wide Tor solution, and NOT a guarantee of anonymity.
