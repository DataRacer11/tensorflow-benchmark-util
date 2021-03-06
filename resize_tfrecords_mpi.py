#!/usr/bin/env python3
#
# Copyright (c) 2018 Dell Inc., or its subsidiaries. All Rights Reserved.
#
# Written by Claudio Fahey <claudio.fahey@dell.com>
#


"""
This script reads images from TFRecord files, resizes all images, and writes them to new TFRecord files.
"""

import os
import argparse
from os.path import join, basename, splitext
import tensorflow as tf
import six
from glob import glob


def _bytes_feature(value):
  """Wrapper for inserting bytes features into Example proto."""
  if six.PY3 and isinstance(value, six.text_type):
    value = six.binary_type(value, encoding='utf-8')
  return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))

def _int64_feature(value):
  """Wrapper for inserting int64 features into Example proto."""
  if not isinstance(value, list):
    value = [value]
  return tf.train.Feature(int64_list=tf.train.Int64List(value=value))


def _float_feature(value):
  """Wrapper for inserting float features into Example proto."""
  if not isinstance(value, list):
    value = [value]
  return tf.train.Feature(float_list=tf.train.FloatList(value=value))


def _convert_to_example(filename, image_buffer, label, synset, human, xmin, ymin, xmax, ymax,
                        height, width):
  """Build an Example proto for an example.

  Args:
    filename: string, path to an image file, e.g., '/path/to/example.JPG'
    image_buffer: string, JPEG encoding of RGB image
    label: integer, identifier for the ground truth for the network
    synset: string, unique WordNet ID specifying the label, e.g., 'n02323233'
    human: string, human-readable label, e.g., 'red fox, Vulpes vulpes'
    xmin, ymin, xmax, ymax: list of bounding boxes
    height: integer, image height in pixels
    width: integer, image width in pixels
  Returns:
    Example proto
  """
  colorspace = 'RGB'
  channels = 3
  image_format = 'JPEG'
  # image_format = 'PNG'

  example = tf.train.Example(features=tf.train.Features(feature={
      'image/height': _int64_feature(height),
      'image/width': _int64_feature(width),
      'image/colorspace': _bytes_feature(colorspace),
      'image/channels': _int64_feature(channels),
      'image/class/label': _int64_feature(label),
      'image/class/synset': _bytes_feature(synset),
      'image/class/text': _bytes_feature(human),
      'image/object/bbox/xmin': _float_feature(xmin),
      'image/object/bbox/xmax': _float_feature(xmax),
      'image/object/bbox/ymin': _float_feature(ymin),
      'image/object/bbox/ymax': _float_feature(ymax),
      'image/object/bbox/label': _int64_feature([label] * len(xmin)),
      'image/format': _bytes_feature(image_format),
      'image/filename': _bytes_feature(os.path.basename(filename)),
      'image/encoded': _bytes_feature(image_buffer)}))
  return example


def process_tf_record_file(input_tf_record_filename, output_tf_record_filename):
    """Read single TFRecord file, resize images, and write a new TFRecord file.

    Note that bounding box values are floats between 0 and 1 and do not need to be scaled.
    """
    tf_record_iterator = tf.python_io.tf_record_iterator(path=input_tf_record_filename)
    original_len_total = 0
    resized_len_total = 0
    image_count = 0
    with tf.python_io.TFRecordWriter(output_tf_record_filename) as writer:
        for record_string in tf_record_iterator:
            image_count += 1

            # Parse input record.
            example = tf.train.Example()
            example.ParseFromString(record_string)
            filename = example.features.feature['image/filename'].bytes_list.value[0]
            label = int(example.features.feature['image/class/label'].int64_list.value[0])
            synset = example.features.feature['image/class/synset'].bytes_list.value[0]
            human = example.features.feature['image/class/text'].bytes_list.value[0]
            xmin = list(example.features.feature['image/object/bbox/xmin'].float_list.value)
            ymin = list(example.features.feature['image/object/bbox/ymin'].float_list.value)
            xmax = list(example.features.feature['image/object/bbox/xmax'].float_list.value)
            ymax = list(example.features.feature['image/object/bbox/ymax'].float_list.value)
            original_height = int(example.features.feature['image/height'].int64_list.value[0])
            original_width = int(example.features.feature['image/width'].int64_list.value[0])
            original_encoded = example.features.feature['image/encoded'].bytes_list.value[0]
            original_len = len(original_encoded)
            original_len_total += original_len

            # with open("/imagenet-scratch/in.jpg", "wb") as output_jpeg_file:
            #     output_jpeg_file.write(encoded)

            # Decode JPEG.
            image = tf.image.decode_jpeg(original_encoded, channels=3)

            # Resize image.
            resize_factor = 3.0
            new_height = int(original_height * resize_factor)
            new_width = int(original_width * resize_factor)
            resized_image = tf.image.resize_images(image, [new_height, new_width], align_corners=True)

            # Encode JPEG.
            resized_encoded = tf.image.encode_jpeg(
                tf.cast(resized_image, tf.uint8),
                quality=100,
                chroma_downsampling=False,
            )
            resized_encoded = resized_encoded.eval()
            resized_len = len(resized_encoded)
            resized_len_total += resized_len

            print('%(input_tf_record_filename)s: %(filename)s %(original_KB)0.0f KB => %(resized_KB)0.0f KB' % dict(
                input_tf_record_filename=input_tf_record_filename,
                xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax,
                filename=filename.decode(), original_height=original_height, original_width=original_width,
                original_KB=original_len/1000.0, resized_KB=resized_len/1000.0))

            # with open("/imagenet-scratch/out.jpg", "wb") as output_jpeg_file:
            #     output_jpeg_file.write(resized_encoded)

            # Write to TFRecord.
            example = _convert_to_example(
                filename, resized_encoded, label,
                synset, human, xmin, ymin, xmax, ymax,
                new_height, new_width)
            writer.write(example.SerializeToString())

            # if image_count >= 10:
            #     break

    original_len_mean = original_len_total / image_count
    resized_len_mean = resized_len_total / image_count
    print('%(input_tf_record_filename)s: %(image_count)d images, mean size %(original_KB_mean)0.0f KB => %(resized_KB_mean)0.0f KB' % dict(
        input_tf_record_filename=input_tf_record_filename,
        image_count=image_count,
        original_KB_mean=original_len_mean/1000,
        resized_KB_mean=resized_len_mean / 1000))


def worker(rank, size, input_files, output_dir):
    with tf.Session() as sess:
        input_tf_record_filenames = sorted(glob(input_files))
        num_files = len(input_tf_record_filenames)
        i = rank
        while (i < num_files):
            input_tf_record_filename = input_tf_record_filenames[i]
            output_tf_record_filename = join(output_dir, basename(input_tf_record_filename))
            print(rank, input_tf_record_filename, output_tf_record_filename)
            process_tf_record_file(input_tf_record_filename, output_tf_record_filename)
            i += size


def main():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-i', '--input_files', help='Input files', required=True)
    parser.add_argument('-o', '--output_dir', help='Output directory', required=True)
    args = parser.parse_args()
    rank = int(os.environ['OMPI_COMM_WORLD_RANK'])
    size = int(os.environ['OMPI_COMM_WORLD_SIZE'])
    worker(rank, size, args.input_files, args.output_dir)


if __name__ == '__main__':
    main()
