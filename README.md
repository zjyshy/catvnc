# CatVNC Remote Control Project State

Last updated: 2026-06-29

## Goal

Build a website where each user logs in and controls their bound phone.

## Current Verified Architecture

- iPhone 8 jailbroken device runs CatVNC.
- CatVNC exposes a local web page on `localhost:5800`.
- The iPhone opens an SSH reverse tunnel to Ubuntu server `39.106.125.238`.
- Nginx on the server proxies public access to the CatVNC tunnel.
- Coturn runs on the same Ubuntu server for WebRTC relay.

## Current Public Entry

- Public page: `http://39.106.125.238:18888/`
- Nginx config: `/etc/nginx/conf.d/catvnc.conf`
- Reverse tunnel target on server: `127.0.0.1:15901`
- CatVNC upstream on iPhone: `localhost:5800`

## SSH Tunnel

Working reverse tunnel shape:

```bash
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -R 127.0.0.1:15901:0.0.0.0:5800 root@39.106.125.238
```

Earlier note: using the wrong public IP caused SSH failure. The correct server IP is `39.106.125.238`.

## Verified Facts

- Nginx reverse proxy works.
- SSH reverse tunnel works.
- CatVNC itself works.
- Direct local forward test from Windows worked and showed the screen:

```powershell
ssh -N -L 18080:127.0.0.1:15901 root@39.106.125.238
```

Then visiting `http://127.0.0.1:18080/` displayed the iPhone screen.

This proved the blank-screen issue was not caused by CatVNC itself or the SSH tunnel.

## Original Problem

On mobile data, the control page loaded and taps/swipes worked, but the screen area was blank.

Observed behavior:

- HTTP page loaded.
- Static assets loaded.
- `/ws` WebSocket connected with HTTP `101`.
- Click/touch control worked.
- Screen video was blank.

This meant signaling/control worked, but WebRTC media failed.

## WebRTC Evidence

CatVNC frontend bundle contains:

```text
RTCPeerConnection
iceServers
candidate
offer
answer
WebSocket
```

Original CatVNC frontend ICE config only had STUN:

```js
iceServers:[
  {urls:"stun:stun.chat.bilibili.com:3478"},
  {urls:"stun:stun.l.google.com:19302"}
]
```

## Coturn State

Coturn is installed and running on the Ubuntu server.

Important `/etc/turnserver.conf` values verified during debugging:

```conf
listening-ip=172.17.82.174
relay-ip=172.17.82.174
external-ip=39.106.125.238/172.17.82.174
min-port=49160
max-port=49200
fingerprint
lt-cred-mech
realm=catvnc
user=catvnc:1q2w3e4r
```

Security group was opened for:

```text
3478 TCP/UDP
49160-49200 TCP/UDP
```

Coturn logs showed successful allocation:

```text
ALLOCATE processed, success
Local relay addr: 172.17.82.174:49xxx
```

## Key Diagnosis

Adding TURN alone was not enough because CatVNC sent private ICE candidates to the browser:

```text
10.213.240.81
192.168.1.124
```

The real iPhone public egress IP observed from the SSH tunnel was:

```text
123.124.217.250
```

Tcpdump showed the iPhone sending WebRTC packets from:

```text
123.124.217.250:5800
```

to the coturn relay port:

```text
172.17.82.174:49xxx
```

But coturn permissions were being created for the private peer IPs, not the real public source IP. So coturn received packets from the iPhone but did not relay them to the browser correctly.

## Working Temporary Fix

Nginx `sub_filter` was used to patch the CatVNC frontend JS.

The patch does two things:

1. Replaces original STUN-only `iceServers` with TURN config.
2. Rewrites private ICE candidate IPs in frontend handling before calling:
   - `setRemoteDescription`
   - `addIceCandidate`

The exact JS hook strings exist in the bundle:

```js
await u.setRemoteDescription(i.body);
await u.addIceCandidate(i.body);
```

Working candidate rewrite idea:

```nginx
sub_filter 'await u.setRemoteDescription(i.body);' 'i.body.sdp&&(i.body.sdp=i.body.sdp.split("10.213.240.81").join("123.124.217.250").split("192.168.1.124").join("123.124.217.250"));await u.setRemoteDescription(i.body);';

sub_filter 'await u.addIceCandidate(i.body);' 'i.body&&i.body.candidate&&(i.body.candidate=i.body.candidate.split("10.213.240.81").join("123.124.217.250").split("192.168.1.124").join("123.124.217.250"));await u.addIceCandidate(i.body);';
```

After this, the mobile-data blank screen was fixed.

## Important Caveats

- This is a temporary workaround.
- `123.124.217.250` is hard-coded and can change.
- The TURN password has been exposed during debugging and should be rotated.
- Final product should not expose long-lived static TURN credentials in frontend JS.
- `iceTransportPolicy:"relay"` was tested and caused WiFi to go blank when TURN/candidate handling was not yet fully correct, so it was removed.

## Production Direction

The correct product architecture should add a backend signaling layer:

- User login.
- Device binding.
- Per-device tunnel/session tracking.
- Dynamic TURN credentials.
- Dynamic ICE candidate rewrite or proper WebRTC signaling relay.
- Avoid hard-coded public IPs in nginx.
- Avoid fixed TURN password in frontend.

Recommended next architecture:

1. Each phone agent/tunnel registers to backend with a device ID.
2. Backend tracks current server-side tunnel port and observed public egress IP.
3. User logs in and selects a bound device.
4. Backend proxies CatVNC HTTP/WebSocket for that device.
5. Backend rewrites WebRTC ICE candidates dynamically or terminates/re-signals WebRTC.
6. Backend issues short-lived TURN credentials per viewing session.

## Useful Commands

Find CatVNC asset:

```bash
asset=$(curl -s http://127.0.0.1:15901/ | grep -oE '/assets/index-[^"]+\.js' | head -n 1)
```

Check WebRTC bundle markers:

```bash
curl -s "http://127.0.0.1:15901$asset" | grep -Eo 'RTCPeerConnection|iceServers|candidate|offer|answer|WebSocket' | sort -u
```

Verify nginx-patched JS:

```bash
asset=$(curl -s http://127.0.0.1:18888/ | grep -oE '/assets/index-[^"]+\.js' | head -n 1)
curl -s "http://127.0.0.1:18888$asset" | grep -o '123.124.217.250' | head
```

Watch coturn:

```bash
sudo journalctl -u coturn -f
```

Find which SSH connection owns reverse tunnel port:

```bash
sudo ss -lntp | grep ':15901'
sudo ss -tnp '( sport = :22 )'
```

Watch iPhone WebRTC traffic to TURN relay:

```bash
sudo tcpdump -ni any 'host 123.124.217.250 and (udp port 3478 or tcp port 3478 or udp portrange 49160-49200 or tcp portrange 49160-49200)'
```

## Resume Prompt

Use this context:

CatVNC on a jailbroken iPhone is exposed through SSH reverse tunnel to Ubuntu server `39.106.125.238`. Nginx proxies public `18888` to `127.0.0.1:15901`. The mobile-data blank-screen issue was caused by WebRTC ICE candidates using private IPs. Coturn works. A temporary nginx `sub_filter` patch rewrites private candidate IPs to the iPhone current public egress IP and fixes the screen. Next step is to turn this into a proper multi-user website with login, device binding, dynamic signaling proxy/candidate rewrite, and short-lived TURN credentials.

## Product Decision: Single Active Controller

After the blank-screen fix, multi-client simultaneous control was no longer required.

Final product rule:

- One bound phone can have only one active controller session at a time.
- This should be implemented intentionally in the backend, not by relying on current CatVNC/nginx behavior.
- Backend should grant an exclusive control lease when a user enters a device page.
- Other users should see the device as busy, or wait until the current session exits/times out.
- The lease should be released on WebSocket disconnect, explicit exit, heartbeat timeout, or admin force release.

Suggested implementation later:

- `devices` table tracks owner/binding/offline state.
- `control_sessions` table tracks active user/device/session.
- Enforce one active session per device with a unique active lock or transactional lease.
- Only the active session holder can send touch/control WebSocket messages.
- Optional future feature: allow read-only viewers while keeping control exclusive.

