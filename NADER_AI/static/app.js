/* NADER AI · interfaz
 * Dos motores de voz:
 *  - "edge": POST /api/audio devuelve un MP3 que se reproduce en <audio>.
 *  - "navegador": SpeechSynthesisUtterance (voces del sistema operativo / navegador).
 * La pausa, la reanudación y la detención actúan solo sobre la reproducción local,
 * nunca sobre las solicitudes HTTP en curso.
 */
"use strict";

const API = {
  health: "/api/health",
  voices: "/api/voices",
  audio: "/api/audio",
  chat: "/api/chat",
  images: "/api/images",
};

const $ = (id) => document.getElementById(id);
const el = {
  texto: $("texto"), counter: $("counter"), motor: $("motor"), voz: $("voz"),
  velocidad: $("velocidad"), velocidadValor: $("velocidadValor"), motorNota: $("motorNota"),
  generar: $("btnGenerar"), pausa: $("btnPausa"), reanudar: $("btnReanudar"), detener: $("btnDetener"),
  dictar: $("btnDictar"), audio: $("audio"), playerBox: $("playerBox"),
  status: $("status"), statusText: $("statusText"), error: $("error"),
  modules: $("modules"), version: $("version"),
  iaEstado: $("iaEstado"), iaNota: $("iaNota"), preguntar: $("btnPreguntar"),
  narrarRespuesta: $("btnNarrarRespuesta"), respuesta: $("respuesta"),
  imgEstado: $("imgEstado"), imgZone: $("imgZone"), imgPrompt: $("imgPrompt"),
  imgBtn: $("btnImagen"), imgOut: $("imgOut"), imgNota: $("imgNota"),
};

const state = {
  maxChars: 5000,
  edgeVoices: [],
  defaultEdgeVoice: "",
  playback: "idle",      // idle | generating | playing | paused | ended
  requestSeq: 0,         // la solicitud más reciente; las anteriores se descartan
  controller: null,      // AbortController de la solicitud de audio en curso
  audioUrl: null,
  speechQueue: null,     // narración del navegador en curso
  llmReady: false,
  conversationId: null,
  ultimaRespuesta: "",
};

/* ---------- Estado visible ---------- */
function setStatus(text, tone = "idle") {
  el.status.dataset.tone = tone;
  el.statusText.textContent = text;
}
function showError(message) {
  el.error.textContent = message;
  el.error.hidden = !message;
}
function setPlayback(next) {
  state.playback = next;
  const generating = next === "generating";
  el.generar.disabled = generating;
  el.pausa.disabled = next !== "playing";
  el.reanudar.disabled = next !== "paused";
  el.detener.disabled = !["generating", "playing", "paused"].includes(next);
  el.motor.disabled = generating;
  el.voz.disabled = generating;
  el.generar.textContent = generating ? "Generando…" : "Generar y reproducir";
}

/* ---------- Errores HTTP ---------- */
async function errorFromResponse(res) {
  try {
    const data = await res.json();
    if (data && data.error && data.error.message) return data.error.message;
  } catch (_) { /* respuesta sin JSON */ }
  if (res.status === 503) return "El servidor está ocupado o el módulo no está configurado.";
  return `El servidor respondió con un error (${res.status}).`;
}
function connectionError(err) {
  return err && err.name === "AbortError"
    ? null
    : "Error de conexión: no se pudo contactar con el servidor de NADER AI. ¿Sigue abierto uvicorn?";
}

/* ---------- Contador ---------- */
function updateCounter() {
  const n = el.texto.value.length;
  el.counter.textContent = `${n.toLocaleString("es-CO")} / ${state.maxChars.toLocaleString("es-CO")}`;
  el.counter.dataset.over = String(n > state.maxChars);
}

/* ---------- Velocidad ---------- */
function rateValue() { return Number(el.velocidad.value) || 0; }
function updateRateLabel() {
  const r = rateValue();
  el.velocidadValor.textContent = `${r > 0 ? "+" : ""}${r}%`;
}
// La Web Speech API admite 0.1–10; usamos 0.5–1.5 para que -50..+50 signifique lo mismo en ambos motores.
function browserRate() { return Math.min(10, Math.max(0.1, 1 + rateValue() / 100)); }

/* ---------- Voces ---------- */
function fillEdgeVoices() {
  el.voz.textContent = "";
  for (const v of state.edgeVoices) {
    const opt = new Option(`${v.name} · ${v.gender}`, v.id);
    if (v.available === false) { opt.disabled = true; opt.textContent += " (no disponible)"; }
    el.voz.add(opt);
  }
  if (state.defaultEdgeVoice) el.voz.value = state.defaultEdgeVoice;
}

function browserVoices() {
  if (!("speechSynthesis" in window)) return [];
  const all = speechSynthesis.getVoices();
  const es = all.filter((v) => (v.lang || "").toLowerCase().startsWith("es"));
  const rank = (v) => {
    const lang = (v.lang || "").toLowerCase().replace("_", "-");
    if (lang === "es-co") return 0;
    if (/es-(419|mx|us|ar|cl|pe|ve|ec)/.test(lang)) return 1;
    return 2;
  };
  return es.sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name));
}

function fillBrowserVoices() {
  el.voz.textContent = "";
  const voces = browserVoices();
  if (!voces.length) {
    el.voz.add(new Option("Sin voces en español (se usará la voz por defecto)", ""));
    return;
  }
  for (const v of voces) el.voz.add(new Option(`${v.name} · ${v.lang}`, v.voiceURI));
}

function updateEngineUI() {
  const edge = el.motor.value === "edge";
  el.playerBox.dataset.off = String(!edge);
  if (edge) {
    fillEdgeVoices();
    el.motorNota.textContent = "Edge TTS genera un MP3 en el servicio de voz de Microsoft: necesita conexión a Internet.";
  } else if (!("speechSynthesis" in window)) {
    el.voz.textContent = "";
    el.motorNota.textContent = "Este navegador no ofrece síntesis de voz. Usa el motor Edge TTS.";
  } else {
    fillBrowserVoices();
    el.motorNota.textContent = "Usa las voces instaladas en tu navegador o sistema operativo; la lista cambia según el equipo.";
  }
}

/* ---------- Reproducción: detener todo ---------- */
function stopPlayback() {
  if (state.speechQueue) {
    state.speechQueue.cancelled = true;
    state.speechQueue = null;
    speechSynthesis.cancel();
  }
  if (!el.audio.paused) el.audio.pause();
  if (el.audio.src) el.audio.currentTime = 0;
}

/* ---------- Motor Edge (MP3 desde el servidor) ---------- */
async function generateEdge(text) {
  const seq = ++state.requestSeq;
  if (state.controller) state.controller.abort();
  const controller = new AbortController();
  state.controller = controller;
  setPlayback("generating");
  setStatus("Generando audio…", "busy");

  let res;
  try {
    res = await fetch(API.audio, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice: el.voz.value, rate: rateValue() }),
      signal: controller.signal,
    });
  } catch (err) {
    if (seq !== state.requestSeq) return;
    const msg = connectionError(err);
    finishWithError(msg);
    return;
  }
  if (seq !== state.requestSeq) return; // llegó tarde: hay una solicitud más reciente

  if (!res.ok) {
    finishWithError(await errorFromResponse(res));
    return;
  }
  let blob;
  try {
    blob = await res.blob();
  } catch (err) {
    if (seq !== state.requestSeq) return;
    finishWithError(connectionError(err));
    return;
  }
  if (seq !== state.requestSeq) return;
  state.controller = null;

  if (state.audioUrl) URL.revokeObjectURL(state.audioUrl);
  state.audioUrl = URL.createObjectURL(blob);
  el.audio.src = state.audioUrl;
  setPlayback("ended");
  setStatus("Audio generado.", "ok");
  try {
    await el.audio.play();
  } catch (_) {
    setStatus("Audio generado. Pulsa reproducir en el reproductor.", "ok");
  }
}

function finishWithError(message) {
  state.controller = null;
  setPlayback("idle");
  if (message) {
    showError(message);
    setStatus(message.startsWith("Error de conexión") ? "Error de conexión." : "No se generó el audio.", "err");
  } else {
    setStatus("Generación cancelada.", "idle");
  }
}

el.audio.addEventListener("play", () => {
  if (el.motor.value !== "edge") return;
  setPlayback("playing");
  setStatus("Reproducción en curso.", "play");
});
el.audio.addEventListener("pause", () => {
  if (el.motor.value !== "edge" || el.audio.ended || state.playback === "generating") return;
  if (el.audio.currentTime === 0) return; // lo maneja "Detener"
  setPlayback("paused");
  setStatus("Reproducción pausada.", "pause");
});
el.audio.addEventListener("ended", () => {
  setPlayback("ended");
  setStatus("Reproducción finalizada.", "ok");
});
el.audio.addEventListener("error", () => {
  if (!el.audio.src || state.playback === "generating") return;
  setPlayback("idle");
  showError("El navegador no pudo reproducir el archivo de audio.");
  setStatus("Error de reproducción.", "err");
});

/* ---------- Motor del navegador ---------- */
function splitForSpeech(text) {
  // Chrome corta las frases largas: se narra por fragmentos de hasta ~220 caracteres.
  const frases = text.replace(/\s+/g, " ").match(/[^.!?¡¿;:\n]+[.!?;:]*\s*/g) || [text];
  const partes = [];
  let actual = "";
  for (const f of frases) {
    if ((actual + f).length > 220 && actual) { partes.push(actual.trim()); actual = ""; }
    if (f.length > 220) {
      for (let i = 0; i < f.length; i += 220) partes.push(f.slice(i, i + 220).trim());
    } else {
      actual += f;
    }
  }
  if (actual.trim()) partes.push(actual.trim());
  return partes.filter(Boolean);
}

function speakBrowser(text) {
  if (!("speechSynthesis" in window)) {
    showError("Este navegador no ofrece síntesis de voz. Cambia al motor Edge TTS.");
    setStatus("Voz no disponible.", "err");
    return;
  }
  stopPlayback();
  const voces = speechSynthesis.getVoices();
  const voz = voces.find((v) => v.voiceURI === el.voz.value) || browserVoices()[0] || null;
  if (el.voz.value && !voces.some((v) => v.voiceURI === el.voz.value)) {
    showError("Voz no disponible en este navegador; se usará otra voz en español.");
  }
  const queue = { cancelled: false };
  state.speechQueue = queue;
  const partes = splitForSpeech(text);
  partes.forEach((parte, i) => {
    const u = new SpeechSynthesisUtterance(parte);
    if (voz) { u.voice = voz; u.lang = voz.lang; } else { u.lang = "es-CO"; }
    u.rate = browserRate();
    if (i === 0) u.onstart = () => { if (!queue.cancelled) { setPlayback("playing"); setStatus("Reproducción en curso.", "play"); } };
    if (i === partes.length - 1) {
      u.onend = () => {
        if (queue.cancelled || state.speechQueue !== queue) return;
        state.speechQueue = null;
        setPlayback("ended");
        setStatus("Reproducción finalizada.", "ok");
      };
    }
    u.onerror = (e) => {
      if (queue.cancelled || e.error === "interrupted" || e.error === "canceled") return;
      queue.cancelled = true;
      state.speechQueue = null;
      speechSynthesis.cancel();
      setPlayback("idle");
      showError(`La voz del navegador falló (${e.error || "error desconocido"}).`);
      setStatus("Error de reproducción.", "err");
    };
    speechSynthesis.speak(u);
  });
}

/* ---------- Acciones ---------- */
function narrate(text) {
  showError("");
  text = (text || "").trim();
  if (!text) {
    showError("Texto vacío: escribe algo para narrar.");
    setStatus("Texto vacío.", "err");
    el.texto.focus();
    return;
  }
  if (text.length > state.maxChars) {
    showError(`El texto supera el máximo de ${state.maxChars.toLocaleString("es-CO")} caracteres.`);
    setStatus("Texto demasiado largo.", "err");
    return;
  }
  stopPlayback();
  if (el.motor.value === "edge") generateEdge(text);
  else speakBrowser(text);
}

el.generar.addEventListener("click", () => narrate(el.texto.value));

el.pausa.addEventListener("click", () => {
  if (el.motor.value === "edge") { el.audio.pause(); return; }
  if (state.speechQueue) {
    speechSynthesis.pause();
    setPlayback("paused");
    setStatus("Reproducción pausada.", "pause");
  }
});

el.reanudar.addEventListener("click", () => {
  if (el.motor.value === "edge") {
    el.audio.play().catch(() => showError("El navegador no permitió reanudar el audio."));
    return;
  }
  if (state.speechQueue) {
    speechSynthesis.resume();
    setPlayback("playing");
    setStatus("Reproducción en curso.", "play");
  }
});

el.detener.addEventListener("click", () => {
  if (state.playback === "generating") {
    state.requestSeq++;               // invalida la respuesta pendiente
    if (state.controller) state.controller.abort(); // el servidor cancela la generación
    state.controller = null;
    setPlayback("idle");
    setStatus("Generación cancelada.", "idle");
    return;
  }
  stopPlayback();
  setPlayback("idle");
  setStatus("Reproducción detenida.", "idle");
});

el.motor.addEventListener("change", () => {
  stopPlayback();
  setPlayback("idle");
  updateEngineUI();
  setStatus("Sistema listo.", "ok");
});

el.velocidad.addEventListener("input", updateRateLabel);
el.texto.addEventListener("input", updateCounter);
el.texto.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); narrate(el.texto.value); }
});

if ("speechSynthesis" in window) {
  speechSynthesis.addEventListener?.("voiceschanged", () => {
    if (el.motor.value === "navegador" && state.playback !== "playing") fillBrowserVoices();
  });
}

/* ---------- Dictado (reconocimiento de voz del navegador) ---------- */
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (Recognition) {
  el.dictar.hidden = false;
  let rec = null;
  el.dictar.addEventListener("click", () => {
    if (rec) { rec.stop(); return; }
    rec = new Recognition();
    rec.lang = "es-CO";
    rec.interimResults = false;
    rec.continuous = true;
    rec.onresult = (e) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) {
          const t = e.results[i][0].transcript.trim();
          el.texto.value = (el.texto.value ? el.texto.value.replace(/\s*$/, " ") : "") + t;
          updateCounter();
        }
      }
    };
    rec.onerror = (e) => {
      showError(e.error === "not-allowed" ? "Permiso de micrófono denegado." : `El dictado falló (${e.error}).`);
    };
    rec.onend = () => { rec = null; el.dictar.setAttribute("aria-pressed", "false"); el.dictar.textContent = "🎙 Dictar"; };
    rec.start();
    el.dictar.setAttribute("aria-pressed", "true");
    el.dictar.textContent = "■ Detener dictado";
  });
}

/* ---------- IA generativa (solo si el servidor tiene un proveedor configurado) ---------- */
el.preguntar.addEventListener("click", async () => {
  const mensaje = el.texto.value.trim();
  if (!mensaje) { showError("Texto vacío: escribe una pregunta."); return; }
  showError("");
  el.preguntar.disabled = true;
  el.respuesta.textContent = "Pensando…";
  try {
    const res = await fetch(API.chat, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: mensaje, conversation_id: state.conversationId }),
    });
    if (!res.ok) throw new Error(await errorFromResponse(res));
    const data = await res.json();
    state.conversationId = data.conversation_id;
    state.ultimaRespuesta = data.reply;
    el.respuesta.textContent = data.reply;
    el.narrarRespuesta.disabled = false;
  } catch (err) {
    el.respuesta.textContent = "";
    showError(err instanceof TypeError ? connectionError(err) : err.message);
  } finally {
    el.preguntar.disabled = !state.llmReady;
  }
});
el.narrarRespuesta.addEventListener("click", () => narrate(state.ultimaRespuesta));

el.imgBtn.addEventListener("click", async () => {
  const prompt = el.imgPrompt.value.trim();
  if (!prompt) { showError("Describe la imagen que quieres generar."); return; }
  el.imgBtn.disabled = true;
  try {
    const res = await fetch(API.images, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    if (!res.ok) throw new Error(await errorFromResponse(res));
    el.imgOut.src = URL.createObjectURL(await res.blob());
    el.imgOut.hidden = false;
  } catch (err) {
    showError(err instanceof TypeError ? connectionError(err) : err.message);
  } finally {
    el.imgBtn.disabled = false;
  }
});

/* ---------- Arranque ---------- */
const MODULE_LABELS = {
  voz_edge: "Voz Edge", voz_navegador: "Voz navegador", llm: "IA texto",
  imagenes: "Imágenes", transcripcion: "Transcripción", memoria: "Memoria",
};
const STATE_LABELS = {
  completo: "completo", configurado: "configurado", no_configurado: "sin configurar",
  pendiente: "pendiente", activada: "activada", desactivada: "desactivada",
};

function renderModules(modules) {
  el.modules.textContent = "";
  for (const [key, info] of Object.entries(modules)) {
    const li = document.createElement("li");
    li.dataset.state = info.estado;
    li.textContent = `${MODULE_LABELS[key] || key}: ${STATE_LABELS[info.estado] || info.estado}`;
    el.modules.append(li);
  }
}

async function init() {
  updateRateLabel();
  setPlayback("idle");
  try {
    const [health, voices] = await Promise.all([
      fetch(API.health).then((r) => r.json()),
      fetch(API.voices).then((r) => r.json()),
    ]);
    el.version.textContent = `v${health.version}`;
    state.maxChars = health.limits.max_text_length;
    state.edgeVoices = voices.voices;
    state.defaultEdgeVoice = voices.default;
    renderModules(health.modules);

    const llm = health.modules.llm;
    state.llmReady = llm.estado === "configurado";
    el.iaEstado.dataset.state = llm.estado;
    el.iaEstado.textContent = state.llmReady ? `proveedor: ${llm.proveedor}` : "módulo sin configurar";
    el.preguntar.disabled = !state.llmReady;
    el.iaNota.textContent = state.llmReady
      ? "Escribe tu pregunta en el campo de texto y pulsa «Preguntar a NADER AI»."
      : "Integración pendiente: define NADER_LLM_PROVIDER y su clave en .env para activar las respuestas. No se muestran respuestas simuladas.";

    const img = health.modules.imagenes;
    el.imgEstado.dataset.state = img.estado;
    el.imgEstado.textContent = img.estado === "configurado" ? "configurado" : "pendiente";
    el.imgZone.hidden = img.estado !== "configurado";
    el.imgNota.textContent = img.estado === "configurado" ? "" : "Integración pendiente: aún no hay un proveedor de imágenes conectado.";

    updateEngineUI();
    updateCounter();
    setStatus("Sistema listo.", "ok");
  } catch (err) {
    updateEngineUI();
    updateCounter();
    showError("Error de conexión: no se pudo cargar la configuración del servidor.");
    setStatus("Error de conexión.", "err");
  }
}

init();
