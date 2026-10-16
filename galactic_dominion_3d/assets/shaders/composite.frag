#version 150
// Composición final: escena HDR + bloom, mapeo de tonos filmico y viñeta.
uniform sampler2D scene;
uniform sampler2D bloom_a;
uniform sampler2D bloom_b;
uniform float bloom_strength;
uniform float exposure;
uniform float vignette;
in vec2 uv;
out vec4 frag;

vec3 aces(vec3 x) {
    // Aproximación de Narkowicz a la curva ACES.
    return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}

void main() {
    vec3 hdr = texture(scene, uv).rgb;
    vec3 glow = texture(bloom_a, uv).rgb * 0.6 + texture(bloom_b, uv).rgb * 0.9;
    vec3 color = aces((hdr + glow * bloom_strength) * exposure);
    vec2 d = uv - 0.5;
    color *= 1.0 - vignette * dot(d, d) * 1.6;
    frag = vec4(color, 1.0);
}
