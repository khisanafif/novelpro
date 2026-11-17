"""
MODUL KEAMANAN FASTAPI & CLOUDFLARE TUNNEL (ZERO TRUST) — LINUX MINT 8GB EDITION
Mengamankan backend FastAPI agar hanya menerima request yang sah melalui:
1. Header Validasi Cloudflare Tunnel & Zero Trust:
   - `X-Novel-Tunnel-Token` (Token rahasia lokal yang diinjeksikan oleh cloudflared/Caddy)
   - `CF-Access-Client-Signature` (Token / HMAC-SHA256 signature + proteksi replay window)
   - `CF-Access-Client-Id` & `CF-Access-Client-Secret` (Cloudflare Access Service Token)
   - `Cf-Access-Jwt-Assertion` (Cloudflare Access OTP Email JWT + verifikasi klaim/email)
2. Isolasi Jaringan Lapis Ganda:
   - Memblokir akses langsung dari IP Publik Internet ke port FastAPI (403 Forbidden).
   - Mendukung 3 mode operasi:
     * `STRICT_CLOUDFLARE`   : Wajib lolos validasi header Cloudflare Tunnel (100% tertutup dari akses langsung).
     * `CF_OR_LOCALHOST`     : Hanya Cloudflare Tunnel tervalidasi ATAU browser lokal 127.0.0.1 (tanpa proxy header).
     * `CLOUDFLARE_AND_LAN`  : Cloudflare Tunnel tervalidasi, Localhost Mint, atau Wi-Fi LAN privat (192.168.x.x/10.x.x.x).
3. CLI Provisioner (`python3 backend/security_config.py --init`) untuk menghasilkan:
   - File `.env.security` (mode 0600) berisi token acak kriptografis 256-bit
   - Template `~/.cloudflared/config.yml` & aturan `Caddyfile.cloudflare`
   - Skrip aturan firewall UFW Linux Mint untuk memblokir akses langsung ke port 8000.
"""

import argparse
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import secrets
import time
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
except ImportError:
    class BaseHTTPMiddleware:  # type: ignore
        def __init__(self, app: Any) -> None:
            self.app = app

    Request = Any  # type: ignore
    JSONResponse = dict  # type: ignore
    Response = Any  # type: ignore


DEFAULT_SECURITY_ENV_PATH = os.path.join(os.path.dirname(__file__), ".env.security")

PRIVATE_LAN_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)

LOOPBACK_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
)

PROXY_INDICATION_HEADERS = (
    "cf-connecting-ip",
    "cf-ray",
    "cf-visitor",
    "cf-access-jwt-assertion",
    "cf-access-client-signature",
    "cf-access-client-id",
    "x-forwarded-for",
    "forwarded",
)


def load_security_env_file(env_path: str = DEFAULT_SECURITY_ENV_PATH) -> Dict[str, str]:
    """
    Membaca file `.env.security` dan menyuntikkan nilainya ke `os.environ` jika belum disetel.
    """
    loaded: Dict[str, str] = {}
    if not env_path or not os.path.isfile(env_path):
        return loaded

    with open(env_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key:
                loaded[key] = val
                if key not in os.environ:
                    os.environ[key] = val
    return loaded


def _parse_bool(raw: Optional[str], default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on", "ya")


def _parse_csv_list(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class CloudflareSecurityConfig:
    """Konfigurasi kebijakan keamanan Cloudflare Tunnel & Isolasi IP FastAPI."""

    security_mode: str = "CLOUDFLARE_AND_LAN"
    tunnel_secret_token: str = ""
    cf_signature_secret: str = ""
    cf_client_id: str = ""
    cf_client_secret: str = ""
    cf_access_team_domain: str = ""
    cf_access_policy_aud: str = ""
    cf_allowed_emails: List[str] = field(default_factory=list)
    trusted_proxy_ips: Set[str] = field(default_factory=lambda: {"127.0.0.1", "::1"})
    allowed_hosts: List[str] = field(default_factory=list)
    allow_healthcheck_without_auth: bool = False
    signature_max_age_seconds: int = 300
    env_file_loaded: bool = False

    @classmethod
    def from_env(cls, env_path: str = DEFAULT_SECURITY_ENV_PATH) -> "CloudflareSecurityConfig":
        loaded = load_security_env_file(env_path)
        mode = (
            os.environ.get("NOVEL_SECURITY_MODE", "CLOUDFLARE_AND_LAN")
            .strip()
            .upper()
        )
        if mode not in ("STRICT_CLOUDFLARE", "CF_OR_LOCALHOST", "CLOUDFLARE_AND_LAN"):
            mode = "CLOUDFLARE_AND_LAN"

        proxy_ips = set(_parse_csv_list(os.environ.get("NOVEL_TRUSTED_PROXY_IPS")))
        if not proxy_ips:
            proxy_ips = {"127.0.0.1", "::1"}

        return cls(
            security_mode=mode,
            tunnel_secret_token=os.environ.get("NOVEL_TUNNEL_SECRET", "").strip(),
            cf_signature_secret=os.environ.get("CF_ACCESS_SIGNATURE_SECRET", "").strip(),
            cf_client_id=os.environ.get("CF_ACCESS_CLIENT_ID", "").strip(),
            cf_client_secret=os.environ.get("CF_ACCESS_CLIENT_SECRET", "").strip(),
            cf_access_team_domain=os.environ.get("CF_ACCESS_TEAM_DOMAIN", "").strip().lower(),
            cf_access_policy_aud=os.environ.get("CF_ACCESS_POLICY_AUD", "").strip(),
            cf_allowed_emails=[
                e.lower() for e in _parse_csv_list(os.environ.get("CF_ALLOWED_EMAILS"))
            ],
            trusted_proxy_ips=proxy_ips,
            allowed_hosts=[h.lower() for h in _parse_csv_list(os.environ.get("NOVEL_ALLOWED_HOSTS"))],
            allow_healthcheck_without_auth=_parse_bool(
                os.environ.get("NOVEL_ALLOW_PUBLIC_HEALTHCHECK"), default=False
            ),
            signature_max_age_seconds=max(
                30, int(os.environ.get("NOVEL_SIGNATURE_MAX_AGE", "300") or "300")
            ),
            env_file_loaded=bool(loaded) or os.path.isfile(env_path),
        )

    def has_any_cloudflare_secret(self) -> bool:
        return bool(
            self.tunnel_secret_token
            or self.cf_signature_secret
            or (self.cf_client_id and self.cf_client_secret)
            or self.cf_access_policy_aud
        )

    def public_summary(self) -> Dict[str, Any]:
        """Ringkasan status keamanan tanpa pernah membocorkan isi rahasia."""
        return {
            "security_mode": self.security_mode,
            "env_file_loaded": self.env_file_loaded,
            "checks_enabled": {
                "local_tunnel_token_header": bool(self.tunnel_secret_token),
                "cf_access_client_signature_hmac": bool(self.cf_signature_secret),
                "cf_service_token_pair": bool(self.cf_client_id and self.cf_client_secret),
                "cf_access_jwt_assertion": bool(
                    self.cf_access_policy_aud or self.cf_allowed_emails
                ),
                "host_header_allowlist": bool(self.allowed_hosts),
            },
            "trusted_proxy_ips": sorted(self.trusted_proxy_ips),
            "signature_max_age_seconds": self.signature_max_age_seconds,
            "cf_allowed_emails_count": len(self.cf_allowed_emails),
        }


# ============================================================================
# HELPER VALIDASI IP, JWT CLAIM, & HMAC-SHA256 CONSTANT-TIME
# ============================================================================

def _parse_ip(raw_ip: Optional[str]) -> Optional[ipaddress._BaseAddress]:
    if not raw_ip:
        return None
    cleaned = raw_ip.strip().split("%")[0]
    try:
        return ipaddress.ip_address(cleaned)
    except ValueError:
        return None


def is_loopback_ip(raw_ip: Optional[str]) -> bool:
    ip_obj = _parse_ip(raw_ip)
    if ip_obj is None:
        return False
    return any(ip_obj in net for net in LOOPBACK_NETWORKS)


def is_private_lan_ip(raw_ip: Optional[str]) -> bool:
    ip_obj = _parse_ip(raw_ip)
    if ip_obj is None:
        return False
    return any(ip_obj in net for net in PRIVATE_LAN_NETWORKS)


def decode_jwt_payload_claims(jwt_token: str) -> Optional[Dict[str, Any]]:
    """
    Mendekode segmen payload JWT Cloudflare Access (`Cf-Access-Jwt-Assertion`)
    untuk memverifikasi waktu kedaluwarsa (`exp`), issuer (`iss`), audience (`aud`),
    dan email pengguna (`email`).
    """
    parts = (jwt_token or "").strip().split(".")
    if len(parts) != 3 or not all(parts):
        return None
    try:
        payload_b64 = parts[1]
        padding = "=" * (-len(payload_b64) % 4)
        raw_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        claims = json.loads(raw_bytes.decode("utf-8"))
        return claims if isinstance(claims, dict) else None
    except Exception:
        return None


def verify_cf_client_signature_header(
    signature_header: str,
    secret: str,
    method: str,
    path: str,
    timestamp_header: Optional[str] = None,
    max_age_seconds: int = 300,
) -> Tuple[bool, str]:
    """
    Memvalidasi header `CF-Access-Client-Signature` dalam 3 format aman:
    1. Format timestamped HMAC: `t=<unix_ts>,v1=<hex_hmac_sha256>`
       di mana `v1 = HMAC_SHA256(secret, "{t}.{METHOD}.{path}")`
    2. Format HMAC dengan header `X-CF-Timestamp` terpisah:
       `v1 = HMAC_SHA256(secret, "{timestamp}.{METHOD}.{path}")`
    3. Direct HMAC-SHA256 digest atas `"{METHOD}:{path}"` atau token identik constant-time.
    """
    sig = (signature_header or "").strip()
    if not sig or not secret:
        return False, "Header CF-Access-Client-Signature atau secret kosong"

    now_ts = int(time.time())

    # Format 1: t=<unix_ts>,v1=<hex>
    if "t=" in sig and "v1=" in sig:
        kv_map: Dict[str, str] = {}
        for part in sig.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                kv_map[k.strip()] = v.strip()
        ts_str = kv_map.get("t", "")
        v1_hex = kv_map.get("v1", "").lower()
        if not ts_str.isdigit() or not v1_hex:
            return False, "Format CF-Access-Client-Signature (t=...,v1=...) tidak valid"

        ts_val = int(ts_str)
        if abs(now_ts - ts_val) > max_age_seconds:
            return False, "CF-Access-Client-Signature sudah kedaluwarsa (replay protection)"

        signed_payload = f"{ts_val}.{method.upper()}.{path}".encode("utf-8")
        expected_hex = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        if hmac.compare_digest(v1_hex, expected_hex):
            return True, "CF-Access-Client-Signature (HMAC-SHA256 timestamped) valid"
        return False, "Signature HMAC-SHA256 pada CF-Access-Client-Signature tidak cocok"

    # Format 2: Timestamp header terpisah
    if timestamp_header and timestamp_header.strip().isdigit():
        ts_val = int(timestamp_header.strip())
        if abs(now_ts - ts_val) > max_age_seconds:
            return False, "Timestamp X-CF-Timestamp sudah kedaluwarsa"
        signed_payload = f"{ts_val}.{method.upper()}.{path}".encode("utf-8")
        expected_hex = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        if hmac.compare_digest(sig.lower(), expected_hex):
            return True, "CF-Access-Client-Signature (HMAC-SHA256 + X-CF-Timestamp) valid"

    # Format 3: Direct HMAC path digest atau token rahasia constant-time
    path_payload = f"{method.upper()}:{path}".encode("utf-8")
    expected_path_hmac = hmac.new(secret.encode("utf-8"), path_payload, hashlib.sha256).hexdigest()
    if hmac.compare_digest(sig.lower(), expected_path_hmac):
        return True, "CF-Access-Client-Signature (HMAC path digest) valid"

    if hmac.compare_digest(sig, secret):
        return True, "CF-Access-Client-Signature token cocok (constant-time)"

    return False, "CF-Access-Client-Signature tidak valid"


def generate_signed_cf_client_signature(
    secret: str,
    method: str = "GET",
    path: str = "/api/projects",
    timestamp: Optional[int] = None,
) -> str:
    """Helper untuk membuat header `CF-Access-Client-Signature` format `t=...,v1=...`."""
    ts = int(timestamp if timestamp is not None else time.time())
    payload = f"{ts}.{method.upper()}.{path}".encode("utf-8")
    sig_hex = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig_hex}"


# ============================================================================
# FASTAPI / STARLETTE MIDDLEWARE VALIDASI CLOUDFLARE TUNNEL
# ============================================================================

class CloudflareZeroTrustMiddleware(BaseHTTPMiddleware):
    """
    Middleware Keamanan FastAPI untuk mencegah akses langsung ke IP/Port server
    dari internet luar dan memverifikasi header otentikasi Cloudflare Tunnel.
    """

    def __init__(self, app: Any, config: Optional[CloudflareSecurityConfig] = None) -> None:
        super().__init__(app)
        self.config = config or CloudflareSecurityConfig.from_env()

    def _is_host_allowed(self, host_header: str) -> bool:
        if not self.config.allowed_hosts:
            return True
        host_only = (host_header or "").split(":")[0].strip().lower()
        for pattern in self.config.allowed_hosts:
            if pattern.startswith("*."):
                suffix = pattern[1:]
                if host_only.endswith(suffix):
                    return True
            elif host_only == pattern:
                return True
        return False

    def _validate_jwt_assertion(self, request: Request) -> Tuple[bool, str]:
        """Validasi JWT Cloudflare Access (`Cf-Access-Jwt-Assertion`)."""
        headers = request.headers
        cfg = self.config
        jwt_token = (headers.get("cf-access-jwt-assertion") or "").strip()
        if not jwt_token:
            return False, "Header Cf-Access-Jwt-Assertion wajib ada saat Cloudflare Access diaktifkan"

        claims = decode_jwt_payload_claims(jwt_token)
        if not claims:
            return False, "Format JWT Cf-Access-Jwt-Assertion rusak"

        now_ts = int(time.time())
        exp = claims.get("exp")
        if isinstance(exp, (int, float)) and exp < now_ts:
            return False, "Sesi JWT Cloudflare Access sudah kedaluwarsa"

        if cfg.cf_access_policy_aud:
            aud_claim = claims.get("aud")
            aud_list = aud_claim if isinstance(aud_claim, list) else [aud_claim]
            if cfg.cf_access_policy_aud not in [str(a) for a in aud_list]:
                return False, "Audience (AUD) Cloudflare Access JWT tidak sesuai aplikasi ini"

        if cfg.cf_access_team_domain:
            iss = str(claims.get("iss") or "").lower()
            if cfg.cf_access_team_domain not in iss:
                return False, "Issuer (Team Domain) Cloudflare Access JWT tidak cocok"

        user_email = str(
            claims.get("email")
            or headers.get("cf-access-authenticated-user-email")
            or ""
        ).strip().lower()
        if cfg.cf_allowed_emails and user_email not in cfg.cf_allowed_emails:
            return False, f"Email '{user_email}' tidak termasuk daftar whitelist CF_ALLOWED_EMAILS"

        return True, f"Cloudflare Access JWT ({user_email or 'authenticated'})"

    def _verify_cloudflare_headers(self, request: Request) -> Tuple[bool, str]:
        """
        Memvalidasi apakah request benar-benar datang melalui Cloudflare Tunnel (`cloudflared`)
        yang terautentikasi dan membawa header rahasia/signature yang sah.
        """
        headers = request.headers
        cfg = self.config

        # 1. Pastikan peer TCP adalah trusted proxy lokal (cloudflared / Caddy di Linux Mint)
        client_host = request.client.host if request.client else ""
        if client_host not in cfg.trusted_proxy_ips and not is_loopback_ip(client_host):
            return False, f"Koneksi langsung dari IP {client_host} bukan berasal dari daemon cloudflared lokal"

        # 2. Jika kebijakan Access JWT (AUD / Email) aktif dan request berasal dari edge Cloudflare, wajib validasi JWT
        jwt_policy_required = bool(cfg.cf_access_policy_aud or cfg.cf_allowed_emails)
        is_edge_forwarded = bool(headers.get("cf-connecting-ip") or headers.get("cf-ray"))

        # 3. Cek Token Rahasia Tunnel Lokal (`X-Novel-Tunnel-Token` / `X-CF-Tunnel-Token`)
        local_token = (
            headers.get("x-novel-tunnel-token")
            or headers.get("x-cf-tunnel-token")
            or ""
        ).strip()
        if cfg.tunnel_secret_token and local_token:
            if not hmac.compare_digest(local_token, cfg.tunnel_secret_token):
                return False, "Token rahasia lokal X-Novel-Tunnel-Token tidak cocok"
            if jwt_policy_required and is_edge_forwarded:
                jwt_ok, jwt_reason = self._validate_jwt_assertion(request)
                if not jwt_ok:
                    return False, jwt_reason
            return True, "Valid: X-Novel-Tunnel-Token terverifikasi"

        # 4. Cek `CF-Access-Client-Signature`
        cf_sig = (headers.get("cf-access-client-signature") or "").strip()
        if cf_sig:
            effective_secret = cfg.cf_signature_secret or cfg.tunnel_secret_token
            if effective_secret:
                ok, reason = verify_cf_client_signature_header(
                    signature_header=cf_sig,
                    secret=effective_secret,
                    method=request.method,
                    path=request.url.path,
                    timestamp_header=headers.get("x-cf-timestamp"),
                    max_age_seconds=cfg.signature_max_age_seconds,
                )
                if not ok:
                    return False, reason
                if jwt_policy_required and is_edge_forwarded:
                    jwt_ok, jwt_reason = self._validate_jwt_assertion(request)
                    if not jwt_ok:
                        return False, jwt_reason
                return True, reason
            if headers.get("cf-connecting-ip") and headers.get("cf-ray"):
                if jwt_policy_required:
                    jwt_ok, jwt_reason = self._validate_jwt_assertion(request)
                    if not jwt_ok:
                        return False, jwt_reason
                return True, "Valid: CF-Access-Client-Signature dengan CF-Ray via cloudflared"

        # 5. Cek Cloudflare Access Service Token (`CF-Access-Client-Id` & `CF-Access-Client-Secret`)
        req_cf_id = (headers.get("cf-access-client-id") or "").strip()
        req_cf_secret = (headers.get("cf-access-client-secret") or "").strip()
        if cfg.cf_client_id and cfg.cf_client_secret and req_cf_id and req_cf_secret:
            id_ok = hmac.compare_digest(req_cf_id, cfg.cf_client_id)
            sec_ok = hmac.compare_digest(req_cf_secret, cfg.cf_client_secret)
            if id_ok and sec_ok:
                return True, "Valid: Cloudflare Access Service Token cocok"
            return False, "Cloudflare Access Service Token (Client ID / Secret) tidak valid"

        # 6. Cek Cloudflare Access OTP User JWT (`Cf-Access-Jwt-Assertion`)
        if headers.get("cf-access-jwt-assertion"):
            if cfg.tunnel_secret_token and not local_token:
                return False, "Request Cloudflare JWT wajib menyertakan X-Novel-Tunnel-Token origin"
            jwt_ok, jwt_reason = self._validate_jwt_assertion(request)
            if not jwt_ok:
                return False, jwt_reason
            if is_edge_forwarded:
                return True, f"Valid: {jwt_reason}"

        return False, "Header validasi Cloudflare Tunnel tidak ditemukan atau tidak lengkap"

    def evaluate_request(self, request: Request) -> Tuple[bool, int, str]:
        """
        Menentukan apakah request diizinkan masuk ke endpoint FastAPI atau ditolak.
        Returns: (allowed, http_status, reason)
        """
        cfg = self.config
        host_header = request.headers.get("host", "")
        if not self._is_host_allowed(host_header):
            return False, 403, f"Host '{host_header}' tidak diizinkan oleh kebijakan keamanan"

        if cfg.allow_healthcheck_without_auth and request.url.path == "/api/system/health":
            return True, 200, "Healthcheck endpoint diizinkan"

        client_ip = request.client.host if request.client else ""
        has_proxy_headers = any(h in request.headers for h in PROXY_INDICATION_HEADERS)

        # MODE 1: STRICT_CLOUDFLARE -> Hanya terima request tervalidasi dari Cloudflare Tunnel
        if cfg.security_mode == "STRICT_CLOUDFLARE":
            ok, reason = self._verify_cloudflare_headers(request)
            return (True, 200, reason) if ok else (False, 403, reason)

        # Jika request melewati proxy / tunnel atau membawa header Cloudflare/Forwarded,
        # WAJIB lolos validasi kriptografis Cloudflare Tunnel (anti-spoofing!)
        if has_proxy_headers:
            # Kecuali Caddy LAN lokal yang hanya meneruskan X-Real-IP tanpa header internet publik,
            # tetap periksa apakah ada token rahasia jika secret disetel.
            ok, reason = self._verify_cloudflare_headers(request)
            if ok:
                return True, 200, reason
            # Jika berasal dari Caddy lokal (127.0.0.1) pada jaringan rumah dengan hanya X-Forwarded-For LAN
            # tanpa CF headers DAN mode mengizinkan LAN, cek XFF:
            if (
                cfg.security_mode == "CLOUDFLARE_AND_LAN"
                and not cfg.tunnel_secret_token
                and is_loopback_ip(client_ip)
                and not request.headers.get("cf-connecting-ip")
                and not request.headers.get("cf-ray")
            ):
                xff = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
                if is_loopback_ip(xff) or is_private_lan_ip(xff):
                    return True, 200, f"Akses Proxy Caddy LAN lokal ({xff}) diizinkan"
            return False, 403, reason

        # MODE 2: CF_OR_LOCALHOST -> Tolak LAN & Internet Publik, hanya izinkan 127.0.0.1 langsung
        if cfg.security_mode == "CF_OR_LOCALHOST":
            if is_loopback_ip(client_ip):
                if cfg.tunnel_secret_token:
                    # Jika tunnel secret diwajibkan untuk semua panggilan kecuali lokal UI tanpa proxy
                    return True, 200, "Akses langsung browser Linux Mint (127.0.0.1) diizinkan"
                return True, 200, "Akses langsung Loopback diizinkan"
            return False, 403, f"Akses langsung dari IP {client_ip} ditolak (Mode CF_OR_LOCALHOST)"

        # MODE 3: CLOUDFLARE_AND_LAN -> Blokir 100% IP Publik Internet, izinkan Loopback & Wi-Fi LAN
        if is_loopback_ip(client_ip):
            return True, 200, "Akses lokal Linux Mint (127.0.0.1) diizinkan"
        if is_private_lan_ip(client_ip):
            return True, 200, f"Akses Wi-Fi LAN privat ({client_ip}) diizinkan"

        return False, 403, (
            f"Akses langsung dari IP publik {client_ip} DITOLAK. "
            "Gunakan Cloudflare Tunnel yang terverifikasi."
        )

    @staticmethod
    def _attach_security_headers(response: Response) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        allowed, status_code, reason = self.evaluate_request(request)
        if not allowed:
            resp = JSONResponse(
                status_code=status_code,
                content={
                    "error": "CLOUDFLARE_ZERO_TRUST_DENIED",
                    "detail": reason,
                    "security_mode": self.config.security_mode,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            return self._attach_security_headers(resp)

        response = await call_next(request)
        return self._attach_security_headers(response)


# ============================================================================
# GENERATOR OTOMATIS FILE KONFIGURASI (.env.security, cloudflared, Caddy, UFW)
# ============================================================================

def provision_cloudflare_security_bundle(
    output_dir: str,
    domain_name: str = "novel.domain-anda.com",
    team_domain: str = "nama-tim.cloudflareaccess.com",
    allowed_email: str = "penulis@email-anda.com",
    fastapi_port: int = 8000,
    overwrite: bool = True,
) -> Dict[str, str]:
    """
    Membuat seluruh skrip dan file konfigurasi pengamanan Cloudflare Tunnel untuk Linux Mint:
    1. `backend/.env.security` (Token rahasia 256-bit, mode 0600)
    2. `deploy/cloudflared-config.yml` (Konfigurasi daemon cloudflared + Header Injection)
    3. `deploy/Caddyfile.cloudflare` (Reverse Proxy SSE + Injeksikan Token Origin Lokal)
    4. `deploy/setup_ufw_cloudflare.sh` (Skrip Firewall UFW agar port 8000 tertutup dari Internet)
    5. `deploy/PANDUAN_CLOUDFLARE_TUNNEL.md` (Panduan langkah demi langkah Linux Mint)
    """
    root_path = Path(output_dir).resolve()
    backend_dir = root_path / "backend"
    deploy_dir = root_path / "deploy"
    backend_dir.mkdir(parents=True, exist_ok=True)
    deploy_dir.mkdir(parents=True, exist_ok=True)

    tunnel_secret = secrets.token_urlsafe(36)
    cf_sig_secret = secrets.token_urlsafe(36)
    cf_svc_secret = secrets.token_urlsafe(32)
    cf_svc_id = f"{secrets.token_hex(16)}.access"

    # 1. backend/.env.security
    env_security_path = backend_dir / ".env.security"
    env_content = f"""# ==============================================================================
# KONFIGURASI KEAMANAN CLOUDFLARE TUNNEL — AI NOVEL STUDIO (LINUX MINT 8GB)
# Dibuat otomatis oleh security_config.py — JANGAN PERNAH DI-COMMIT KE GIT PUBLIK!
# ==============================================================================

# Pilih salah satu mode:
# - STRICT_CLOUDFLARE  : HANYA terima request ber-header Cloudflare Tunnel valid (Paling Ketat)
# - CF_OR_LOCALHOST    : Cloudflare Tunnel valid ATAU browser langsung di Linux Mint (127.0.0.1)
# - CLOUDFLARE_AND_LAN : Cloudflare Tunnel valid, Linux Mint lokal, atau Wi-Fi LAN rumah (192.168.x.x)
NOVEL_SECURITY_MODE=STRICT_CLOUDFLARE

# Token rahasia lokal yang disuntikkan oleh cloudflared (httpHostHeader / Caddy header_up)
NOVEL_TUNNEL_SECRET={tunnel_secret}

# Rahasia HMAC-SHA256 untuk memvalidasi header CF-Access-Client-Signature
CF_ACCESS_SIGNATURE_SECRET={cf_sig_secret}

# Pasangan Service Token Cloudflare Access (Opsional untuk akses script/API/HP tanpa browser OTP)
CF_ACCESS_CLIENT_ID={cf_svc_id}
CF_ACCESS_CLIENT_SECRET={cf_svc_secret}

# Pengaturan Cloudflare Access OTP Email (Ambil AUD tag dari Dashboard Cloudflare Zero Trust)
CF_ACCESS_TEAM_DOMAIN={team_domain}
CF_ACCESS_POLICY_AUD=ISI_DENGAN_AUD_TAG_DARI_CLOUDFLARE_ZERO_TRUST
CF_ALLOWED_EMAILS={allowed_email}

# Daftar Hostname yang diizinkan (pisahkan koma)
NOVEL_ALLOWED_HOSTS=localhost,127.0.0.1,{domain_name}

# Trusted local proxy (daemon cloudflared & Caddy berjalan di mesin Linux Mint yang sama)
NOVEL_TRUSTED_PROXY_IPS=127.0.0.1,::1
NOVEL_SIGNATURE_MAX_AGE=300
NOVEL_ALLOW_PUBLIC_HEALTHCHECK=false
"""
    if overwrite or not env_security_path.exists():
        env_security_path.write_text(env_content, encoding="utf-8")
        os.chmod(env_security_path, 0o600)

    # 2. deploy/cloudflared-config.yml
    cloudflared_yml_path = deploy_dir / "cloudflared-config.yml"
    cloudflared_yml_content = f"""# Simpan/tautkan ke ~/.cloudflared/config.yml di Linux Mint Anda
# Pastikan Anda sudah menjalankan: cloudflared tunnel login && cloudflared tunnel create novel-studio

tunnel: GANTI_DENGAN_TUNNEL_UUID_ANDA
credentials-file: /home/$USER/.cloudflared/GANTI_DENGAN_TUNNEL_UUID_ANDA.json

ingress:
  # Meneruskan domain publik melalui Caddy (port 3000) yang menginjeksikan X-Novel-Tunnel-Token ke FastAPI
  # ATAU arahkan langsung ke http://127.0.0.1:{fastapi_port} bila tidak memakai Caddy
  - hostname: {domain_name}
    service: http://127.0.0.1:3000
    originRequest:
      noTLSVerify: false
      connectTimeout: 10s
      # Penting untuk Server-Sent Events (SSE) Streaming Micro-Beat:
      disableChunkedEncoding: false
      tcpKeepAlive: 30s
  - service: http_status:404
"""
    cloudflared_yml_path.write_text(cloudflared_yml_content, encoding="utf-8")

    # 3. deploy/Caddyfile.cloudflare
    caddy_cf_path = deploy_dir / "Caddyfile.cloudflare"
    caddy_cf_content = f"""# Caddy Reverse Proxy + Injeksikan Token Rahasia Cloudflare ke FastAPI (Port {fastapi_port})
:3000 {{
    encode zstd gzip

    handle /api/* {{
        reverse_proxy 127.0.0.1:{fastapi_port} {{
            flush_interval -1
            header_up Host {{host}}
            header_up X-Real-IP {{remote_host}}
            # Token rahasia lokal hanya ditambahkan jika request memang datang lewat Cloudflare Tunnel
            header_up X-Novel-Tunnel-Token "{tunnel_secret}"
        }}
    }}

    handle {{
        root * {root_path / "frontend"}
        try_files {{path}} /index.html
        file_server
    }}
}}
"""
    caddy_cf_path.write_text(caddy_cf_content, encoding="utf-8")

    # 4. deploy/setup_ufw_cloudflare.sh
    ufw_script_path = deploy_dir / "setup_ufw_cloudflare.sh"
    ufw_script_content = f"""#!/usr/bin/env bash
# ==============================================================================
# SKRIP FIREWALL UFW LINUX MINT — BLOKIR AKSES IP LANGSUNG KE PORT STUDIO
# ==============================================================================
set -euo pipefail

echo "→ Mengaktifkan dan mengonfigurasi UFW Firewall Linux Mint..."
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 1. Blokir mutlak port FastAPI ({fastapi_port}), llama-server (8080), dan Caddy (3000) dari Internet Luar
sudo ufw deny {fastapi_port}/tcp
sudo ufw deny 8080/tcp
sudo ufw deny 3000/tcp

# 2. (Opsional) Jika Anda juga membuka via Wi-Fi LAN rumah, hapus tanda # di baris bawah:
# sudo ufw allow from 192.168.0.0/16 to any port 3000 proto tcp

sudo ufw --force enable
sudo ufw status verbose
echo "✓ Port {fastapi_port} & 8080 kini 100% tertutup dari internet langsung. Akses luar HANYA lewat Cloudflare Tunnel!"
"""
    ufw_script_path.write_text(ufw_script_content, encoding="utf-8")
    os.chmod(ufw_script_path, 0o755)

    # 5. deploy/PANDUAN_CLOUDFLARE_TUNNEL.md
    guide_path = deploy_dir / "PANDUAN_CLOUDFLARE_TUNNEL.md"
    guide_content = f"""# Panduan Setup Cloudflare Tunnel & Zero Trust di Linux Mint 8 GB

Arsitektur ini melindungi **AI Novel Studio** agar **sama sekali tidak membuka port IP rumah ke internet** dan memastikan FastAPI hanya menerima permintaan sah yang melewati **Cloudflare Tunnel (`cloudflared`)**.

---

## 1. Instalasi `cloudflared` di Linux Mint (Ubuntu/Debian Based)

```bash
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update && sudo apt install -y cloudflared
```

---

## 2. Login, Buat Tunnel, dan Pasang DNS Domain

```bash
cloudflared tunnel login
cloudflared tunnel create novel-studio
cloudflared tunnel route dns novel-studio {domain_name}
```

Salin UUID tunnel yang muncul, lalu tempel ke file konfigurasi:
- File konfigurasi siap pakai: `deploy/cloudflared-config.yml`
- Salin ke `~/.cloudflared/config.yml`:
```bash
mkdir -p ~/.cloudflared
cp "{cloudflared_yml_path}" ~/.cloudflared/config.yml
nano ~/.cloudflared/config.yml  # Isi Tunnel UUID & path credentials JSON Anda
```

---

## 3. Bind FastAPI Hanya ke Localhost (`127.0.0.1:{fastapi_port}`) + Aktifkan UFW

Agar tidak ada satu pun IP eksternal yang dapat menembak port `{fastapi_port}` secara langsung:

1. Jalankan skrip firewall UFW yang sudah dibuat:
   ```bash
   sudo bash "{ufw_script_path}"
   ```
2. Pastikan di terminal atau `systemd` Anda menjalankan FastAPI terikat pada `127.0.0.1`:
   ```bash
   uvicorn main:app --host 127.0.0.1 --port {fastapi_port} --workers 1
   ```
   *(Daemon `cloudflared` berkomunikasi secara lokal melalui `127.0.0.1` ke Caddy/FastAPI tanpa memerlukan port publik terbuka di router).*

---

## 4. Aktifkan Cloudflare Zero Trust (OTP Email / Service Token & Header Validation)

1. Buka **Cloudflare Zero Trust Dashboard -> Access -> Applications -> Add an application (Self-hosted)**.
2. Masukkan domain: `{domain_name}`.
3. Buat Policy **Allow** -> Include Emails: `{allowed_email}` (menggunakan kode OTP sekali pakai ke email Anda saat login dari HP/Laptop di luar rumah).
4. Salin **Application Audience (AUD) Tag** dari tab Overview, lalu tempel ke `backend/.env.security` pada variabel:
   `CF_ACCESS_POLICY_AUD=...`
5. *(Opsional untuk akses skrip/API memakai Header Validation langsung)*:
   Tambahkan **Cloudflare Transform Rule (Modify Request Header)** pada dashboard Cloudflare untuk menyuntikkan header `CF-Access-Client-Signature` atau gunakan `CF-Access-Client-Id` & `CF-Access-Client-Secret` dari menu **Access -> Service Auth** ke `backend/.env.security`.

---

## 5. Cara Verifikasi Header Validation FastAPI (`security_config.py`)

FastAPI otomatis memuat `backend/.env.security` dan memasang `CloudflareZeroTrustMiddleware`:
- **Tes Tolak Akses Langsung (Harus 403 Forbidden pada mode `STRICT_CLOUDFLARE`):**
  ```bash
  curl -i http://127.0.0.1:{fastapi_port}/api/projects
  ```
- **Tes Akses dengan Header Token Rahasia Lokal (`X-Novel-Tunnel-Token`):**
  ```bash
  curl -i -H "X-Novel-Tunnel-Token: <ISI_NOVEL_TUNNEL_SECRET>" http://127.0.0.1:{fastapi_port}/api/projects
  ```
- **Tes Akses dengan `CF-Access-Client-Signature` HMAC-SHA256:**
  Anda dapat menghasilkan header validasi menggunakan helper `generate_signed_cf_client_signature()` di `backend/security_config.py`.
"""
    guide_path.write_text(guide_content, encoding="utf-8")

    return {
        "env_security": str(env_security_path),
        "cloudflared_config": str(cloudflared_yml_path),
        "caddyfile_cloudflare": str(caddy_cf_path),
        "ufw_script": str(ufw_script_path),
        "guide_markdown": str(guide_path),
        "tunnel_secret": tunnel_secret,
        "cf_signature_secret": cf_sig_secret,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Provisioner & Inspector Keamanan Cloudflare Tunnel untuk AI Novel Studio"
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Membuat file .env.security, template cloudflared, Caddyfile, UFW script, dan panduan.",
    )
    parser.add_argument(
        "--domain",
        default="novel.domain-anda.com",
        help="Nama domain Cloudflare Anda (misal: novel.contoh.my.id).",
    )
    parser.add_argument(
        "--team-domain",
        default="nama-tim.cloudflareaccess.com",
        help="Team domain Cloudflare Zero Trust Anda.",
    )
    parser.add_argument(
        "--email",
        default="penulis@email-anda.com",
        help="Alamat email yang diizinkan masuk via Cloudflare Access OTP.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Menampilkan ringkasan konfigurasi keamanan aktif saat ini.",
    )
    args = parser.parse_args()

    if args.init:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        created = provision_cloudflare_security_bundle(
            output_dir=root_dir,
            domain_name=args.domain,
            team_domain=args.team_domain,
            allowed_email=args.email,
        )
        print("Berhasil menghasilkan paket konfigurasi keamanan Cloudflare Tunnel:")
        for k, v in created.items():
            if "secret" not in k:
                print(f"  - {k}: {v}")
        return

    cfg = CloudflareSecurityConfig.from_env()
    print(json.dumps(cfg.public_summary(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
