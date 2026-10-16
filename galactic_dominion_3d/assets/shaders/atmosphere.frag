#version 150
// Halo atmosférico: más intenso en el borde del planeta y en el lado iluminado.
uniform vec3 cam_pos;
uniform vec3 sun_dir;
uniform vec4 atmo_color;
uniform float power;
in vec3 v_normal;
in vec3 v_pos;
out vec4 frag;
void main() {
    vec3 n = normalize(v_normal);
    vec3 v = normalize(cam_pos - v_pos);
    float rim = pow(1.0 - abs(dot(n, v)), power);
    float light = clamp(dot(n, -sun_dir) * 0.85 + 0.3, 0.0, 1.0);
    frag = vec4(atmo_color.rgb * rim * light * atmo_color.a, 1.0);
}
