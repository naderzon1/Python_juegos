// Estudio Generativo: modelo de lenguaje local, en un Worker para no congelar la página.
// Usa transformers.js (Hugging Face) con un modelo pequeño que se descarga una vez
// desde huggingface.co y queda guardado en el navegador. No usa claves ni servidores propios.
// Paquete oficial para navegador, servido por jsDelivr (sw.js lo guarda para usarlo sin conexión).
import { pipeline, TextStreamer, InterruptableStoppingCriteria, env } from "https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.3.1/dist/transformers.min.js";

env.allowLocalModels = false;  // los modelos vienen del Hub; el navegador los guarda en caché

// En orden de preferencia; si uno no carga se prueba el siguiente.
const MODELOS = [
  { id: "onnx-community/Qwen2.5-0.5B-Instruct", dtype: "q4", plantilla: {} },
  { id: "onnx-community/Qwen3-0.6B-ONNX", dtype: "q4", plantilla: { enable_thinking: false } },
];

let generador = null, modelo = null;
const parada = new InterruptableStoppingCriteria();

async function cargar(device) {
  let ultimo;
  for (const m of MODELOS) {
    try {
      generador = await pipeline("text-generation", m.id, {
        dtype: m.dtype, device,
        progress_callback: (p) => {
          if (p.status === "progress_total") self.postMessage({ tipo: "progreso", cargado: p.loaded, total: p.total });
        },
      });
      modelo = m;
      return m.id;
    } catch (e) { ultimo = e; }
  }
  throw ultimo || new Error("ningún modelo disponible");
}

self.onmessage = async (e) => {
  const d = e.data || {};
  if (d.tipo === "cargar") {
    try {
      let device = d.webgpu ? "webgpu" : "wasm", id;
      try { id = await cargar(device); }
      catch (err) {
        if (device !== "webgpu") throw err;
        device = "wasm"; id = await cargar(device);  // WebGPU falló: CPU
      }
      self.postMessage({ tipo: "listo", modelo: id, device });
    } catch (err) {
      self.postMessage({ tipo: "error", mensaje: String((err && err.message) || err) });
    }
  } else if (d.tipo === "generar") {
    if (!generador) { self.postMessage({ tipo: "error", id: d.id, mensaje: "modelo no cargado" }); return; }
    parada.reset();
    let texto = "";
    const streamer = new TextStreamer(generador.tokenizer, {
      skip_prompt: true, skip_special_tokens: true,
      callback_function: (t) => { texto += t; self.postMessage({ tipo: "trozo", id: d.id, texto: t }); },
    });
    try {
      await generador(d.mensajes, {
        max_new_tokens: d.max || 450, do_sample: true, temperature: 0.7, top_p: 0.9, repetition_penalty: 1.12,
        streamer, stopping_criteria: parada, tokenizer_encode_kwargs: modelo.plantilla,
      });
      self.postMessage({ tipo: "fin", id: d.id, interrumpido: parada.interrupted });
    } catch (err) {
      self.postMessage({ tipo: "error", id: d.id, mensaje: String((err && err.message) || err), texto });
    }
  } else if (d.tipo === "parar") {
    parada.interrupt();
  }
};
