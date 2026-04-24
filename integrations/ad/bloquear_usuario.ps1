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

    $user = Get-ADUser -Identity $UsuarioAd -Properties MemberOf, SamAccountName, Enabled
    if (-not $user) {
        throw "Usuário não encontrado no AD"
    }

    # A regra da VPN depende da presença do usuário no grupo Printi_Acesso.
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

    @{
        success = $true
        usuario_ad = $user.SamAccountName
        user_found = $true
        is_in_printi_acesso = $isInPrintiAcesso
        ad_status = "BLOQUEADO"
        vpn_status = $vpnStatus
        already_in_desired_state = $alreadyBlocked
        message = $(if ($alreadyBlocked) { "Usuário já estava bloqueado no AD" } else { "Usuário bloqueado com sucesso" })
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
        already_in_desired_state = $false
        message = $_.Exception.Message
    } | ConvertTo-Json -Compress
}
