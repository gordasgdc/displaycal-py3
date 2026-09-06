# ghid_es.py — contenido de la guía de DisplayCAL-CG (español).
# Estructura declarativa leída por `_engine.build()` — ver allí los tipos
# de bloque aceptados ("p", "h2", "ul", "code", "img", "steps", "opt",
# "info"/"warn"/"ok", "pagebreak").

CONTENT = {
    "title": "Guía de uso de DisplayCAL-CG",
    "subtitle": "Calibración y perfilado de monitor, paso a paso — edición GDC",
    "note": "Versión del documento 1.0 · basado en DisplayCAL-CG 3.10.0.dev82",
    "toc_title": "Índice",
    "cover_subtitle": "Calibración y caracterización de monitor con ArgyllCMS",
    "cover_version_label": "Versión de la app",
    "cover_lang_label": "Edición en español",
    "footer": "DisplayCAL-CG — Guía de uso (ES)",
    "sections": [
        {
            "h": "Qué es DisplayCAL-CG",
            "blocks": [
                ("p", "DisplayCAL-CG es una edición GDC del proyecto de "
                       "código abierto <b>DisplayCAL</b> (la continuación "
                       "comunitaria del trabajo original de Florian Höch), "
                       "reempaquetada y traducida íntegramente por GDC. La "
                       "aplicación calibra y perfila tu monitor usando el "
                       "motor de medición <b>ArgyllCMS</b> — el resultado "
                       "es un monitor con colores correctos y constantes, "
                       "sin importar la aplicación en la que trabajes "
                       "(foto, vídeo, diseño)."),
                ("info", ("Qué significa \"calibración\" vs. \"perfilado\"",
                          "La <b>calibración</b> lleva el monitor a un "
                          "estado objetivo conocido (punto blanco, "
                          "luminancia, curva tonal) mediante ajustes de "
                          "hardware/software (las curvas de la tarjeta "
                          "gráfica). El <b>perfilado</b> mide después cómo "
                          "responde el monitor ya calibrado y escribe un "
                          "<b>perfil ICC</b> que el resto del sistema usa "
                          "para una corrección de color precisa. Siempre "
                          "se hacen uno después del otro, en este orden.")),
                ("p", "Esta guía explica, uno por uno, cada una de las 5 "
                       "pestañas principales de la aplicación (Pantalla e "
                       "instrumento, Calibración, Perfilado, LUT 3D, "
                       "Verificación), las herramientas avanzadas de los "
                       "menús, y cómo instalar/actualizar la aplicación en "
                       "Mac y Windows."),
                ("warn", ("Necesitas un instrumento de medición",
                          "DisplayCAL-CG NO puede calibrar un monitor sin "
                          "un colorímetro o espectrofotómetro físico "
                          "conectado por USB (ej. X-Rite i1Display Pro, "
                          "ColorMunki Display, Datacolor Spyder). La "
                          "aplicación detecta automáticamente el "
                          "instrumento conectado en la pestaña \"Pantalla e "
                          "instrumento\".")),
            ],
        },
        {
            "h": "Instalación",
            "blocks": [
                ("h2", "macOS"),
                ("steps", [
                    "Descarga el paquete <b>DisplayCAL-CG.pkg</b> desde la "
                    "página de descargas (gordas.dev/DisplayCAL-CG).",
                    "Haz doble clic en el archivo <b>.pkg</b> descargado.",
                    "En la ventana del instalador, pulsa <b>Continuar</b> "
                    "en cada paso hasta llegar a la página de "
                    "<b>Licencia</b>.",
                    "Lee el resumen de la licencia GPLv3 mostrado, pulsa "
                    "<b>Aceptar</b> (sin aceptación explícita, la "
                    "instalación no puede continuar — es un requisito del "
                    "instalador nativo de macOS, no un paso opcional).",
                    "Pulsa <b>Instalar</b> — la aplicación y las 9 "
                    "herramientas satélite (Profile Info, Curve Viewer, "
                    "etc.) se instalan directamente en <b>Aplicaciones</b>, "
                    "sin arrastrar nada manualmente.",
                    "Abre <b>DisplayCAL-CG</b> desde Launchpad/Aplicaciones.",
                ]),
                ("info", ("El paquete está firmado y notarizado por Apple",
                          "Gatekeeper de macOS dejará que la aplicación se "
                          "abra directamente, sin la advertencia de \"no se "
                          "puede abrir porque proviene de un desarrollador "
                          "no identificado\".")),
                ("h2", "Windows"),
                ("steps", [
                    "Descarga el instalador <b>DisplayCAL-CG-Setup.exe</b> "
                    "desde la página de descargas.",
                    "Haz doble clic en el archivo descargado.",
                    "Si aparece el aviso de <b>Windows SmartScreen</b> "
                    "(\"Windows protegió tu equipo\"), pulsa <b>Más "
                    "información</b> y luego <b>Ejecutar de todas "
                    "formas</b>.",
                    "En la página de licencia del instalador, selecciona "
                    "<b>Acepto el acuerdo</b> — el botón \"Siguiente\" "
                    "permanece desactivado hasta que lo marques.",
                    "Sigue los pasos del instalador (se recomienda la "
                    "ubicación predeterminada) hasta <b>Instalar</b>.",
                    "Abre <b>DisplayCAL-CG</b> desde el menú Inicio o el "
                    "acceso directo del Escritorio.",
                ]),
                ("warn", ("Por qué aparece el aviso de SmartScreen",
                          "El instalador de Windows todavía no está firmado "
                          "con un certificado de firma de código de pago — "
                          "el aviso es normal para software sin firmar, no "
                          "una señal de que el archivo sea inseguro. "
                          "Descárgalo solo desde la página oficial de "
                          "arriba.")),
            ],
        },
        {
            "h": "Pantalla e instrumento",
            "blocks": [
                ("p", "La primera pestaña — elige QUÉ monitor vas a "
                       "calibrar y CON QUÉ instrumento. La aplicación "
                       "necesita saber ambas cosas antes de poder pasar a "
                       "Calibración."),
                ("img", ("monitor_instrument_full.png",
                        "La pestaña Pantalla e instrumento, con un monitor "
                        "externo y un colorímetro i1DisplayPro ya "
                        "detectados.")),
                ("opt", (("Campo", "Qué hace"), [
                    ("Pantalla", "Elige de la lista el monitor a calibrar, "
                                "si tienes varios conectados. El botón "
                                "redondo ↻ vuelve a escanear las pantallas "
                                "conectadas."),
                    ("Instrumento", "El colorímetro/espectrofotómetro "
                                    "detectado por USB. Si aparece vacío, "
                                    "revisa el cable USB y que el "
                                    "instrumento sea reconocido por el "
                                    "sistema operativo."),
                    ("Modo", "El modo de medición del instrumento — "
                            "\"Refresh (genérico)\" sirve para la mayoría "
                            "de monitores LCD/LED. Algunos instrumentos "
                            "(K-10, Spyder4/5/X) ofrecen modos "
                            "precalibrados para tipos de pantalla "
                            "específicos — elige el más parecido al tuyo "
                            "si existe."),
                    ("Compensación de deriva de blanco", "Actívala si el "
                            "monitor es un TV OLED/Plasma u otro tipo con "
                            "salida de luz variable según el contenido "
                            "mostrado."),
                    ("Compensación de deriva de negro", "Actívala si usas "
                            "un espectrómetro en modo de contacto sobre un "
                            "monitor con nivel de negro inestable."),
                    ("Niveles de salida", "\"Automático\" es la opción "
                            "correcta en casi todos los casos. \"TV RGB "
                            "16-235\" solo aplica si el monitor/tarjeta "
                            "gráfica limita intencionalmente el rango de "
                            "señal, como con un TV usado como monitor."),
                    ("Corrección", "La corrección de color específica del "
                            "instrumento + monitor — DisplayCAL-CG la elige "
                            "automáticamente (\"Automático (Espectral: "
                            "...)\") cuando puede; no la cambies "
                            "manualmente salvo que sepas exactamente lo "
                            "que haces."),
                ])),
                ("info", ("Antes de medir",
                          "Deja que el monitor se caliente <b>al menos 30 "
                          "minutos</b> antes de calibrar — los colores de "
                          "un monitor frío varían mientras se estabiliza "
                          "térmicamente. Desactiva cualquier ajuste "
                          "dinámico de imagen (contraste dinámico, brillo "
                          "automático) y evita que la luz incida "
                          "directamente sobre la pantalla durante la "
                          "medición.")),
            ],
        },
        {
            "h": "Calibración",
            "blocks": [
                ("p", "La segunda pestaña — elige QUÉ estado objetivo "
                       "quieres para el monitor: qué punto blanco, qué "
                       "luminancia, qué curva tonal."),
                ("img", ("calibrare_full.png",
                        "Ajustes de calibración predeterminados (Gamma "
                        "2.2, punto blanco y niveles \"según medido\").")),
                ("opt", (("Campo", "Qué hace"), [
                    ("Ajuste interactivo del monitor", "Marcado, la "
                            "aplicación te guía para ajustar manualmente "
                            "los controles físicos del monitor "
                            "(brillo, contraste, RGB) durante la "
                            "calibración, para acercarte lo más posible al "
                            "objetivo antes de generar las curvas por "
                            "software."),
                    ("Observador", "El estándar CIE usado para interpretar "
                            "el color — \"CIE 1931 2°\" es la opción "
                            "predeterminada, adecuada para la gran mayoría "
                            "de casos."),
                    ("Punto blanco", "\"Según medido\" mantiene el punto "
                            "blanco nativo del monitor. Puedes elegir en "
                            "cambio una temperatura de color fija (ej. "
                            "6500K/D65) si necesitas un estándar exacto, "
                            "con una referencia (\"Luz de día\"/\"Cuerpo "
                            "negro\")."),
                    ("Nivel de blanco / Nivel de negro", "\"Según medido\" "
                            "mantiene la luminancia nativa del monitor. "
                            "Puedes fijar manualmente un valor (ej. 120 "
                            "cd/m²) si necesitas cumplir un estándar de "
                            "luminancia."),
                    ("Curva tonal", "La forma que tendrá la respuesta "
                            "tonal resultante — \"Gamma 2.2\" es lo "
                            "adecuado por defecto para foto/web; \"Rec. "
                            "1886\" u otras curvas importan sobre todo "
                            "para vídeo."),
                    ("Offset de salida de negro", "0% = negro \"puro\"; "
                            "100% = el negro sigue exactamente la curva "
                            "elegida sin offset. Los valores intermedios "
                            "compensan monitores con negro elevado."),
                    ("Corrección de punto negro", "La tasa/porcentaje con "
                            "el que se corrigen las no linealidades cerca "
                            "del negro — \"Automático\" deja que la "
                            "aplicación decida."),
                    ("Velocidad de calibración", "Un compromiso entre "
                            "tiempo y precisión — \"Alta\" (predeterminado) "
                            "basta para la mayoría de usos."),
                ])),
                ("warn", ("La calibración 1D LUT no sustituye a un perfil ICC",
                          "Las curvas generadas aquí solo corrigen la "
                          "tonalidad general del monitor — para una "
                          "corrección de color completa también necesitas "
                          "un <b>perfil ICC de dispositivo</b> o un "
                          "<b>LUT 3D</b>, creados en las siguientes "
                          "pestañas.")),
            ],
        },
        {
            "h": "Perfilado",
            "blocks": [
                ("p", "La tercera pestaña — DisplayCAL-CG muestra parches "
                       "de color reales en pantalla, los mide con el "
                       "instrumento, y construye el <b>perfil ICC</b> que "
                       "caracteriza tu monitor ya calibrado."),
                ("img", ("profilare_full.png",
                        "Ajustes de perfilado — tipo \"Curva única + "
                        "matriz\", testchart auto-optimizado, 34 "
                        "parches.")),
                ("opt", (("Campo", "Qué hace"), [
                    ("Tipo de perfil", "\"Curva única + matriz\" es rápido "
                            "y suficiente para muchos monitores buenos; un "
                            "perfil basado en <b>LUT</b> con cientos o "
                            "miles de parches ofrece la mejor precisión "
                            "posible, pero tarda mucho más."),
                    ("Compensación de punto negro", "Se recomienda "
                            "marcada — mejora la precisión en zonas "
                            "oscuras."),
                    ("Calidad del perfil", "Deslizador Baja→Alta — influye "
                            "en la finura con la que se calcula el perfil "
                            "a partir de los datos medidos, no en el "
                            "número de parches."),
                    ("Testchart", "\"Auto-optimizado\" elige "
                            "automáticamente la distribución de parches "
                            "según las no linealidades reales de tu "
                            "monitor — recomendado para los mejores "
                            "resultados."),
                    ("Número de parches", "El deslizador controla cuántos "
                            "parches se miden — más parches = un perfil "
                            "más preciso, pero una medición más larga."),
                    ("Secuencia de parches", "\"Minimizar el retardo de "
                            "respuesta del monitor\" ordena los parches "
                            "para acortar el tiempo total de medición."),
                    ("Nombre del perfil", "La plantilla de nombrado "
                            "automático — puedes editar libremente el "
                            "campo de abajo si quieres un nombre propio."),
                ])),
                ("info", ("Cuánto dura",
                          "La aplicación muestra un tiempo estimado bajo "
                          "los ajustes de perfilado (ej. \"aproximadamente "
                          "1 minuto\" para 34 parches) — un perfil basado "
                          "en LUT, con miles de parches, puede tardar desde "
                          "unos minutos hasta más de una hora.")),
            ],
        },
        {
            "h": "LUT 3D",
            "blocks": [
                ("p", "Pestaña opcional — genera un <b>LUT 3D</b> (tabla de "
                       "búsqueda tridimensional) a partir del perfil ya "
                       "creado, para aplicaciones que admiten corrección de "
                       "color mediante LUT 3D en lugar de un perfil ICC "
                       "(habitual en flujos de vídeo/etalonaje de color — "
                       "DaVinci Resolve, reproductores multimedia)."),
                ("img", ("lut3d_full.png",
                        "Ajustes de LUT 3D — origen Rec709, curva "
                        "Rec.1886, formato IRIDAS .cube, resolución "
                        "65×65×65.")),
                ("opt", (("Campo", "Qué hace"), [
                    ("Crear LUT 3D tras el perfilado", "Márcalo si quieres "
                            "que el LUT se genere automáticamente justo "
                            "después de que termine el perfilado, sin un "
                            "paso separado."),
                    ("Espacio de color de origen", "El espacio de color "
                            "del material que vas a reproducir (ej. "
                            "\"Rec709 ITU-R BT.709\" para vídeo HD "
                            "estándar)."),
                    ("Curva tonal", "Debe coincidir con el estándar del "
                            "material de origen — el vídeo HD suele usar "
                            "una curva de potencia de ~2,2-2,4, o bien "
                            "\"Rec. 1886\"."),
                    ("Modo de mapeo de gama", "\"Dispositivo-a-PCS "
                            "inverso\" es la opción estándar para un LUT "
                            "de visualización (no de conversión de "
                            "contenido)."),
                    ("Intención de renderizado", "\"Colorimétrico absoluto "
                            "con escalado de punto blanco\" se recomienda "
                            "si no has calibrado explícitamente al punto "
                            "blanco del material de origen."),
                    ("Formato de archivo LUT 3D", "IRIDAS .cube es el más "
                            "compatible (Resolve, la mayoría de "
                            "reproductores); otros formatos existen para "
                            "software específico."),
                    ("Resolución LUT 3D", "65×65×65 es un buen compromiso "
                            "entre precisión y tamaño de archivo — "
                            "resoluciones mayores aumentan ambas cosas."),
                ])),
                ("warn", ("Usa los MISMOS ajustes con los que se creó el LUT",
                          "Al verificar más adelante un LUT 3D ya creado "
                          "(pestaña Verificación), asegúrate de usar "
                          "exactamente los mismos ajustes (espacio de "
                          "origen, curva, intención de renderizado) — de "
                          "lo contrario el resultado de la verificación no "
                          "tiene sentido.")),
            ],
        },
        {
            "h": "Verificación",
            "blocks": [
                ("p", "La quinta pestaña — comprueba la precisión de un "
                       "perfil ICC o LUT 3D ya creado, mediante un informe "
                       "de medición con estadísticas de los errores de "
                       "color medidos sobre un conjunto de parches."),
                ("img", ("verificare.png",
                        "Ajustes de verificación — testchart de "
                        "verificación extendido, 51 parches, ~2 minutos "
                        "estimados.")),
                ("opt", (("Campo", "Qué hace"), [
                    ("Testchart o referencia", "El conjunto de parches "
                            "usado para la verificación — \"Testchart de "
                            "verificación extendido\" es un conjunto "
                            "estándar, independiente del usado en el "
                            "perfilado (de lo contrario la verificación "
                            "estaría sesgada)."),
                    ("Simular punto blanco", "Compara el resultado en "
                            "relación a un punto blanco simulado, en lugar "
                            "del nativo del monitor."),
                    ("Relativo al punto blanco del perfil del monitor", "Al "
                            "igual que arriba, pero respecto al punto "
                            "blanco REGISTRADO en el perfil actual."),
                    ("Perfil de simulación", "Opcional — comprueba cómo se "
                            "comportaría el monitor si simulara otro "
                            "perfil/espacio de color."),
                ])),
                ("steps", [
                    "Elige el testchart de verificación (el "
                    "predeterminado sirve en casi todos los casos).",
                    "Pulsa <b>Informe de medición...</b> en la parte "
                    "inferior de la ventana.",
                    "Sigue al instrumento en pantalla mientras la "
                    "aplicación muestra y mide los parches de prueba uno "
                    "por uno.",
                    "Al final se abre un informe con los errores de color "
                    "medios/máximos medidos (ΔE) — cuanto menor sea el "
                    "ΔE, más preciso es el perfil.",
                ]),
                ("info", ("Consejo",
                          "Mantén pulsada la tecla <b>ALT</b> del teclado "
                          "al pulsar \"Informe de medición...\" para crear "
                          "un informe de <b>autoverificación</b> en lugar "
                          "de un informe de medición normal.")),
            ],
        },
        {
            "h": "Herramientas avanzadas",
            "blocks": [
                ("p", "Además del flujo principal (las 5 pestañas "
                       "anteriores), DisplayCAL-CG incluye varias "
                       "herramientas independientes, útiles para casos "
                       "especiales — accesibles desde el menú de la "
                       "aplicación principal o como aplicaciones separadas "
                       "instaladas junto a ella."),
                ("h2", "Crear perfil ICC sintético"),
                ("img", ("creeaza_profil_sintetic.png",
                        "La herramienta de creación de perfil ICC "
                        "sintético, a partir de parámetros descritos "
                        "manualmente (no de mediciones reales).")),
                ("p", "Construye un perfil ICC a partir de parámetros "
                       "descritos manualmente (punto blanco, gamma, "
                       "primarios de color) — útil para generar un perfil "
                       "de referencia teórico sin medir un monitor real "
                       "(ej. para simulación o pruebas)."),
                ("h2", "Crear LUT 3D (independiente)"),
                ("img", ("creeaza_lut3d_standalone.png",
                        "La herramienta independiente de creación de LUT "
                        "3D, para convertir entre espacios de color sin "
                        "pasar por un flujo completo de calibración de "
                        "monitor.")),
                ("p", "La misma lógica de generación de LUT 3D que en la "
                       "pestaña \"LUT 3D\", pero ejecutada de forma "
                       "independiente de cualquier flujo de calibración de "
                       "monitor — útil para convertir entre dos "
                       "perfiles/espacios de color arbitrarios."),
                ("h2", "Profile Info"),
                ("img", ("profile_info.png",
                        "La ventana Profile Info — información completa "
                        "sobre un perfil ICC, más una representación "
                        "gráfica de su gama de color.")),
                ("p", "Abre cualquier perfil ICC (creado por DisplayCAL-CG "
                       "o de otra fuente) y muestra toda la información "
                       "que contiene — punto blanco, curva tonal, "
                       "primarios de color — además de una representación "
                       "gráfica 3D de la gama de color cubierta."),
                ("h2", "Curvas"),
                ("img", ("curbe.png",
                        "La ventana Curvas — visualización de las curvas "
                        "de calibración (vcgt) cargadas actualmente en la "
                        "tarjeta gráfica.")),
                ("p", "Muestra gráficamente las curvas de calibración "
                       "(VCGT — Video Card Gamma Table) cargadas "
                       "actualmente en la tarjeta gráfica — útil para "
                       "comprobar rápida y visualmente qué calibración "
                       "está activa en este momento."),
                ("h2", "Registro"),
                ("img", ("jurnal.png",
                        "La ventana Registro — el registro técnico "
                        "detallado de las operaciones de ArgyllCMS "
                        "detrás de la aplicación.")),
                ("p", "El registro técnico detallado de los comandos de "
                       "ArgyllCMS ejecutados por la aplicación en segundo "
                       "plano — útil sobre todo para diagnosticar si algo "
                       "no funciona como esperas y quieres entender "
                       "exactamente qué ha pasado."),
            ],
        },
        {
            "h": "Licencia GPLv3 y apoyo opcional",
            "blocks": [
                ("ok", ("100% gratis, para siempre",
                        "DisplayCAL-CG es software libre, licenciado bajo "
                        "GPLv3 — completamente funcional desde el primer "
                        "día, sin activación, sin prueba limitada en el "
                        "tiempo, sin ninguna función bloqueada tras un "
                        "pago. Puedes instalar, usar y redistribuir la "
                        "aplicación libremente, respetando los términos de "
                        "la licencia GPLv3 incluida (LICENSE.txt).")),
                ("p", "DisplayCAL-CG está construido sobre el trabajo de "
                       "código abierto de DisplayCAL (Florian Höch) y sus "
                       "continuadores comunitarios — los créditos "
                       "completos siguen visibles en la aplicación (Ayuda "
                       "→ Acerca de)."),
                ("p", "Si la aplicación te ha resultado útil, aparece "
                       "ocasionalmente en ella un mensaje opcional de "
                       "apoyo — es puramente informativo, nunca un "
                       "requisito para usar ninguna función."),
            ],
        },
        {
            "h": "Actualizaciones",
            "blocks": [
                ("p", "DisplayCAL-CG comprueba automáticamente, al "
                       "iniciarse, si hay una versión más reciente "
                       "disponible en la página de descargas. También "
                       "puedes comprobarlo manualmente desde el menú "
                       "Ayuda."),
                ("steps", [
                    "Si aparece una notificación de versión nueva, pulsa "
                    "el enlace de la notificación — te lleva directamente "
                    "a la página de descargas con la última versión.",
                    "Descarga el nuevo paquete (.pkg en Mac, .exe en "
                    "Windows).",
                    "Instálalo sobre la versión actual, igual que en la "
                    "primera instalación (ver el capítulo "
                    "\"Instalación\") — tus ajustes y los perfiles ya "
                    "creados permanecen intactos.",
                    "Reinicia la aplicación después de instalar.",
                ]),
            ],
        },
    ],
}
