#version 150
// Superposición del salto hiperespacial: estelas radiales, distorsión y destello.
uniform float progress;
uniform float osg_FrameTime;
uniform vec4 tint;
in vec2 uv;
out vec4 frag;
float hash(float n) { return fract(sin(n) * 43758.5453); }
void main() {
    vec2 p = uv * 2.0 - 1.0;
    p.x *= 1.7;
    float r = length(p);
    float a = atan(p.y, p.x);
    float lane = floor(a * 60.0);
    float speed = 0.6 + hash(lane) * 1.4;
    float streak = step(0.72, hash(lane + 7.0)) * smoothstep(0.0, 0.25, fract(r * 1.5 - osg_FrameTime * speed * 3.0) );
    streak *= smoothstep(0.1, 0.9, r) * progress;
    float tunnel = smoothstep(1.4, 0.0, r) * progress * 0.6;
    float flash = smoothstep(0.85, 1.0, progress);
    vec3 col = tint.rgb * (streak * 1.6 + tunnel) + vec3(flash);
    float alpha = clamp(streak + tunnel * 0.8 + flash + progress * 0.25, 0.0, 1.0);
    frag = vec4(col, alpha);
}
