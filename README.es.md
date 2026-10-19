![license](https://img.shields.io/badge/License-GPL%20v3-blue.svg)
![pyversion](https://img.shields.io/pypi/pyversions/DisplayCAL.svg)
![pypiversion](https://img.shields.io/pypi/v/DisplayCAL.svg)
![wheel](https://img.shields.io/pypi/wheel/DisplayCAL.svg)

[🇷🇴 Română](README.md) &middot; [🇬🇧 English](README.en.md) &middot; [🇪🇸 Español](README.es.md)

DisplayCAL-CG — Distribución GDC
=================================

Esta es **DisplayCAL-CG**, una distribución mantenida por GDC de este
proyecto, sobre el mismo código y la misma licencia GPLv3 que el proyecto
original de abajo. Sin licencias, sin prueba, sin ninguna forma de
monetización.

Qué aporta esta edición:

- **Calibración guiada** en cinco pasos, con interfaz Qt: monitor e
  instrumento, objetivo, preparación física (lista con fuentes, animación de
  colocación para los instrumentos que el fabricante documenta), plan de
  medición, instalación y verificación del perfil.
- **Identificación honesta del instrumento**: si varios modelos comparten la
  misma identidad USB, el modelo exacto lo confirmas tú.
- **Sesiones largas más seguras**: medición en bloques guardados al
  terminar, diario de sesión, continuar con los bloques restantes (solo en
  las mismas condiciones), prevención de suspensión solo durante la
  ejecución.
- **ArgyllCMS incluido** en el instalador y verificado con un hash SHA-256
  fijo.
- Interfaz y guías en rumano, inglés y español; instaladores nativos para
  macOS (`.pkg`, firmado y notarizado) y Windows.

- **Descarga y página web:** [gordas.dev/DisplayCAL-CG](https://gordas.dev/DisplayCAL-CG/)
- **Versiones (macOS `.pkg`):** [github.com/gordasgdc/displaycal-py3/releases](https://github.com/gordasgdc/displaycal-py3/releases)
- **Mantenido por:** Cristi Gordaș (GDC) — solo rebranding, traducción al
  rumano y paquete nativo de instalación. Todo el crédito por DisplayCAL en
  sí pertenece a los autores originales de abajo.

Todo lo que sigue es el `README.md` original del proyecto upstream,
traducido al español — el código y la funcionalidad siguen siendo idénticos.

---

Proyecto DisplayCAL para Python 3
===================================

Este proyecto se propuso modernizar el código de DisplayCAL, incluyendo
soporte para Python 3.

Florian Höch, el desarrollador original, hizo un trabajo increíble creando
y manteniendo DisplayCAL durante todos estos años. Pero, parece que,
durante la pandemia, muy comprensiblemente, perdió la pasión por el
proyecto. Ahora es momento de que nosotros, la comunidad de DisplayCAL,
contribuyamos de vuelta a esta gran herramienta.

Este proyecto se basa en el ``HEAD`` de la versión de Sourceforge, que tenía
5 commits adicionales creados por Florian sobre la versión ``3.8.9.3``,
lanzada el 14 de enero de 2020.

Gracias a todos los esfuerzos de la comunidad, DisplayCAL ahora funciona
con Python 3.9+:

![image](screenshots/DisplayCAL-screenshot-GNOME-3.9.5-running_on_python3.10.png)

Instrucciones de instalación
==============================

Sigue las instrucciones según tu sistema operativo:

- [Windows](docs/install_instructions_windows.md)
- [MacOS](docs/install_instructions_macos.md)
- [Linux](docs/install_instructions_linux.md)

¡Que lo disfrutes!
