// Estudio Generativo: generadores locales (sin internet ni clave).
// Puerto a JavaScript de ia_generativa/temas.py e imagen.py.
// - interpretar(texto): escena, hora y ánimo a partir de palabras clave.
// - pintarPaisaje(p): paisaje procedural por capas en un <canvas> (800×500).

// ------------------------------------------------------------------ azar con semilla
export function hash(texto) {
  let h = 2166136261;
  for (const c of String(texto)) { h ^= c.codePointAt(0); h = Math.imul(h, 16777619); }
  return h >>> 0;
}
function crearAzar(semilla) {
  let a = semilla >>> 0;
  const r = () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  r.uniform = (a0, b0) => a0 + (b0 - a0) * r();
  r.randint = (a0, b0) => a0 + Math.floor(r() * (b0 - a0 + 1));
  r.choice = (lista) => lista[Math.floor(r() * lista.length)];
  r.weighted = (lista, pesos) => {
    let total = pesos.reduce((s, p) => s + p, 0), x = r() * total;
    for (let i = 0; i < lista.length; i++) { x -= pesos[i]; if (x <= 0) return lista[i]; }
    return lista[lista.length - 1];
  };
  return r;
}

// ------------------------------------------------------------------ interpretación
export const ESCENAS = ["montana", "bosque", "mar", "desierto", "ciudad", "espacio"];
export const HORAS = ["amanecer", "dia", "atardecer", "noche"];
export const ANIMOS = ["alegre", "calma", "triste", "epico", "misterio"];
export const NOMBRES = {
  montana: "montaña", bosque: "bosque", mar: "mar", desierto: "desierto", ciudad: "ciudad", espacio: "espacio",
  amanecer: "amanecer", dia: "día", atardecer: "atardecer", noche: "noche",
  alegre: "alegre", calma: "en calma", triste: "melancólico", epico: "épico", misterio: "misterioso",
};
const PALABRAS = {
  montana: ["montan", "cordiller", "pico", "cumbre", "nieve", "nevad", "volcan", "roca", "sierra", "andes", "colina", "cerro", "valle", "glaciar", "lava", "terremot", "geolog"],
  bosque: ["bosque", "arbol", "selva", "jungla", "hoja", "pino", "verde", "musgo", "naturaleza", "flor", "jardin", "planta", "parque", "animal", "pajaro", "huerta", "cultivo", "semilla", "fruta", "fotosint", "biolog", "ecolog"],
  mar: ["mar", "ocean", "playa", "ola", "costa", "isla", "barco", "puerto", "lago", "agua", "rio", "marea", "pez", "peces", "ballena", "nadar", "pesca"],
  desierto: ["desierto", "duna", "arena", "sahara", "oasis", "cactus", "seco", "arido", "calor", "egipto", "piramide", "camello"],
  ciudad: ["ciudad", "urban", "calle", "edificio", "rascacielo", "metropoli", "neon", "trafico", "barrio", "pueblo", "torre", "casa", "oficina", "trabajo", "dinero", "tienda", "negocio", "empresa", "escuela", "computador", "tecnolog", "internet", "telefono", "program", "codigo", "coche", "auto", "tren", "historia", "cocina", "receta", "comida"],
  espacio: ["espacio", "galaxia", "estrella", "planeta", "nebulosa", "cosmo", "universo", "astronaut", "orbita", "luna", "cohete", "nave", "marte", "sideral", "satelite", "fisica", "cuantic", "atomo", "ciencia", "inteligencia", "robot", "futuro"],
  amanecer: ["amanec", "alba", "aurora", "madrugada", "manana", "despert", "comienzo", "empezar", "inicio", "nacer"],
  dia: ["dia", "mediodia", "soleado", "luminos", "verano", "hoy", "trabajo", "escuela", "aprender"],
  atardecer: ["atardec", "ocaso", "crepusculo", "puesta", "anochecer", "dorad", "otono", "final", "despedid"],
  noche: ["noche", "nocturn", "oscur", "medianoche", "sueno", "dormir", "estrellad", "luna", "cuna"],
  alegre: ["alegr", "feliz", "content", "divert", "fiesta", "brillante", "esperanz", "celebr", "jugar", "risa", "chiste", "cumpleanos", "gracias", "genial", "excelente"],
  calma: ["calma", "tranquil", "paz", "seren", "relaj", "suave", "silencio", "lent", "medit", "descans", "respir", "cuna", "dormir", "estres"],
  triste: ["trist", "melancol", "nostalg", "soledad", "solo", "lluvia", "llanto", "pena", "perdid", "olvido", "adios", "gris", "muerte", "duelo", "dolor", "lament"],
  epico: ["epic", "heroe", "heroic", "batalla", "guerr", "aventur", "glori", "poder", "tormenta", "dragon", "conquist", "valient", "fuerza", "volcan", "erupcion", "explosi", "energia", "record"],
  misterio: ["misterio", "enigma", "secreto", "extran", "fantasma", "niebla", "sombra", "magia", "mistic", "antiguo", "ruina", "oculto", "bruma", "desconoc", "agujero negro", "cuantic"],
};
export function normalizar(texto) {
  return String(texto).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}
function puntuar(palabras, norm, categorias) {
  const puntos = {};
  for (const cat of categorias) {
    let total = 0;
    for (const raiz of PALABRAS[cat]) {
      if (raiz.includes(" ")) { total += 2 * (norm.split(raiz).length - 1); continue; }
      const corta = raiz.length <= 3;
      for (const p of palabras) {
        if (corta ? (p === raiz || p === raiz + "s" || p === raiz + "es") : p.startsWith(raiz)) total += p === raiz ? 2 : 1;
      }
    }
    if (total) puntos[cat] = total;
  }
  return puntos;
}
// La petición manda; la respuesta solo completa lo que la petición no dice.
export function interpretar(peticion, respuesta = "", semilla) {
  semilla = semilla ?? hash(peticion + "\u0000" + respuesta);
  const azar = crearAzar(semilla);
  for (let i = 0; i < 4; i++) azar();  // las primeras salidas dependen mucho de la semilla
  const fuentes = [peticion, respuesta].map((t) => { const n = normalizar(t); return { n, p: n.match(/[a-zñ]+/g) || [] }; });
  const r = { semilla, detectado: {} };
  for (const [clave, cats] of [["escena", ESCENAS], ["hora", HORAS], ["animo", ANIMOS]]) {
    let elegido = null;
    for (const f of fuentes) {
      const pts = puntuar(f.p, f.n, cats);
      const max = Math.max(0, ...Object.values(pts));
      if (max > 0) { elegido = cats.find((c) => pts[c] === max); break; }
    }
    r.detectado[clave] = !!elegido;
    // Sin pista, se prefieren las horas con más luz (se ven mejor).
    r[clave] = elegido || (clave === "hora" ? azar.weighted(cats, [2, 3, 3, 2]) : azar.choice(cats));
  }
  if (r.escena === "espacio" && !r.detectado.hora) r.hora = "noche";
  return r;
}
export function describir(p) {
  if (p.escena === "espacio") return `Escena del espacio, ${NOMBRES[p.animo]}, con una nebulosa y un planeta`;
  return `Paisaje de ${NOMBRES[p.escena]} al ${p.hora === "dia" ? "mediodía" : p.hora === "noche" ? "anochecer, de noche" : NOMBRES[p.hora]}, ${NOMBRES[p.animo]}`;
}

// ------------------------------------------------------------------ imagen
const CIELOS = {
  amanecer: [[0, [38, 56, 112]], [0.5, [170, 120, 160]], [0.82, [248, 172, 146]], [1, [255, 216, 172]]],
  dia: [[0, [46, 104, 186]], [0.6, [112, 170, 226]], [1, [204, 228, 246]]],
  atardecer: [[0, [28, 22, 68]], [0.42, [128, 52, 108]], [0.74, [236, 104, 72]], [1, [255, 192, 104]]],
  noche: [[0, [3, 5, 18]], [0.6, [12, 20, 50]], [1, [32, 46, 90]]],
};
const ASTRO = { amanecer: [[255, 238, 204], 0.82, 0.055], dia: [[255, 252, 238], 0.22, 0.045], atardecer: [[255, 214, 140], 0.78, 0.07], noche: [[236, 236, 224], 0.28, 0.04] };
const NEBLINA = { amanecer: [236, 176, 166], dia: [196, 218, 236], atardecer: [222, 118, 104], noche: [42, 54, 98] };
const LUZ_HORA = { amanecer: [0.62, [1.12, 0.9, 0.98]], dia: [1, [1, 1, 1]], atardecer: [0.42, [1.25, 0.82, 0.92]], noche: [0.2, [0.75, 0.9, 1.35]] };
const BASE_ESCENA = { montana: [66, 76, 92], bosque: [30, 72, 46], desierto: [218, 168, 104], ciudad: [60, 68, 90], mar: [28, 62, 84] };
const NEBULOSAS = { alegre: [[236, 84, 160], [64, 210, 236]], calma: [[40, 150, 170], [70, 90, 210]], triste: [[60, 80, 150], [120, 130, 160]], epico: [[230, 70, 40], [250, 170, 60]], misterio: [[130, 50, 190], [40, 190, 140]] };
const ETALONADO = { alegre: [1.18, [1.04, 1.02, 0.98], 1.06], calma: [0.92, [0.98, 1, 1.03], 0.96], triste: [0.62, [0.94, 0.98, 1.08], 0.98], epico: [1.12, [1.07, 1, 0.94], 1.14], misterio: [0.85, [1, 0.95, 1.08], 1.04] };

const mezclarC = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
function degradado(paradas, t) {
  for (let i = 0; i < paradas.length - 1; i++) {
    const [t0, c0] = paradas[i], [t1, c1] = paradas[i + 1];
    if (t <= t1) return mezclarC(c0, c1, t1 > t0 ? (t - t0) / (t1 - t0) : 0);
  }
  return paradas[paradas.length - 1][1];
}

class Ruido2D {
  constructor(azar, tam = 64) { this.tam = tam; this.v = Float32Array.from({ length: tam * tam }, () => azar()); }
  valor(x, y) {
    const t = this.tam, xi = Math.floor(x), yi = Math.floor(y);
    let fx = x - xi, fy = y - yi;
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
    const x0 = ((xi % t) + t) % t, y0 = ((yi % t) + t) % t, x1 = (x0 + 1) % t, y1 = (y0 + 1) % t, v = this.v;
    const a = v[y0 * t + x0] + (v[y0 * t + x1] - v[y0 * t + x0]) * fx;
    const b = v[y1 * t + x0] + (v[y1 * t + x1] - v[y1 * t + x0]) * fx;
    return a + (b - a) * fy;
  }
  fractal(x, y, oct = 4) {
    let total = 0, amp = 1, norma = 0;
    for (let i = 0; i < oct; i++) { total += this.valor(x, y) * amp; norma += amp; amp *= 0.5; x = x * 2.03 + 17.1; y = y * 2.03 + 9.7; }
    return total / norma;
  }
}
function ruido1d(n, azar, escala, octavas = 5, crestas = false) {
  const salida = new Float32Array(n);
  let amp = 1, norma = 0, frec = escala;
  for (let o = 0; o < octavas; o++) {
    const puntos = Array.from({ length: Math.floor(n * frec) + 3 }, () => azar());
    for (let x = 0; x < n; x++) {
      const p = x * frec, i = Math.floor(p);
      const f = (1 - Math.cos((p - i) * Math.PI)) * 0.5;
      let v = puntos[i] + (puntos[i + 1] - puntos[i]) * f;
      if (crestas) v = 1 - Math.abs(v * 2 - 1);
      salida[x] += v * amp;
    }
    norma += amp; amp *= 0.5; frec *= 2.1;
  }
  for (let x = 0; x < n; x++) salida[x] /= norma;
  return salida;
}
function suavizar(valores, radio) {
  const n = valores.length, acum = new Float64Array(n + 1), out = new Float32Array(n);
  for (let i = 0; i < n; i++) acum[i + 1] = acum[i] + valores[i];
  for (let i = 0; i < n; i++) { const a = Math.max(0, i - radio), b = Math.min(n, i + radio + 1); out[i] = (acum[b] - acum[a]) / (b - a); }
  return out;
}

class Lienzo {
  constructor(w, h) { this.w = w; this.h = h; this.px = new Float32Array(w * h * 3); }
  fila(y, c) { const p = this.px; for (let i = y * this.w * 3, f = i + this.w * 3; i < f; i += 3) { p[i] = c[0]; p[i + 1] = c[1]; p[i + 2] = c[2]; } }
  mezclar(x, y, c, a) {
    if (a <= 0 || x < 0 || y < 0 || x >= this.w || y >= this.h) return;
    if (a > 1) a = 1;
    const i = ((y | 0) * this.w + (x | 0)) * 3, p = this.px;
    p[i] += (c[0] - p[i]) * a; p[i + 1] += (c[1] - p[i + 1]) * a; p[i + 2] += (c[2] - p[i + 2]) * a;
  }
  sumar(x, y, c, a) {
    if (a <= 0 || x < 0 || y < 0 || x >= this.w || y >= this.h) return;
    const i = ((y | 0) * this.w + (x | 0)) * 3, p = this.px;
    p[i] = Math.min(255, p[i] + c[0] * a); p[i + 1] = Math.min(255, p[i + 1] + c[1] * a); p[i + 2] = Math.min(255, p[i + 2] + c[2] * a);
  }
  leer(x, y) { const i = (y * this.w + x) * 3; return [this.px[i], this.px[i + 1], this.px[i + 2]]; }
}

function cielo(lz, hora, horizonte) { for (let y = 0; y < lz.h; y++) lz.fila(y, degradado(CIELOS[hora], Math.min(1, y / Math.max(1, horizonte)))); }
function estrellas(lz, azar, hasta, cantidad) {
  for (let k = 0; k < cantidad; k++) {
    const x = Math.floor(azar() * lz.w), y = Math.floor(azar() * Math.max(1, hasta));
    const brillo = azar() ** 3, tono = azar.choice([[255, 255, 255], [200, 220, 255], [255, 230, 200]]);
    lz.sumar(x, y, tono, 0.35 + 0.65 * brillo);
    if (brillo > 0.75) for (const d of [1, 2]) for (const [dx, dy] of [[d, 0], [-d, 0], [0, d], [0, -d]]) lz.sumar(x + dx, y + dy, tono, 0.5 / d);
  }
}
function astro(lz, azar, hora, horizonte, ruido) {
  const [color, altura, radioRel] = ASTRO[hora];
  const r = Math.max(4, Math.floor(lz.h * radioRel)), cx = Math.floor(lz.w * azar.uniform(0.22, 0.78)), cy = Math.floor(horizonte * altura);
  const alcance = r * (hora !== "dia" ? 5 : 4), luna = hora === "noche";
  const disco = luna ? color : mezclarC(color, [255, 255, 250], 0.65);
  for (let y = Math.max(0, cy - alcance); y < Math.min(lz.h, cy + alcance); y++) {
    for (let x = Math.max(0, cx - alcance); x < Math.min(lz.w, cx + alcance); x++) {
      const d = Math.hypot(x - cx, y - cy);
      const g = 1 - Math.max(0, d - r) / (alcance - r);
      if (g > 0) lz.sumar(x, y, color, g * g * (luna ? 0.22 : 0.5));
      if (d < r + 1) {
        let c = disco;
        if (luna) c = mezclarC(color, [170, 172, 180], Math.max(0, ruido.fractal(x * 0.18, y * 0.18, 3) - 0.45) * 1.6);
        lz.mezclar(x, y, c, Math.min(1, r + 1 - d));
      }
    }
  }
  return [cx, cy];
}
function nubes(lz, azar, ruido, hora, horizonte, densidad) {
  const luz = { amanecer: [255, 206, 190], dia: [255, 255, 255], atardecer: [255, 170, 120], noche: [70, 80, 110] }[hora];
  const sombra = mezclarC(CIELOS[hora][0][1], luz, 0.45), umbral = 0.62 - densidad * 0.18;
  const ox = azar.uniform(0, 50), oy = azar.uniform(0, 50), sx = 4 / lz.w;
  for (let y = 0; y < Math.floor(horizonte * 0.78); y++) {
    const t = y / horizonte, sy = 14 / lz.h * (1 + t * 1.8);
    for (let x = 0; x < lz.w; x++) {
      const n = ruido.fractal(x * sx + ox, y * sy + oy, 4);
      if (n > umbral) {
        const a = Math.min(1, (n - umbral) * 5) * (1 - t * 0.7);
        const arriba = ruido.fractal(x * sx + ox, (y - 3) * sy + oy, 2);
        lz.mezclar(x, y, mezclarC(sombra, luz, Math.min(1, 0.75 + (n - arriba) * 6)), a * 0.9);
      }
    }
  }
}
function colorCapa(escena, hora, prof) {
  const [mult, tinte] = LUZ_HORA[hora], base = BASE_ESCENA[escena];
  const cerca = [base[0] * mult * tinte[0], base[1] * mult * tinte[1], base[2] * mult * tinte[2]];
  return mezclarC(cerca, NEBLINA[hora], prof ** 1.15 * 0.88);
}
function rellenoPerfil(lz, alturas, color, neblina, espesor, sombreado) {
  const { w, h, px } = lz, fondo = Math.max(1, espesor);
  const ref = suavizar(alturas, Math.max(4, Math.floor(w / 25)));
  for (let x = 0; x < w; x++) {
    const y0 = Math.max(0, Math.floor(alturas[x])), s = sombreado ? sombreado[x] : 0;
    for (let y = y0; y < h; y++) {
      let t = (y - ref[x]) / fondo; t = t < 0 ? 0 : t > 1 ? 1 : t;
      const k = 1 - s * 0.45 * (1 - t) ** 2, f = t * 0.55, i = (y * w + x) * 3;
      px[i] = color[0] * k + (neblina[0] - color[0] * k) * f;
      px[i + 1] = color[1] * k + (neblina[1] - color[1] * k) * f;
      px[i + 2] = color[2] * k + (neblina[2] - color[2] * k) * f;
    }
    if (y0 > 0 && y0 < h) lz.mezclar(x, y0 - 1, color, 0.5);
  }
}
function bruma(lz, color, desde, hasta, maximo) {
  for (let y = Math.max(0, desde); y < lz.h; y++) {
    const a = maximo * Math.min(1, (y - desde) / Math.max(1, hasta - desde));
    if (a > 0) for (let x = 0; x < lz.w; x++) lz.mezclar(x, y, color, a);
  }
}
function montanas(lz, azar, hora, horizonte, capas = 4) {
  for (let k = 0; k < capas; k++) {
    const prof = (1 - k / (capas - 1)) * 0.82;
    const perfil = ruido1d(lz.w, azar, 0.006 + 0.004 * k, 6, true);
    const base = horizonte + Math.floor(lz.h * (0.02 + 0.09 * k)), amp = lz.h * (0.42 - 0.07 * k);
    const alturas = Array.from(perfil, (v) => Math.floor(base - v * amp));
    const suave = suavizar(perfil, 5);
    let somb = Array.from({ length: lz.w }, (_, x) => Math.min(1, Math.max(0, (suave[Math.min(lz.w - 1, x + 3)] - suave[Math.max(0, x - 3)]) * 14 + 0.45)));
    somb = suavizar(somb, 2);
    rellenoPerfil(lz, alturas, colorCapa("montana", hora, prof), NEBLINA[hora], lz.h * 0.16, somb);
    if (k === 0 && (hora === "dia" || hora === "amanecer")) {
      const cima = Math.min(...alturas), limite = cima + amp * 0.2;
      for (let x = 0; x < lz.w; x++) for (let y = alturas[x]; y < Math.min(lz.h, limite); y++) {
        lz.mezclar(x, y, [246, 248, 255], 0.7 * Math.min(1, (limite - y) / (amp * 0.05)) * (1 - somb[x] * 0.55));
      }
    }
  }
}
function pino(lz, x0, base, alto, color) {
  const ancho = alto * 0.42, pisos = 4;
  for (let y = Math.max(0, base - alto); y < Math.min(lz.h, base); y++) {
    const t = (y - (base - alto)) / alto, piso = (t * pisos) % 1;
    const medio = ancho * 0.5 * (0.25 + 0.75 * t) * (0.55 + 0.45 * piso);
    for (let x = Math.floor(x0 - medio); x <= Math.floor(x0 + medio); x++) lz.mezclar(x, y, color, 1);
  }
  const tw = Math.max(1, Math.floor(alto / 30));
  for (let y = base; y < Math.min(lz.h, base + Math.max(2, Math.floor(alto / 10))); y++) for (let x = x0 - tw; x <= x0 + tw; x++) lz.mezclar(x, y, color, 1);
}
function bosque(lz, azar, hora, horizonte) {
  for (let k = 0; k < 2; k++) {
    const perfil = ruido1d(lz.w, azar, 0.004, 4);
    rellenoPerfil(lz, Array.from(perfil, (v) => Math.floor(horizonte + lz.h * 0.02 * k - v * lz.h * (0.2 - 0.06 * k))), colorCapa("bosque", hora, 0.95 - 0.2 * k), NEBLINA[hora], lz.h * 0.2);
  }
  for (let k = 0; k < 4; k++) {
    const color = colorCapa("bosque", hora, Math.max(0, 0.75 - k * 0.25)), suelo = horizonte + Math.floor(lz.h * (0.06 + 0.1 * k));
    const perfil = ruido1d(lz.w, azar, 0.01, 3), alturas = Array.from(perfil, (v) => Math.floor(suelo - v * lz.h * 0.04));
    rellenoPerfil(lz, alturas, color, NEBLINA[hora], lz.h * 0.25);
    const tam = lz.h * (0.1 + 0.09 * k);
    for (let x = azar.uniform(-10, 0); x < lz.w + 10; x += tam * azar.uniform(0.12, 0.3)) {
      const xi = Math.floor(x);
      pino(lz, xi, alturas[Math.min(lz.w - 1, Math.max(0, xi))] + 2, Math.floor(tam * azar.uniform(0.7, 1.3)), color);
    }
    if (k < 3) bruma(lz, NEBLINA[hora], Math.floor(suelo - tam * 0.7), Math.floor(suelo + lz.h * 0.04), 0.5 - 0.1 * k);
  }
}
function mar(lz, azar, hora, horizonte, sol) {
  const { w, h } = lz;
  if (azar() < 0.7) {
    const perfil = ruido1d(w, azar, 0.008, 5), corte = azar.uniform(0.45, 0.6), color = colorCapa("montana", hora, 0.7);
    for (let x = 0; x < w; x++) if (perfil[x] > corte) for (let y = Math.max(0, Math.floor(horizonte - (perfil[x] - corte) * h * 0.5)); y < horizonte; y++) lz.mezclar(x, y, color, 1);
  }
  const agua = colorCapa("mar", hora, 0.2), colorSol = ASTRO[hora][0], fase = azar.uniform(0, 6.28);
  for (let y = horizonte; y < h; y++) {
    const prof = (y - horizonte) / Math.max(1, h - horizonte), espejo = Math.max(0, 2 * horizonte - y - 1), anchoBrillo = w * (0.02 + 0.16 * prof);
    for (let x = 0; x < w; x++) {
      const ola = Math.sin(x * 0.045 / (0.3 + prof) + y * 0.9 + fase) * Math.sin(y * 0.37 + x * 0.011);
      const ex = Math.min(w - 1, Math.max(0, x + Math.floor(ola * 4 * (0.3 + prof))));
      const [r, g, b] = lz.leer(ex, Math.min(espejo, h - 1)), refl = 0.75 - prof * 0.45;
      let c = [r * refl + agua[0] * (1 - refl), g * refl + agua[1] * (1 - refl), b * refl + agua[2] * (1 - refl)];
      c = mezclarC(c, [c[0] * 0.8, c[1] * 0.8, c[2] * 0.85], prof * 0.6);
      const i = (y * w + x) * 3; lz.px[i] = c[0]; lz.px[i + 1] = c[1]; lz.px[i + 2] = c[2];
      const dx = Math.abs(x - sol[0]);
      if (dx < anchoBrillo && ola > 0.25) lz.sumar(x, y, colorSol, (1 - dx / anchoBrillo) * (ola - 0.25) * 1.3);
    }
    if (y === horizonte) for (let x = 0; x < w; x++) lz.mezclar(x, y, NEBLINA[hora], 0.5);
  }
}
function desierto(lz, azar, hora, horizonte) {
  for (let k = 0; k < 4; k++) {
    const prof = 1 - k / 3, fases = [0, 1, 2].map(() => azar.uniform(0, 6.28));
    const frec = [azar.uniform(0.004, 0.008), azar.uniform(0.01, 0.02), azar.uniform(0.025, 0.04)];
    const amp = lz.h * (0.05 + 0.03 * k), base = horizonte + Math.floor(lz.h * (0.02 + 0.1 * k));
    const perfil = [], pend = [];
    for (let x = 0; x < lz.w; x++) {
      let v = 0, d = 0;
      for (let i = 0; i < 3; i++) { v += Math.sin(x * frec[i] + fases[i]) / (i + 1) ** 1.3; d += Math.cos(x * frec[i] + fases[i]) * frec[i] / (i + 1) ** 1.3; }
      perfil.push(Math.floor(base - v * amp)); pend.push(d);
    }
    const maxp = Math.max(...pend.map(Math.abs)) || 1;
    rellenoPerfil(lz, perfil, colorCapa("desierto", hora, prof * 0.85), NEBLINA[hora], lz.h * 0.3, pend.map((d) => Math.min(1, Math.max(0, 0.5 + d / maxp * 0.7))));
  }
}
function edificios(lz, azar, hora, suelo, altoMax, color, ventanas) {
  const luz = hora === "noche" || hora === "atardecer" ? [255, 214, 130] : [150, 190, 220];
  const prob = { noche: 0.45, atardecer: 0.25, amanecer: 0.15, dia: 0.5 }[hora];
  for (let x = azar.randint(-20, 0); x < lz.w;) {
    const ancho = azar.randint(Math.floor(lz.w * 0.03), Math.floor(lz.w * 0.09)), alto = Math.floor(altoMax * azar.uniform(0.35, 1)), tope = suelo - alto;
    for (let y = Math.max(0, tope); y < Math.min(lz.h, suelo + 1); y++) for (let xx = Math.max(0, x); xx < Math.min(lz.w, x + ancho); xx++) lz.mezclar(xx, y, color, 1);
    if (azar() < 0.3) for (let y = Math.max(0, tope - Math.floor(alto / 6)); y < tope; y++) lz.mezclar(x + Math.floor(ancho / 2), y, color, 1);
    if (ventanas) {
      const paso = Math.max(4, Math.floor(ancho / 6)), lado = Math.max(1, Math.floor(paso / 2));
      for (let wy = tope + 4; wy < suelo - 3; wy += paso) for (let wx = x + 3; wx < x + ancho - 3; wx += paso) {
        if (azar() < prob) { const a = azar.uniform(0.5, 1) * (hora === "dia" ? 0.55 : 1); for (let dy = 0; dy < lado; dy++) for (let dx = 0; dx < lado; dx++) lz.mezclar(wx + dx, wy + dy, luz, a); }
      }
    }
    x += ancho + azar.randint(0, 4);
  }
}
function ciudad(lz, azar, hora, horizonte) {
  for (let k = 0; k < 3; k++) {
    const color = colorCapa("ciudad", hora, (1 - k / 2) * 0.8), suelo = horizonte + Math.floor(lz.h * (0.05 + 0.12 * k));
    edificios(lz, azar, hora, suelo, lz.h * (0.28 + 0.12 * k), color, k > 0);
  }
  const calle = colorCapa("ciudad", hora, 0);
  for (let y = Math.floor(horizonte + lz.h * 0.29); y < lz.h; y++) lz.fila(y, calle);
}
function espacio(lz, azar, ruido, animo) {
  const { w, h } = lz, [c1, c2] = NEBULOSAS[animo];
  const ox = azar.uniform(0, 40), oy = azar.uniform(0, 40), ang = azar.uniform(-0.6, 0.6), ca = Math.cos(ang), sa = Math.sin(ang), s = 3 / w;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const u = (x - w / 2) * ca + (y - h / 2) * sa, v = -(x - w / 2) * sa + (y - h / 2) * ca;
    const banda = Math.exp(-((v / (h * 0.32)) ** 2)), n = ruido.fractal(u * s + ox, v * s * 2 + oy, 5), m = ruido.fractal(u * s * 2 + oy, v * s * 2 + ox, 3);
    const a = Math.max(0, n - 0.35) * 1.9 * banda;
    if (a > 0) { lz.sumar(x, y, mezclarC(c1, c2, m), a * 0.85); if (n > 0.62) lz.sumar(x, y, [255, 240, 230], (n - 0.62) * 1.4 * banda); }
  }
  estrellas(lz, azar, h, Math.floor(w * h / 90));
  const r = Math.floor(h * azar.uniform(0.16, 0.26)), cx = Math.floor(w * azar.choice([0.2, 0.78])) + azar.randint(-20, 20), cy = Math.floor(h * azar.uniform(0.55, 0.75));
  const base = mezclarC(c2, [200, 190, 170], 0.4), [lx, ly] = cx > w / 2 ? [-0.6, -0.5] : [0.6, -0.5], anillo = azar() < 0.55;
  for (let y = Math.max(0, cy - r - 4); y < Math.min(h, cy + r + 5); y++) for (let x = Math.max(0, cx - r - 4); x < Math.min(w, cx + r + 5); x++) {
    const dx = (x - cx) / r, dy = (y - cy) / r, d2 = dx * dx + dy * dy;
    if (d2 <= 1) {
      const luz = Math.max(0, dx * lx + dy * ly + Math.sqrt(1 - d2) * 0.6);
      let c = mezclarC(base, mezclarC(c1, [40, 30, 30], 0.4), ruido.fractal(dx * 1.5 + 3, dy * 9 + 5, 3));
      c = [c[0] * (0.06 + luz), c[1] * (0.06 + luz), c[2] * (0.08 + luz)];
      lz.mezclar(x, y, c, Math.min(1, (1 - Math.sqrt(d2)) * r));
    } else if (d2 < 1.12) {
      const atm = (1.12 - d2) / 0.12;
      lz.sumar(x, y, c2, atm * atm * 0.55 * Math.max(0.2, dx * lx + dy * ly + 0.5));
    }
  }
  if (anillo) {
    const inc = azar.uniform(0.18, 0.3);
    for (let y = Math.max(0, cy - r); y < Math.min(h, cy + r); y++) for (let x = Math.max(0, cx - Math.floor(r * 2.3)); x < Math.min(w, cx + Math.floor(r * 2.3)); x++) {
      const dx = (x - cx) / r, dy = (y - cy) / (r * inc), d = Math.hypot(dx, dy);
      if (d > 1.35 && d < 2.2 && (dy > 0 || dx * dx + ((y - cy) / r) ** 2 > 1)) {
        lz.mezclar(x, y, mezclarC(base, [230, 220, 200], 0.5), (0.35 + 0.35 * Math.sin(d * 23)) * (1 - Math.abs(d - 1.77) / 0.43) * 0.8);
      }
    }
  }
}
function lluvia(lz, azar, cantidad) {
  for (let k = 0; k < cantidad; k++) {
    const x = Math.floor(azar() * lz.w), y = Math.floor(azar() * lz.h), largo = azar.randint(6, 16);
    for (let j = 0; j < largo; j++) lz.mezclar(x - Math.floor(j / 4), y + j, [200, 210, 230], 0.22 * (1 - j / largo));
  }
}
function niebla(lz, azar, ruido, color, desde) {
  const ox = azar.uniform(0, 30);
  for (let y = desde; y < lz.h; y++) {
    const t = (y - desde) / Math.max(1, lz.h - desde);
    for (let x = 0; x < lz.w; x++) lz.mezclar(x, y, color, Math.max(0, ruido.fractal(x * 3 / lz.w + ox, y * 9 / lz.h, 3) - 0.3) * (0.3 + 0.5 * Math.sin(t * Math.PI)));
  }
}
function etalonarA(lz, azar, animo, datos) {
  const [sat, tinte, contraste] = ETALONADO[animo], { w, h, px } = lz;
  for (let y = 0; y < h; y++) {
    const vy = 1 - 0.3 * ((y / h - 0.5) * 2) ** 2;
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 3, o = (y * w + x) * 4, v = (1 - 0.35 * ((x / w - 0.5) * 2) ** 2) * vy, n = (azar() - 0.5) * 8;
      const r = px[i], g = px[i + 1], b = px[i + 2], lum = r * 0.3 + g * 0.59 + b * 0.11;
      for (let c = 0; c < 3; c++) {
        let val = (lum + ([r, g, b][c] - lum) * sat) * tinte[c];
        val = ((Math.min(255, Math.max(0, val)) / 255 - 0.5) * contraste + 0.5) * 255 * v + n;
        datos[o + c] = val;
      }
      datos[o + 3] = 255;
    }
  }
}

// Pinta en un canvas nuevo y lo devuelve. p = {escena, hora, animo, semilla}
export function pintarPaisaje(p, ancho = 800, alto = 500) {
  const azar = crearAzar((p.semilla ^ 0x1a6e) >>> 0), ruido = new Ruido2D(azar), lz = new Lienzo(ancho, alto);
  const { escena, hora, animo } = p;
  if (escena === "espacio") {
    for (let i = 0; i < lz.px.length; i += 3) { lz.px[i] = 4; lz.px[i + 1] = 5; lz.px[i + 2] = 14; }
    espacio(lz, azar, ruido, animo);
  } else {
    const horizonte = Math.floor(alto * ({ mar: 0.56, desierto: 0.58, ciudad: 0.5 }[escena] || 0.55));
    cielo(lz, hora, horizonte);
    if (hora === "noche") estrellas(lz, azar, horizonte, Math.floor(ancho * horizonte / 120));
    const sol = astro(lz, azar, hora, horizonte, ruido);
    if (hora !== "noche" || animo === "triste" || animo === "misterio") nubes(lz, azar, ruido, hora, horizonte, { triste: 1, misterio: 0.8, epico: 0.7 }[animo] || 0.35);
    ({ montana: () => montanas(lz, azar, hora, horizonte), bosque: () => bosque(lz, azar, hora, horizonte), mar: () => mar(lz, azar, hora, horizonte, sol),
      desierto: () => desierto(lz, azar, hora, horizonte), ciudad: () => ciudad(lz, azar, hora, horizonte) })[escena]();
    if (animo === "misterio") niebla(lz, azar, ruido, NEBLINA[hora], Math.floor(horizonte * 0.7));
    if (animo === "triste") lluvia(lz, azar, Math.floor(ancho * alto / 260));
  }
  const canvas = document.createElement("canvas"); canvas.width = ancho; canvas.height = alto;
  const ctx = canvas.getContext("2d"), img = ctx.createImageData(ancho, alto);
  etalonarA(lz, azar, animo, img.data);
  ctx.putImageData(img, 0, 0);
  return canvas;
}
