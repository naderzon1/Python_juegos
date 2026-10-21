"""Corpus de entrenamiento del modelo de texto (escrito para este proyecto).

Está dividido por escena, hora y ánimo. Para cada prompt se entrena un modelo
con el corpus general más los bloques que correspondan a su interpretación.
Las frases comparten giros ("bajo la luz de", "en el silencio de", "como si")
para que el modelo pueda saltar de una frase a otra y crear combinaciones
nuevas en lugar de repetir el original.
"""

GENERAL = """
El viento cuenta historias que nadie recuerda.
Cada paso deja una huella que el tiempo borra despacio.
La luz cae sobre el mundo como una promesa antigua.
En el silencio se escucha el pulso de las cosas.
Hay un camino que se abre cuando dejamos de buscarlo.
Los recuerdos viajan con el viento hacia lugares lejanos.
El tiempo se detiene cuando la mirada encuentra lo que ama.
Una voz antigua llama desde el horizonte.
Todo lo que existe guarda un secreto en su interior.
La memoria del mundo vive en las piedras y en el agua.
El horizonte promete un viaje que todavía no empieza.
Caminamos despacio, como si el tiempo nos esperara.
Las sombras se alargan y el mundo respira en calma.
Bajo la luz de cada día nace una historia nueva.
Nadie sabe hacia dónde viaja la luz cuando se apaga.
El corazón aprende a escuchar lo que el silencio dice.
"""

ESCENAS = {
    "montana": """
Las montañas guardan el silencio de los siglos.
Sobre la cumbre, la nieve brilla como un espejo del cielo.
El viento baja por la ladera y despierta a los pinos dormidos.
Cada cumbre es una pregunta que el cielo responde con nubes.
Los picos se alzan hacia el cielo como gigantes de piedra.
En el valle, el río canta entre las rocas una canción de nieve.
La niebla sube despacio por la ladera y borra el camino.
Desde lo alto se ve el mundo pequeño y lejano.
La roca recuerda el fuego que la hizo nacer.
El sendero sube entre las piedras hacia la cumbre.
Las nubes se enredan en los picos como lana blanca.
Quien sube a la montaña aprende el valor de cada paso.
El eco de la montaña devuelve las palabras al viajero.
Bajo la luz de la cumbre, el aire es frío y limpio.
""",
    "bosque": """
El bosque respira despacio bajo un techo de hojas.
Entre los árboles, la luz cae en hilos dorados.
Las raíces cuentan historias antiguas a la tierra húmeda.
Un pájaro canta entre las ramas y el bosque le responde.
El musgo cubre las piedras como un abrigo verde.
Los árboles se mecen con el viento y susurran secretos.
En el corazón del bosque, el tiempo camina más lento.
El sendero se pierde entre helechos y sombras.
Las hojas caen sobre el camino como cartas del otoño.
La lluvia golpea las hojas con dedos suaves.
Cada árbol guarda en su corteza la memoria del bosque.
Bajo la luz del bosque, todo parece estar vivo.
Los pinos altos se mecen como guardianes del silencio.
Un ciervo cruza el claro y desaparece entre los árboles.
""",
    "mar": """
El mar llega a la orilla y vuelve a irse, como un recuerdo.
Las olas cantan una canción que la arena aprende de memoria.
En el horizonte, el cielo y el mar se confunden en un solo azul.
El viento del mar trae sal y voces de puertos lejanos.
Un barco pequeño navega hacia el horizonte sin miedo.
La espuma dibuja en la arena mapas que nadie podrá leer.
Bajo la luz del mar, el agua brilla como un espejo roto.
Las gaviotas vuelan sobre las olas buscando el camino a casa.
El faro guarda la costa con su luz paciente.
La marea sube despacio y borra las huellas de la playa.
El mar guarda en su fondo los secretos de los marineros.
Cada ola trae una historia y se lleva otra.
El agua del mar refleja el cielo como si fuera su sueño.
En la playa, el tiempo se mide en olas.
""",
    "desierto": """
El desierto guarda un silencio hecho de arena y de sol.
Las dunas se mueven con el viento como olas de oro.
Bajo la luz del desierto, el aire tiembla sobre la arena.
Un viajero camina hacia el horizonte buscando el oasis.
La arena borra cada huella como si nadie hubiera pasado.
En el desierto, el cielo es más grande que el mundo.
El viento canta entre las dunas una canción muy antigua.
Las caravanas cruzan la arena siguiendo a las estrellas.
El sol cae sobre las dunas y las pinta de fuego.
Un cactus solitario guarda el agua como un tesoro.
El oasis brilla a lo lejos como una promesa verde.
La sed enseña al viajero el valor de cada gota.
Las dunas cambian de forma, pero el desierto siempre es el mismo.
""",
    "ciudad": """
La ciudad nunca duerme del todo y respira con sus luces.
Las calles guardan los pasos de miles de historias.
Entre los edificios, el cielo es una franja estrecha de luz.
Las ventanas encendidas son pequeños mundos en la noche.
El tráfico canta una canción de motores y de prisa.
En cada esquina de la ciudad espera un encuentro distinto.
Las torres se alzan hacia el cielo como sueños de vidrio.
La lluvia sobre el asfalto refleja las luces de neón.
Un tren cruza la ciudad llevando sueños de un barrio a otro.
Bajo la luz de las farolas, la calle parece un río dorado.
La ciudad guarda en sus muros la memoria de su gente.
Desde la azotea se ve la ciudad como un mar de luces.
En el silencio de la madrugada, la ciudad parece otra.
""",
    "espacio": """
Las estrellas brillan en el espacio como faros de otros mundos.
La galaxia gira despacio, indiferente al paso del tiempo.
Una nave cruza el silencio infinito entre los planetas.
En el espacio no hay viento, pero la luz viaja sin descanso.
Las nebulosas pintan el vacío con colores imposibles.
Un planeta azul gira solo en la inmensa oscuridad.
La luz de las estrellas tarda siglos en llegar a nuestros ojos.
El universo guarda secretos que ninguna nave ha visto.
Los anillos del planeta brillan como un camino de polvo.
Bajo la luz de mil soles, el astronauta mira hacia casa.
En el silencio del espacio, el corazón suena como un tambor.
Cada estrella es un mundo que nació del polvo y del fuego.
La órbita de la luna dibuja un círculo de plata.
El cosmos se abre como un océano sin orillas.
""",
}

HORAS = {
    "amanecer": """
El amanecer pinta el cielo de rosa y de oro.
La primera luz del día despierta al mundo despacio.
Con el alba, las sombras de la noche se retiran.
El sol nace en el horizonte como una promesa nueva.
La mañana llega con el aire fresco y limpio.
El cielo se abre al amanecer como una flor de luz.
""",
    "dia": """
El sol brilla alto y el mundo se llena de color.
La luz del día cae sobre todo con generosidad.
El cielo azul se extiende sin una sola nube.
Bajo el sol del mediodía, las sombras se hacen pequeñas.
Las nubes blancas viajan despacio por el cielo.
El día es largo y luminoso como una canción alegre.
""",
    "atardecer": """
El atardecer tiñe el cielo de naranja y violeta.
El sol se despide en el horizonte con un incendio dorado.
Las sombras se alargan cuando cae la tarde.
En el ocaso, el cielo arde y luego se apaga despacio.
La luz dorada del atardecer lo vuelve todo un recuerdo.
El día termina y el cielo se viste de fuego.
""",
    "noche": """
La noche cae y las estrellas se encienden una a una.
La luna llena derrama su luz de plata sobre el mundo.
En la oscuridad, cada sonido parece un secreto.
Bajo la luz de la luna, el mundo sueña en silencio.
La noche guarda los sueños de quienes duermen.
Las estrellas miran desde lo alto como ojos antiguos.
""",
}

ANIMOS = {
    "alegre": """
La alegría llega como una canción que todos conocen.
Todo brilla y el corazón quiere bailar.
Hay una fiesta de luz en cada rincón del mundo.
Reír es la forma más bonita de decir que estamos vivos.
El mundo sonríe y nosotros sonreímos con él.
""",
    "calma": """
Todo está en calma y el tiempo respira despacio.
La paz llega sin ruido, como la luz de la mañana.
En el silencio hay un descanso que el alma agradece.
Respirar despacio es volver a casa.
La calma es un lago quieto donde se refleja el cielo.
""",
    "triste": """
La tristeza camina despacio, como la lluvia en la ventana.
Hay recuerdos que duelen como una canción lejana.
La soledad se sienta a nuestro lado sin decir nada.
Lo que perdimos vive todavía en la memoria.
Una lágrima cae y el mundo se vuelve gris.
""",
    "epico": """
El héroe avanza hacia la tormenta sin mirar atrás.
Las banderas ondean y los tambores anuncian la batalla.
Solo los valientes llegan a la cumbre de la gloria.
La fuerza nace del corazón cuando todo parece perdido.
Una nueva aventura comienza más allá del horizonte.
""",
    "misterio": """
La niebla esconde un secreto que nadie se atreve a nombrar.
Algo se mueve entre las sombras y desaparece.
Las ruinas antiguas guardan una magia olvidada.
Nadie sabe quién encendió la luz en la torre abandonada.
Hay puertas que solo se abren a quien sabe esperar.
""",
}

# Palabras para títulos, por escena: (sustantivos, complementos).
TITULOS = {
    "montana": (["La cumbre", "El eco", "La ladera", "El sendero", "La nieve"],
                ["de piedra", "de los picos", "del viento", "de las nubes", "sin nombre"]),
    "bosque": (["El claro", "Las raíces", "La sombra verde", "El susurro", "Las hojas"],
               ["del bosque", "de los pinos", "de la lluvia", "del musgo", "del ciervo"]),
    "mar": (["La marea", "El faro", "La orilla", "La espuma", "El horizonte"],
            ["del mar", "de sal", "de las olas", "sin fin", "de los marineros"]),
    "desierto": (["Las dunas", "El oasis", "La caravana", "La arena", "El espejismo"],
                 ["de oro", "del desierto", "sin agua", "del viento", "de las estrellas"]),
    "ciudad": (["Las luces", "La avenida", "La azotea", "Las ventanas", "El último tren"],
               ["de neón", "de la ciudad", "de medianoche", "del barrio", "de vidrio"]),
    "espacio": (["La órbita", "Las estrellas", "La nebulosa", "El planeta", "El viaje"],
                ["de polvo", "sin regreso", "de plata", "entre mundos", "del silencio"]),
}
