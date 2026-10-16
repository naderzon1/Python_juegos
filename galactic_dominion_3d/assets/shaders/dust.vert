#version 150
// Polvo espacial: los puntos se repiten en una caja que sigue a la cámara,
// así siempre hay partículas cerca que dan sensación de velocidad.
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform vec3 cam_pos;
uniform float box_size;
in vec4 p3d_Vertex;
in vec4 p3d_Color;
out vec4 v_color;
void main() {
    vec3 rel = mod(p3d_Vertex.xyz - cam_pos + box_size * 0.5, box_size) - box_size * 0.5;
    vec3 world = cam_pos + rel;
    gl_Position = p3d_ModelViewProjectionMatrix * vec4(world, 1.0);
    float fade = 1.0 - smoothstep(box_size * 0.25, box_size * 0.5, length(rel));
    v_color = p3d_Color * fade;
}
