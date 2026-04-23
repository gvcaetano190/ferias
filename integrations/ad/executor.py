from __future__ import annotations

import json
import subprocess
from pathlib import Path


AD_DIR = Path(__file__).resolve().parent


def bloquear_usuario_ad(usuario_ad: str) -> dict:
    return _run_powershell_script("bloquear_usuario.ps1", usuario_ad)


def desbloquear_usuario_ad(usuario_ad: str) -> dict:
    return _run_powershell_script("desbloquear_usuario.ps1", usuario_ad)


def _run_powershell_script(script_name: str, usuario_ad: str) -> dict:
    script_path = AD_DIR / script_name
    command = [
        "pwsh",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-UsuarioAd",
        usuario_ad,
    ]

    try:
        # O PowerShell retorna JSON para o Python fazer parse com segurança.
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except FileNotFoundError:
        return _error_result(usuario_ad, "PowerShell (`pwsh`) não encontrado no ambiente.")
    except subprocess.SubprocessError as exc:
        return _error_result(usuario_ad, f"Falha ao executar PowerShell: {exc}")

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if not stdout:
        return _error_result(usuario_ad, stderr or "Script não retornou saída JSON.")

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return _error_result(usuario_ad, f"Saída inválida do script: {stdout}")

    if stderr and payload.get("success"):
        payload["message"] = f"{payload.get('message', '')} | stderr: {stderr}".strip(" |")

    return {
        "success": bool(payload.get("success")),
        "usuario_ad": payload.get("usuario_ad", usuario_ad),
        "ad_status": payload.get("ad_status", "ERRO"),
        "vpn_status": payload.get("vpn_status", "NP"),
        "message": payload.get("message", stderr or "Sem mensagem"),
        "user_found": bool(payload.get("user_found", False)),
        "is_in_printi_acesso": bool(payload.get("is_in_printi_acesso", False)),
    }


def _error_result(usuario_ad: str, message: str) -> dict:
    return {
        "success": False,
        "usuario_ad": usuario_ad,
        "ad_status": "ERRO",
        "vpn_status": "NP",
        "message": message,
        "user_found": False,
        "is_in_printi_acesso": False,
    }
