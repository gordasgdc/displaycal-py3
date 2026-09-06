# codesigning/ — semnare Windows (Self-Signed, testare internă)

DisplayCAL-CG semnează `.pkg`-ul macOS separat (Developer ID real +
notarizare, vezi `build_pkg.sh` — neatins de acest document). Acest folder
acoperă DOAR partea Windows, adăugată 2026-09-06 (CLAUDE.md, Regula 34),
aplicând pattern-ul deja folosit în CGConvertor (`codesigning/README-windows.md`
din acel repo).

## De ce Self-Signed, și ce NU rezolvă

Un certificat self-signed **nu elimină avertismentul SmartScreen/"Unknown
publisher"** pentru publicul larg — doar un certificat real de la o CA
publică (cu reputație acumulată) sau un certificat EV fac asta. Self-signed
e util STRICT pentru:
- testare internă (buildurile pe care le rulează Cristi însuși),
- distribuire către un cerc restrâns de colaboratori care importă manual
  certificatul public (`.cer`) în Trusted Root o singură dată.

Aceasta e o stare tranzitorie deja documentată în CLAUDE.md ("Windows:
fără certificat de semnare cod încă — installer rămâne nesemnat la
primul release, SmartScreen va avertiza, acceptat ca stare tranzitorie") —
acest folder o îmbunătățește (semnătură Authenticode prezentă, utilă
pentru cercul restrâns care importă `.cer`), fără să pretindă că rezolvă
SmartScreen pentru publicul larg. La lansare publică mai amplă, planul e
Azure Trusted Signing sau un certificat EV (HSM cloud).

## Setup unic (o dată, făcut DIRECT de Cristi pe Windows real)

Certificatul (privat, cu cheie) nu trece niciodată prin conversația cu
Claude — la fel ca orice altă parolă/cheie din ecosistem.

1. Pe Windows real (Parallels e suficient), deschide PowerShell **ca
   Administrator** și rulează:
   ```powershell
   .\codesigning\generate-self-signed-cert.ps1
   ```
   Scriptul cere o parolă nouă (pentru `.pfx`) și produce două fișiere:
   - `displaycal-cg-selfsign.pfx` — **PRIVAT**, nu se distribuie, nu se
     comite în git.
   - `displaycal-cg-selfsign.cer` — **PUBLIC**, se distribuie colaboratorilor.

2. Încarcă `.pfx`-ul ca secrete GitHub Actions — comenzile exacte sunt
   afișate la finalul scriptului (necesită `gh` CLI autentificat pe acea
   mașină):
   ```powershell
   gh secret set WIN_SELFSIGN_PFX_BASE64 --repo gordasgdc/displaycal-py3 --body $b64
   gh secret set WIN_SELFSIGN_PFX_PASSWORD --repo gordasgdc/displaycal-py3
   ```

3. Șterge `.pfx`-ul local imediat după (`Remove-Item displaycal-cg-selfsign.pfx -Force`)
   — rămâne doar în secretele CI, criptate.

4. Distribuie `displaycal-cg-selfsign.cer` colaboratorilor. Pe fiecare
   mașină a lor, o singură dată: dublu-click → **Install Certificate** →
   **Local Machine** → "Place all certificates in the following store" →
   **Trusted Root Certification Authorities**.

Odată făcuți pașii 1-4, **fiecare build viitor din CI** (tag nou
`vX.Y.Z-cg.N` împins pe `release_builds.yml`) semnează automat
installer-ul cu ACELAȘI certificat — colaboratorii nu mai trebuie să
reimporte nimic la versiunile următoare.

## Ce face CI-ul automat (`.github/workflows/release_builds.yml`)

- Dacă secretele NU sunt setate: build-ul continuă **nesemnat**, exact ca
  până acum — nicio eroare, nicio schimbare de comportament.
- Dacă secretele SUNT setate: după ce installer-ul final Inno Setup
  există (`DisplayCAL-*-Setup.exe`, înainte de duplicarea sub numele
  stabil `DisplayCAL-CG-Setup.exe`), e semnat cu `signtool.exe`
  (localizat dinamic din Windows Kits, cu timestamp), apoi verificat cu
  `Get-AuthenticodeSignature` — confirmă DOAR că semnătura a fost atașată
  corect, fără să ceară lanț de încredere complet (asta ar eșua mereu pe
  un runner CI proaspăt, care nu are certificatul în Trusted Root —
  normal pentru self-signed, nu un bug). Copia stabilă
  (`DisplayCAL-CG-Setup.exe`) e făcută DUPĂ semnare, deci poartă aceeași
  semnătură. Un eșec real de semnare (fișier fără nicio semnătură) tot
  oprește build-ul (CI roșu).

## Regenerarea certificatului (dacă expiră sau e compromis)

Rulează din nou `generate-self-signed-cert.ps1`, reîncarcă secretele
(pasul 2 de mai sus îi suprascrie pe cei vechi) — dar **toți colaboratorii
trebuie să reimporte noul `.cer`**, altfel văd din nou avertismentul
pentru versiunile semnate cu noul certificat. Evită regenerarea
inutilă — de asta scriptul folosește o valabilitate de 5 ani.
