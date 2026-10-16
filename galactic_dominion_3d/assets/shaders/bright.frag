#version 150
// Extrae las zonas más brillantes de la escena (base del bloom).
uniform sampler2D src;
uniform float threshold;
in vec2 uv;
out vec4 frag;
void main() {
    vec3 c = texture(src, uv).rgb;
    float lum = dot(c, vec3(0.2126, 0.7152, 0.0722));
    float knee = max(lum - threshold, 0.0) / max(lum, 1e-4);
    frag = vec4(c * knee, 1.0);
}
