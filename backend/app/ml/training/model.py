"""
GRU forecaster — model definition.

Keeps the architecture in a single ``build_model`` function so it can be
swapped out without touching the training loop.
"""

import logging

log = logging.getLogger("training.model")


def build_model(input_shape: tuple, n_classes: int = 3):
    """Build and compile a simple GRU classifier.

    Architecture::

        Input(shape=(window_size, n_features))
        GRU(64, return_sequences=False)
        Dropout(0.2)
        Dense(32, activation="relu")
        Dense(n_classes, activation="softmax")

    Parameters
    ----------
    input_shape : tuple
        ``(window_size, n_features)`` — e.g. ``(30, 20)``.
    n_classes : int
        Number of output classes (default 3).

    Returns
    -------
    Compiled ``tf.keras.Model``.
    """
    import tensorflow as tf

    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=input_shape),
        tf.keras.layers.GRU(64, return_sequences=False),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(n_classes, activation="softmax"),
    ])

    model.compile(
        optimizer="adam",
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    log.info("Model built — input_shape=%s, params=%d", input_shape, model.count_params())
    model.summary(print_fn=log.info)
    return model
