Overview

GhostRoute is a Windows-oriented GUI wrapper around a local Tor daemon and SOCKS5 proxy.

It provides:

Tor daemon start/stop controls

A local HTTP/HTTPS proxy gateway

SOCKS5 connections with hostname-based DNS resolution through Tor

Optional Windows system-proxy configuration

Tor exit-IP verification

Tor NEWNYM support

A simple Tkinter-based interface

How traffic is routed

When the system proxy is enabled, applications that respect the Windows proxy configuration can use:

Application → GhostRoute Gateway → Tor SOCKS5 → Tor network → Internet

GhostRoute is not a VPN and should not be considered a complete system-wide anonymity solution.

Applications that bypass the Windows proxy can still connect directly to the Internet.
