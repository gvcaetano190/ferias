param(
    [Parameter(Mandatory = $true)]
    [string]$UsuariosJson
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

try {
    $usuarios = @($UsuariosJson | ConvertFrom-Json)
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
                throw "Usuário não encontrado no AD"
            }

            $isInPrintiAcesso = $false
            $groups = Get-ADPrincipalGroupMembership -Identity $user.SamAccountName | Select-Object -ExpandProperty Name
            if ($groups -contains $grupoVpn) {
                $isInPrintiAcesso = $true
            }

            $vpnStatus = if ($isInPrintiAcesso) { "BLOQUEADA" } else { "NP" }
            $alreadyBlocked = -not [bool]$user.Enabled

            if (-not $alreadyBlocked) {
                Disable-ADAccount -Identity $user.SamAccountName
            }

            $results.Add(@{
                success = $true
                usuario_ad = $user.SamAccountName
                user_found = $true
                is_in_printi_acesso = $isInPrintiAcesso
                ad_status = "BLOQUEADO"
                vpn_status = $vpnStatus
                already_in_desired_state = $alreadyBlocked
                message = $(if ($alreadyBlocked) { "Usuário já estava bloqueado no AD" } else { "Usuário bloqueado com sucesso em lote" })
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
