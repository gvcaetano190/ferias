param(
    [Parameter(Mandatory = $true)]
    [string]$UsuarioAd
)

$ErrorActionPreference = "Stop"

try {
    Import-Module ActiveDirectory

    $user = Get-ADUser -Identity $UsuarioAd -Properties SamAccountName
    if (-not $user) {
        throw "Usuário não encontrado no AD"
    }

    Enable-ADAccount -Identity $user.SamAccountName

    @{
        success = $true
        usuario_ad = $user.SamAccountName
        user_found = $true
        ad_status = "LIBERADO"
        vpn_status = "NP"
        message = "Usuário desbloqueado com sucesso"
    } | ConvertTo-Json -Compress
}
catch {
    @{
        success = $false
        usuario_ad = $UsuarioAd
        user_found = $false
        ad_status = "ERRO"
        vpn_status = "NP"
        message = $_.Exception.Message
    } | ConvertTo-Json -Compress
}
