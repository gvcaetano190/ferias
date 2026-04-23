param(
    [Parameter(Mandatory = $true)]
    [string]$UsuarioAd
)

$ErrorActionPreference = "Stop"
$grupoVpn = "Printi_Acesso"

try {
    Import-Module ActiveDirectory

    $user = Get-ADUser -Identity $UsuarioAd -Properties MemberOf, SamAccountName
    if (-not $user) {
        throw "Usuário não encontrado no AD"
    }

    # A regra da VPN depende da presença do usuário no grupo Printi_Acesso.
    $isInPrintiAcesso = $false
    $groups = Get-ADPrincipalGroupMembership -Identity $user.SamAccountName | Select-Object -ExpandProperty Name
    if ($groups -contains $grupoVpn) {
        $isInPrintiAcesso = $true
    }

    Disable-ADAccount -Identity $user.SamAccountName

    $vpnStatus = if ($isInPrintiAcesso) { "BLOQUEADA" } else { "NP" }

    @{
        success = $true
        usuario_ad = $user.SamAccountName
        user_found = $true
        is_in_printi_acesso = $isInPrintiAcesso
        ad_status = "BLOQUEADO"
        vpn_status = $vpnStatus
        message = "Usuário bloqueado com sucesso"
    } | ConvertTo-Json -Compress
}
catch {
    @{
        success = $false
        usuario_ad = $UsuarioAd
        user_found = $false
        is_in_printi_acesso = $false
        ad_status = "ERRO"
        vpn_status = "NP"
        message = $_.Exception.Message
    } | ConvertTo-Json -Compress
}
