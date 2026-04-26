param(
    [Parameter(Mandatory = $false)]
    [string]$UsuariosJson,

    [Parameter(Mandatory = $false)]
    [string]$UsuariosBase64
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"
$grupoVpn = "Printi_Acesso"

function New-ErrorPayload {
    param(
        [string]$UsuarioAd,
        [string]$Message
    )

    return @{
        success = $false
        usuario_ad = $UsuarioAd
        user_found = $false
        ad_status = "ERRO"
        vpn_status = "NP"
        is_enabled = $false
        is_in_printi_acesso = $false
        already_in_desired_state = $false
        message = $Message
    }
}

function Get-UsuariosPayload {
    if (-not [string]::IsNullOrWhiteSpace($UsuariosBase64)) {
        $json = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($UsuariosBase64))
        return [string[]]($json | ConvertFrom-Json)
    }

    if (-not [string]::IsNullOrWhiteSpace($UsuariosJson)) {
        return [string[]]($UsuariosJson | ConvertFrom-Json)
    }

    throw "Nenhum payload de usuarios foi informado."
}

try {
    $usuarios = Get-UsuariosPayload
    Import-Module ActiveDirectory
    $results = New-Object System.Collections.Generic.List[object]

    foreach ($usuario in $usuarios) {
        $usuarioAd = [string]$usuario
        if ([string]::IsNullOrWhiteSpace($usuarioAd)) {
            $results.Add((New-ErrorPayload -UsuarioAd $usuarioAd -Message "Usuario AD vazio."))
            continue
        }

        try {
            $user = Get-ADUser -Identity $usuarioAd -Properties MemberOf, SamAccountName, Enabled
            if (-not $user) {
                throw "Usuario nao encontrado no AD"
            }

            $isInPrintiAcesso = $false
            $groups = Get-ADPrincipalGroupMembership -Identity $user.SamAccountName | Select-Object -ExpandProperty Name
            if ($groups -contains $grupoVpn) {
                $isInPrintiAcesso = $true
            }

            $vpnStatus = if ($isInPrintiAcesso) { "LIBERADA" } else { "NP" }
            $alreadyEnabled = [bool]$user.Enabled

            if (-not $alreadyEnabled) {
                Enable-ADAccount -Identity $user.SamAccountName
            }

            $results.Add(@{
                success = $true
                usuario_ad = $user.SamAccountName
                user_found = $true
                is_in_printi_acesso = $isInPrintiAcesso
                ad_status = "LIBERADO"
                vpn_status = $vpnStatus
                already_in_desired_state = $alreadyEnabled
                message = $(if ($alreadyEnabled) { "Usuario ja estava liberado no AD" } else { "Usuario desbloqueado com sucesso em lote" })
            })
        }
        catch {
            $results.Add((New-ErrorPayload -UsuarioAd $usuarioAd -Message $_.Exception.Message))
        }
    }

    $results | ConvertTo-Json -Compress
}
catch {
    @(
        (New-ErrorPayload -UsuarioAd "" -Message $_.Exception.Message)
    ) | ConvertTo-Json -Compress
}
