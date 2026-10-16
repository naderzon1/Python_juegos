#version 150
// Vértice común para efectos con borde luminoso (atmósferas, escudos, campos).
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
out vec3 v_normal;
out vec3 v_pos;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    v_pos = (p3d_ModelMatrix * p3d_Vertex).xyz;
    v_normal = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
}
