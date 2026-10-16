#version 150
// Escudo de energía: borde fresnel, destello en el punto de impacto y ondas.
uniform vec3 cam_pos;
uniform vec4 shield_color;
uniform vec3 hit_dir;
uniform float intensity;
uniform float osg_FrameTime;
uniform vec3 center;
in vec3 v_normal;
in vec3 v_pos;
out vec4 frag;
void main() {
    vec3 n = normalize(v_normal);
    vec3 v = normalize(cam_pos - v_pos);
    float rim = pow(1.0 - abs(dot(n, v)), 2.2);
    float facing = dot(normalize(v_pos - center), hit_dir);
    float spot = smoothstep(0.35, 1.0, facing) * step(0.01, length(hit_dir));
    float ripple = 0.5 + 0.5 * sin(facing * 26.0 - osg_FrameTime * 22.0);
    float bands = 0.5 + 0.5 * sin(v_pos.z * 0.35 + osg_FrameTime * 2.5);
    float value = rim * (0.55 + 0.25 * bands) + spot * (0.5 + 0.5 * ripple);
    frag = vec4(shield_color.rgb * value * intensity, 1.0);
}
