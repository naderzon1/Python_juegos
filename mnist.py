"""MNIST: reconocimiento de dígitos escritos a mano con TensorFlow.

Entrena una red convolucional pequeña sobre las 60.000 imágenes de MNIST,
la evalúa con las 10.000 de prueba y guarda el modelo en mnist_modelo.keras.

La primera vez descarga el conjunto de datos (~11 MB) a ~/.keras/datasets.

Uso:  python mnist.py
"""
import os

# silencia los avisos informativos de TensorFlow al arrancar
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
import tensorflow as tf

EPOCAS = 3
LOTE = 128
ARCHIVO_MODELO = "mnist_modelo.keras"


def cargar_datos():
    (x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()
    # de enteros 0-255 a decimales 0-1, y se añade el canal (28, 28) -> (28, 28, 1)
    x_train = (x_train / 255.0).astype("float32")[..., np.newaxis]
    x_test = (x_test / 255.0).astype("float32")[..., np.newaxis]
    return (x_train, y_train), (x_test, y_test)


def crear_modelo():
    modelo = tf.keras.Sequential([
        tf.keras.Input(shape=(28, 28, 1)),
        tf.keras.layers.Conv2D(32, 3, activation="relu"),
        tf.keras.layers.MaxPooling2D(),
        tf.keras.layers.Conv2D(64, 3, activation="relu"),
        tf.keras.layers.MaxPooling2D(),
        tf.keras.layers.Flatten(),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(10, activation="softmax"),
    ])
    modelo.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    return modelo


def dibujar(imagen):
    """Muestra un dígito en la consola con caracteres."""
    for fila in imagen[..., 0]:
        print("".join(" .:#"[min(3, int(v * 4))] for v in fila))


if __name__ == "__main__":
    tf.keras.utils.set_random_seed(0)

    (x_train, y_train), (x_test, y_test) = cargar_datos()
    print(f"Entrenamiento: {len(x_train)} imágenes   Prueba: {len(x_test)} imágenes")

    modelo = crear_modelo()
    modelo.fit(x_train, y_train, epochs=EPOCAS, batch_size=LOTE, validation_split=0.1, verbose=2)

    perdida, exactitud = modelo.evaluate(x_test, y_test, verbose=0)
    print(f"\nExactitud en prueba: {exactitud:.2%}   (pérdida {perdida:.4f})")

    predicciones = modelo.predict(x_test, verbose=0).argmax(axis=1)
    fallos = np.flatnonzero(predicciones != y_test)
    print(f"Aciertos: {len(y_test) - len(fallos)} de {len(y_test)}   Fallos: {len(fallos)}")

    print("\nEjemplo de la primera imagen de prueba:")
    dibujar(x_test[0])
    print(f"Predicción: {predicciones[0]}   Real: {y_test[0]}")

    modelo.save(ARCHIVO_MODELO)
    print(f"\nModelo guardado en {ARCHIVO_MODELO}")
