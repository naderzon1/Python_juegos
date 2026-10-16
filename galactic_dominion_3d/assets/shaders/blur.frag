#version 150
// Desenfoque gaussiano separable de 9 muestras.
uniform sampler2D src;
uniform vec2 direction;
in vec2 uv;
out vec4 frag;
void main() {
    vec2 texel = direction / vec2(textureSize(src, 0));
    vec3 sum = texture(src, uv).rgb * 0.2270270;
    sum += texture(src, uv + texel * 1.3846154).rgb * 0.3162162;
    sum += texture(src, uv - texel * 1.3846154).rgb * 0.3162162;
    sum += texture(src, uv + texel * 3.2307692).rgb * 0.0702703;
    sum += texture(src, uv - texel * 3.2307692).rgb * 0.0702703;
    frag = vec4(sum, 1.0);
}
