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

    $user = Get-ADUser -Identity $UsuarioAd -Properties SamAccountName, MemberOf, Enabled
    if (-not $user) {
        throw "Usuário não encontrado no AD"
    }

    # No desbloqueio, se o usuário ainda pertence ao grupo Printi_Acesso,
    # entendemos que o acesso VPN volta junto com a reativação do AD.
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

    @{
        success = $true
        usuario_ad = $user.SamAccountName
        user_found = $true
        ad_status = "LIBERADO"
        is_in_printi_acesso = $isInPrintiAcesso
        vpn_status = $vpnStatus
        already_in_desired_state = $alreadyEnabled
        message = $(if ($alreadyEnabled) { "Usuário já estava liberado no AD" } else { "Usuário desbloqueado com sucesso" })
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
