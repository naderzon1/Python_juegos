'use strict';
// Utilidades compartidas por los juegos web: guardado local, sonido sintetizado,
// lienzo que se ajusta a la pantalla, botones táctiles y bucle de animación.

const Guardado = {
  leer(clave, defecto) {
    try {
      const v = localStorage.getItem(clave);
      return v === null ? defecto : JSON.parse(v);
    } catch {
      return defecto;
    }
  },
  escribir(clave, valor) {
    try { localStorage.setItem(clave, JSON.stringify(valor)); } catch { /* sin almacenamiento: no pasa nada */ }
  },
};

// Todo el sonido se sintetiza al empezar: ondas cuadradas, triangulares y ruido, como en las versiones de Python.
const Sonido = (() => {
  let ctx = null, general = null, canalMusica = null, fuenteMusica = null;
  let SR = 44100;
  let activo = Guardado.leer('sonido_activo', true);
  const recetas = {}, buffers = {};

  function hz(nota) {
    return 440 * 2 ** ((nota - 69) / 12);
  }

  // Suma a la pista un sonido que se desliza de f0 a f1 Hz.
  function tono(p, inicio, dur, f0, f1 = null, vol = 0.3, onda = 'cuadrada') {
    if (f1 === null) f1 = f0;
    const i0 = Math.floor(inicio * SR), n = Math.floor(dur * SR);
    while (p.length < i0 + n) p.push(0);
    const ataque = 0.0045 * SR, final = 0.018 * SR;
    let fase = 0;
    for (let k = 0; k < n; k++) {
      const t = k / n;
      fase = (fase + (f0 + (f1 - f0) * t) / SR) % 1;
      const v = onda === 'cuadrada' ? (fase < 0.5 ? 1 : -1)
        : onda === 'triangular' ? 4 * Math.abs(fase - 0.5) - 1
          : Math.random() * 2 - 1;
      // ataque y final suaves para que no haga "clic", y una caída ligera
      p[i0 + k] += vol * v * Math.min(1, k / ataque, (n - k) / final) * (1 - 0.6 * t);
    }
  }

  // notas: lista de [nota MIDI o null para silencio, duración en pasos]
  function melodia(p, notas, paso, vol, onda) {
    let t = 0;
    for (const [nota, pasos] of notas) {
      if (nota !== null) tono(p, t, pasos * paso * 0.92, hz(nota), null, vol, onda);
      t += pasos * paso;
    }
  }

  // deja la pista con la duración exacta (para que la música se repita sin corte)
  function recortar(p, segundos) {
    const n = Math.floor(segundos * SR);
    while (p.length < n) p.push(0);
    p.length = n;
    return p;
  }

  function construir(muestras) {
    const b = ctx.createBuffer(1, Math.max(1, muestras.length), SR);
    const d = b.getChannelData(0);
    for (let i = 0; i < muestras.length; i++) d[i] = Math.max(-1, Math.min(1, muestras[i] || 0));
    return b;
  }

  return {
    definir(nombre, receta) { recetas[nombre] = receta; },
    // Los navegadores solo dejan sonar después de un toque o una tecla: llamarlo desde uno.
    iniciar() {
      if (!ctx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return;
        ctx = new AC();
        SR = ctx.sampleRate;
        general = ctx.createGain();
        general.gain.value = activo ? 1 : 0;
        general.connect(ctx.destination);
        canalMusica = ctx.createGain();
        canalMusica.gain.value = 0.45;
        canalMusica.connect(general);
        const api = { tono, melodia, hz, recortar };
        for (const [n, r] of Object.entries(recetas)) buffers[n] = construir(r(api));
      }
      if (ctx.state === 'suspended') ctx.resume();
    },
    tocar(nombre) {
      if (!ctx || !buffers[nombre]) return;
      const f = ctx.createBufferSource();
      f.buffer = buffers[nombre];
      f.connect(general);
      f.start();
    },
    musica(nombre) {
      this.pararMusica();
      if (!ctx || !buffers[nombre]) return;
      fuenteMusica = ctx.createBufferSource();
      fuenteMusica.buffer = buffers[nombre];
      fuenteMusica.loop = true;
      fuenteMusica.connect(canalMusica);
      fuenteMusica.start();
    },
    pararMusica() {
      if (fuenteMusica) {
        try { fuenteMusica.stop(); } catch { /* ya estaba detenida */ }
        fuenteMusica = null;
      }
    },
    get activo() { return activo; },
    get listo() { return !!ctx; },
    duracion(nombre) { return buffers[nombre] ? buffers[nombre].duration : 0; },
    alternar() {
      activo = !activo;
      Guardado.escribir('sonido_activo', activo);
      if (general) general.gain.value = activo ? 1 : 0;
      return activo;
    },
    pausar() { if (ctx && ctx.state === 'running') ctx.suspend(); },
    reanudar() { if (ctx && ctx.state === 'suspended') ctx.resume(); },
  };
})();

// Ajusta el lienzo al espacio disponible sin deformarlo y con nitidez en pantallas de alta densidad.
// El juego siempre dibuja en sus propias coordenadas (ancho x alto).
function prepararLienzo(canvas, ancho, alto) {
  const g = canvas.getContext('2d');
  const zona = canvas.parentElement;
  function ajustar() {
    const esc = Math.max(0.05, Math.min(zona.clientWidth / ancho, zona.clientHeight / alto));
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    canvas.style.width = Math.floor(ancho * esc) + 'px';
    canvas.style.height = Math.floor(alto * esc) + 'px';
    canvas.width = Math.max(1, Math.round(ancho * esc * dpr));
    canvas.height = Math.max(1, Math.round(alto * esc * dpr));
    g.setTransform(canvas.width / ancho, 0, 0, canvas.height / alto, 0, 0);
  }
  new ResizeObserver(ajustar).observe(zona);
  ajustar();
  return {
    g,
    // posición de un dedo o del ratón en coordenadas del juego
    aJuego(e) {
      const r = canvas.getBoundingClientRect();
      return { x: (e.clientX - r.left) * ancho / r.width, y: (e.clientY - r.top) * alto / r.height };
    },
  };
}

// Botón que actúa al tocarlo y avisa al soltarlo (para mantener pulsado).
function botonMantener(boton, alPulsar, alSoltar = () => {}) {
  let id = null;
  boton.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    Sonido.iniciar();
    id = e.pointerId;
    try { boton.setPointerCapture(id); } catch { /* algunos navegadores no lo admiten */ }
    boton.classList.add('pulsado');
    alPulsar();
  });
  const soltar = (e) => {
    if (e.pointerId !== id) return;
    id = null;
    boton.classList.remove('pulsado');
    alSoltar();
  };
  boton.addEventListener('pointerup', soltar);
  boton.addEventListener('pointercancel', soltar);
  boton.addEventListener('lostpointercapture', soltar);
  boton.addEventListener('contextmenu', (e) => e.preventDefault());
}

// Llama a paso(dt) en cada cuadro de la pantalla; dt en segundos, acotado si la pestaña estuvo oculta.
function bucle(paso) {
  let antes = performance.now();
  function cuadro(ahora) {
    const dt = Math.min(0.1, Math.max(0, (ahora - antes) / 1000));
    antes = ahora;
    paso(dt);
    requestAnimationFrame(cuadro);
  }
  requestAnimationFrame(cuadro);
}

// Para la lógica que en Python avanzaba un paso por cuadro a 60 por segundo.
function pasosFijos(alPaso) {
  let acumulado = 0;
  return (dt) => {
    acumulado += dt;
    while (acumulado >= 1 / 60) {
      alPaso();
      acumulado -= 1 / 60;
    }
  };
}
