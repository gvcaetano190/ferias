param(
    [Parameter(Mandatory = $true)]
    [string]$UsuarioAd
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"
$grupoVpn = "Printi_Acesso"

try {
    Import-Module ActiveDirectory

    $user = Get-ADUser -Identity $UsuarioAd -Properties SamAccountName, Enabled
    if (-not $user) {
        throw "Usuario nao encontrado no AD"
    }

    $isInPrintiAcesso = $false
    $groups = Get-ADPrincipalGroupMembership -Identity $user.SamAccountName | Select-Object -ExpandProperty Name
    if ($groups -contains $grupoVpn) {
        $isInPrintiAcesso = $true
    }

    $adStatus = if ([bool]$user.Enabled) { "LIBERADO" } else { "BLOQUEADO" }
    $vpnStatus = if ($isInPrintiAcesso) { if ([bool]$user.Enabled) { "LIBERADA" } else { "BLOQUEADA" } } else { "NP" }

    @{
        success = $true
        usuario_ad = $user.SamAccountName
        user_found = $true
        ad_status = $adStatus
        vpn_status = $vpnStatus
        is_enabled = [bool]$user.Enabled
        is_in_printi_acesso = $isInPrintiAcesso
        already_in_desired_state = $false
        message = "Consulta AD realizada com sucesso"
    } | ConvertTo-Json -Compress
}
catch {
    @{
        success = $false
        usuario_ad = $UsuarioAd
        user_found = $false
        ad_status = "ERRO"
        vpn_status = "NP"
        is_enabled = $false
        is_in_printi_acesso = $false
        already_in_desired_state = $false
        message = $_.Exception.Message
    } | ConvertTo-Json -Compress
}
