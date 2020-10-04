"""Cats VS Dogs 97%.ipynb

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from warnings import filterwarnings
filterwarnings('ignore')

# Load the data: the Cats vs Dogs dataset

!curl -O https://download.microsoft.com/download/3/E/1/3E1C3F21-ECDB-4869-8368-6DEBA77B919F/kagglecatsanddogs_3367a.zip

!unzip -q kagglecatsanddogs_3367a.zip
!ls

!ls PetImages

# Filter out corrupted images

import os

num_skipped = 0
for folder_name in ("Cat", "Dog"):
    folder_path = os.path.join("PetImages", folder_name)
    for fname in os.listdir(folder_path):
        fpath = os.path.join(folder_path, fname)
        try:
            fobj = open(fpath, "rb")
            is_jfif = tf.compat.as_bytes("JFIF") in fobj.peek(10)
        finally:
            fobj.close()

        if not is_jfif:
            num_skipped += 1
            # Delete corrupted image
            os.remove(fpath)

print("Deleted %d images" % num_skipped)

# Generate a `Dataset`

image_size = (180, 180)
batch_size = 32

train_ds = tf.keras.preprocessing.image_dataset_from_directory(
    "PetImages",
    validation_split=0.2,
    subset="training",
    seed=1337,
    image_size=image_size,
    batch_size=batch_size,
)
val_ds = tf.keras.preprocessing.image_dataset_from_directory(
    "PetImages",
    validation_split=0.2,
    subset="validation",
    seed=1337,
    image_size=image_size,
    batch_size=batch_size,
)

# Visualize the data

import matplotlib.pyplot as plt

def vis(ds):
  plt.figure(figsize=(10, 10))
  for images, labels in ds.take(100):
    for i in range(9):
      ax = plt.subplot(3, 3, i + 1)
      plt.imshow(images[i].numpy().astype("uint8"))
      plt.title(int(labels[i]))
      plt.axis("off")

vis(train_ds)

# Using image data augmentation

data_augmentation = keras.Sequential(
    [
        layers.experimental.preprocessing.RandomFlip("horizontal"),
        layers.experimental.preprocessing.RandomRotation(0.1),
    ]
)

plt.figure(figsize=(10, 10))
for images, _ in train_ds.take(1):
    for i in range(9):
        augmented_images = data_augmentation(images)
        ax = plt.subplot(3, 3, i + 1)
        plt.imshow(augmented_images[0].numpy().astype("uint8"))
        plt.axis("off")

# Standardizing the data

train_ds = train_ds.prefetch(buffer_size=32)
val_ds = val_ds.prefetch(buffer_size=32)

# Build a model

def MyModel(input_shape, num_classes):
    inputs = keras.Input(shape=input_shape)
    # Image augmentation block
    x = data_augmentation(inputs)

    # Entry block
    x = layers.experimental.preprocessing.Rescaling(1.0 / 255)(x)
    x = layers.Conv2D(32, 3, strides=2, padding="same")(x)
    x = layers.BatchNormalization()(x)
    x = tf.nn.relu6(x)

    x = layers.Conv2D(64, 3, padding="same")(x)
    x = layers.BatchNormalization()(x)
    x = tf.nn.relu6(x)

    previous_block_activation = x  # Set aside residual

    for size in [128, 256, 512, 728]:
        x = tf.nn.relu6(x)
        x = layers.SeparableConv2D(size, 3, padding="same")(x)
        x = layers.BatchNormalization()(x)

        x = tf.nn.relu6(x)
        x = layers.SeparableConv2D(size, 3, padding="same")(x)
        x = layers.BatchNormalization()(x)

        x = layers.MaxPooling2D(3, strides=2, padding="same")(x)

        # Project residual
        residual = layers.Conv2D(size, 1, strides=2, padding="same")(
            previous_block_activation
        )
        x = layers.add([x, residual])  # Add back residual
        previous_block_activation = x  # Set aside next residual

    x = layers.SeparableConv2D(1024, 3, padding="same")(x)
    x = layers.BatchNormalization()(x)
    x = tf.nn.relu6(x)

    x = layers.GlobalAveragePooling2D()(x)
    if num_classes == 2:
        activation = "sigmoid"
        units = 1
    else:
        activation = "softmax"
        units = num_classes

    x = layers.Dropout(0.5)(x)
    outputs = layers.Dense(units, activation=activation)(x)
    return keras.Model(inputs, outputs)


model = MyModel(input_shape=image_size + (3,), num_classes=2)
# keras.utils.plot_model(model, show_shapes=True)

model.summary()

# Train the model

epochs = 50

callbacks = [
    keras.callbacks.ModelCheckpoint("checkpoint_model.h5", save_best_only=True),
    keras.callbacks.EarlyStopping(patience=7, restore_best_weights=True, verbose=1),
    keras.callbacks.ReduceLROnPlateau(verbose=1, min_lr=0.000001, patience=5)
]
model.compile(
    optimizer=keras.optimizers.Adam(1e-3),
    loss="binary_crossentropy",
    metrics=["binary_accuracy"],
)
model.fit(
    train_ds, epochs=epochs, callbacks=callbacks, validation_data=val_ds, 
)

# We get to ~97% validation accuracy after training for 30 epochs on the full dataset.

loss, acc = model.evaluate(train_ds, verbose=0)
print("Training Loss: {:.3} \t Training Accuracy: {:.3}".format(loss, acc))
loss, acc = model.evaluate(val_ds, verbose=0)
print("Training Loss: {:.3} \t Training Accuracy: {:.3}".format(loss, acc))

clf = tf.keras.models.load_model('checkpoint_model.h5')
loss, acc = clf.evaluate(train_ds, verbose=0)
print('Training Loss: {:.2} \t Training Accuracy {:.3}'.format(loss, acc))
loss, acc = clf.evaluate(val_ds, verbose=0)
print('Testing Loss: {:.2} \t Testing Accuracy {:.3}'.format(loss, acc))

json_model = model.to_json()
with open('model.json', 'w') as json_file:
  json_file.write(json_model)


yaml_model = model.to_yaml()
with open('model.yaml', 'w') as yaml_file:
  yaml_file.write(yaml_model)

model.save('model.h5')
model.save_weights('model_weights.h5')
print('Done')

# Run inference on new data

img = keras.preprocessing.image.load_img(
    "PetImages/Cat/6779.jpg", target_size=image_size
)
img_array = keras.preprocessing.image.img_to_array(img)
img_array = tf.expand_dims(img_array, 0)  # Create batch axis

predictions = model.predict(img_array)
score = predictions[0]
print(
    "This image is %.2f percent cat and %.2f percent dog."
#     % (100 * (1 - score), 100 * score)
)

