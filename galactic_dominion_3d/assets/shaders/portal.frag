#version 150
// Vórtice del portal de salto: espiral animada en coordenadas polares.
uniform vec4 color_a;
uniform vec4 color_b;
uniform float osg_FrameTime;
uniform float strength;
in vec2 uv;
out vec4 frag;
void main() {
    vec2 p = uv * 2.0 - 1.0;
    float r = length(p);
    float a = atan(p.y, p.x);
    float swirl = 0.5 + 0.5 * sin(a * 5.0 + r * 14.0 - osg_FrameTime * 4.5);
    float swirl2 = 0.5 + 0.5 * sin(a * 3.0 - r * 9.0 + osg_FrameTime * 2.0);
    float core = clamp(1.0 - r, 0.0, 1.0);
    vec3 col = mix(color_a.rgb, color_b.rgb, swirl * swirl2) * pow(core, 1.2) * 1.8;
    col += vec3(1.0) * pow(core, 7.0) * 2.0;
    col *= smoothstep(1.0, 0.82, r) * strength;
    frag = vec4(col, 1.0);
}
