"""Prueba de instalación de TensorFlow.

Comprueba, en orden:
  1. que TensorFlow se importa y qué versión es
  2. qué dispositivos ve (CPU / GPU)
  3. una operación básica con tensores
  4. el entrenamiento de un modelo mínimo (aprende y = 2x - 1)

Uso:  python test_tensorflow.py
"""
import os
import sys

# silencia los avisos informativos de TensorFlow al arrancar
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

try:
    import numpy as np
    import tensorflow as tf
except ImportError as e:
    print(f"ERROR: no se pudo importar TensorFlow ({e})")
    print(f"Python en uso: {sys.version.split()[0]}  ->  {sys.executable}")
    print("Instálalo con:  pip install tensorflow")
    sys.exit(1)


def probar_version():
    print(f"Python      : {sys.version.split()[0]}")
    print(f"TensorFlow  : {tf.__version__}")
    print(f"Keras       : {tf.keras.__version__}")
    print(f"NumPy       : {np.__version__}")


def probar_dispositivos():
    gpus = tf.config.list_physical_devices("GPU")
    print(f"CPU         : {len(tf.config.list_physical_devices('CPU'))}")
    print(f"GPU         : {len(gpus)}" + (f"  {[g.name for g in gpus]}" if gpus else "  (se usará CPU)"))


def probar_tensores():
    a = tf.constant([[1.0, 2.0], [3.0, 4.0]])
    b = tf.constant([[5.0, 6.0], [7.0, 8.0]])
    resultado = tf.matmul(a, b).numpy()
    esperado = np.array([[19.0, 22.0], [43.0, 50.0]])
    assert np.allclose(resultado, esperado), f"matmul devolvió {resultado}"
    print("Tensores    : OK (multiplicación de matrices correcta)")


def probar_entrenamiento():
    tf.keras.utils.set_random_seed(0)
    x = np.array([-1.0, 0.0, 1.0, 2.0, 3.0, 4.0]).reshape(-1, 1)
    y = 2 * x - 1

    modelo = tf.keras.Sequential([tf.keras.Input(shape=(1,)), tf.keras.layers.Dense(1)])
    modelo.compile(optimizer=tf.keras.optimizers.SGD(0.05), loss="mse")
    historia = modelo.fit(x, y, epochs=200, verbose=0)

    prediccion = float(modelo.predict(np.array([[10.0]]), verbose=0)[0][0])
    perdida = historia.history["loss"][-1]
    assert abs(prediccion - 19.0) < 0.5, f"predicción {prediccion:.3f}, se esperaba ~19"
    print(f"Entrenamiento: OK (pérdida final {perdida:.5f}, f(10) = {prediccion:.3f}, esperado 19)")


if __name__ == "__main__":
    print("=== Prueba de TensorFlow ===")
    probar_version()
    probar_dispositivos()
    probar_tensores()
    probar_entrenamiento()
    print("=== Todo correcto ===")
