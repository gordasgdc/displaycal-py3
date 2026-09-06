# generate-self-signed-cert.ps1
#
# Rulat O SINGURA DATA, de Cristi, pe Windows real (nu de Claude - un
# certificat cu cheie privata nu trece niciodata prin conversatie, vezi
# CLAUDE.md, Regula 34). Genereaza un certificat Self-Signed de Code
# Signing STABIL (valabil 5 ani) - NU se regenereaza la fiecare build,
# ca sa nu rupa increderea deja acordata de colaboratori (fiecare
# certificat nou ar cere re-import in Trusted Root pe toate masinile lor).
#
# Foloseste:
#   1. Ruleaza acest script o data (PowerShell, ca Administrator).
#   2. Produce doua fisiere in acelasi folder:
#      - displaycal-cg-selfsign.pfx  (PRIVAT, cu cheie - NU se distribuie,
#        NU se comite in git, NU se lipeste in chat/conversatie)
#      - displaycal-cg-selfsign.cer  (PUBLIC, fara cheie - se distribuie
#        colaboratorilor pentru import manual in Trusted Root)
#   3. Incarca .pfx-ul ca secrete GitHub Actions (comenzile exacte sunt
#      afisate la finalul scriptului) - asta il face disponibil in CI
#      pentru fiecare build viitor, fara sa mai repeti acest pas.

$ErrorActionPreference = "Stop"

$subject = "CN=DisplayCAL-CG (Self-Signed, testare interna)"
$pfxPath = Join-Path $PSScriptRoot "displaycal-cg-selfsign.pfx"
$cerPath = Join-Path $PSScriptRoot "displaycal-cg-selfsign.cer"
$pfxPassword = Read-Host -Prompt "Alege o parola noua pentru fisierul .pfx (o vei pune ca secret CI)" -AsSecureString

Write-Host "==> Generez certificatul self-signed (valabil 5 ani)..."
$cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject $subject `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -NotAfter (Get-Date).AddYears(5) `
    -KeyUsage DigitalSignature `
    -KeyAlgorithm RSA `
    -KeyLength 2048

Write-Host "==> Exporting .pfx (PRIVAT - nu distribui acest fisier)..."
Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $pfxPassword | Out-Null

Write-Host "==> Exporting .cer (PUBLIC - acesta se distribuie colaboratorilor)..."
Export-Certificate -Cert $cert -FilePath $cerPath | Out-Null

Write-Host ""
Write-Host "==> Gata:"
Write-Host "    $pfxPath  (PRIVAT - foloseste-l DOAR pentru pasii de mai jos, apoi sterge-l local)"
Write-Host "    $cerPath  (PUBLIC - trimite-l colaboratorilor)"
Write-Host ""
Write-Host "==> Urmatorul pas - incarca secretele in GitHub Actions (necesita 'gh' CLI autentificat):"
Write-Host ""
Write-Host '    $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("' -NoNewline
Write-Host "$pfxPath" -NoNewline
Write-Host '"))'
Write-Host '    gh secret set WIN_SELFSIGN_PFX_BASE64 --repo gordasgdc/displaycal-py3 --body $b64'
Write-Host '    gh secret set WIN_SELFSIGN_PFX_PASSWORD --repo gordasgdc/displaycal-py3'
Write-Host "    (al doilea comand cere parola interactiv - foloseste ACEEASI parola aleasa mai sus)"
Write-Host ""
Write-Host "==> Dupa ce secretele sunt incarcate, sterge fisierul .pfx local:"
Write-Host "    Remove-Item `"$pfxPath`" -Force"
Write-Host ""
Write-Host "==> Distribuie $cerPath colaboratorilor. Import manual pe masinile lor:"
Write-Host "    dublu-click pe .cer -> Install Certificate -> Local Machine ->"
Write-Host "    'Place all certificates in the following store' -> Trusted Root Certification Authorities."
