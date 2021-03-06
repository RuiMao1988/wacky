'''
Data functions for Wacky parsed, ukWaC datasets. 
Since these are so large, Wacky splits these up. We keep a global pointer
to our dataset and move through the set, loading a new file when we need to.

'''

import os, collections, random

import numpy as np

_data_barriers = []
_current_data_block = []
_integer_files = []
_total_size = 0
_data_index = 0
_data_offset = 0
_current_block = 0

# Move to the next data block and set offsets
# My suspicion is that for some reason, noise contrastive explodes
# if this loops around so we need to signal when we've set at all the data I think
def new_data_block():
  global _current_block
  global _current_data_block
  global _integer_files
  global _data_barriers
  global _data_offset
  global _data_index
  
  # I wonder, should we add a del somewher to keep mem usage down? Virtual mem is 
  # really high

  _current_block = _current_block + 1
  
  print("Loading new block", _current_block, len(_integer_files), _data_index, _data_offset)
  if _current_block >= len(_integer_files):
    _current_block = 0
    _data_offset = 0
    return False
  else:
    _data_offset = _data_barriers[_current_block]
    read_integer_file(_integer_files[_current_block])
  return True

# Called by Tensorflow to grab some more data
def generate_batch( batch_size, num_skips, skip_window):

  global _data_index
  global _total_size
  global _current_data_block
  global _data_offset

  assert batch_size % num_skips == 0
  assert num_skips <= 2 * skip_window
  batch = np.ndarray(shape=(batch_size), dtype=np.int32)
  labels = np.ndarray(shape=(batch_size, 1), dtype=np.int32)
  span = 2 * skip_window + 1 # [ skip_window target skip_window ]
  bbuffer = collections.deque(maxlen=span)
  
  valid_batch = True # or looping over data again

  for _ in range(span):
    offset = _data_index-_data_offset
    if offset >= len(_current_data_block) or offset < 0:
      # Quit if we reached the end of the datablock
      if not new_data_block():
        valid_batch = False
      offset = _data_index-_data_offset

    bbuffer.append(_current_data_block[offset])
    _data_index = (_data_index + 1) % _total_size

  for i in range(batch_size // num_skips):
    target = skip_window  # target label at the center of the buffer
    targets_to_avoid = [ skip_window ]
  
    for j in range(num_skips):
      while target in targets_to_avoid:
        target = random.randint(0, span - 1)
      targets_to_avoid.append(target)
      batch[i * num_skips + j] = bbuffer[skip_window]
      labels[i * num_skips + j, 0] = bbuffer[target]
  
    offset = _data_index -_data_offset
    if offset >= len(_current_data_block) or offset < 0:
      # Quit if we reached the end of the datablock
      if not new_data_block():
        valid_batch=False
      offset = _data_index-_data_offset

    bbuffer.append(_current_data_block[offset])
    _data_index = (_data_index + 1) % _total_size

  return batch, labels, valid_batch


# Read the dictionary file
def read_dictionary(dict_path):
  
  dictionary = dict()
  
  with open(dict_path, 'r') as f:
    size_dict = 0

    for line in f.readlines():
      line = line.replace("\n","")
      dictionary[line] = size_dict
      size_dict += 1

  reverse_dictionary = dict(zip(dictionary.values(), dictionary.keys()))

  return dictionary, reverse_dictionary, size_dict

# Find Integer data files and their associated file sizes
def find_integer_files(intpath):

  data_files = []
  size_files = []

  for dirname, dirnames, filenames in os.walk(intpath):
    for filename in filenames:
      if "integers_" in filename:
        data_files.append(os.path.join(dirname, filename))
      elif "size_" in filename:
        size_files.append(os.path.join(dirname, filename))

  data_files.sort()
  size_files.sort()

  return data_files, size_files

def read_integer_file(filepath):
  global _current_data_block
  print("Reading integer file",filepath)
  _current_data_block = []
  with open(filepath, 'r') as f:
    for line in f.readlines():
      _current_data_block.append(int(line))


# Set the integer data files, reading the first into the buffer
def set_integer_files(integer_files, size_files):

  global _data_barriers
  global _integer_files

  _integer_files = integer_files

  # Set the barriers from the sizes
  offset = 0
  _data_barriers.append(0)
  for size_file in size_files:
    with open(size_file, 'r') as f:
      for line in f.readlines():
        offset += int(line)
        _data_barriers.append(offset)

  read_integer_file(integer_files[0])

# Read in the frequency file
# We return a dictionary of the various frequences and an ordering 
# from most to least
def read_freq(freq_file, dict_size):
  count = {}
  order = []

  with open(freq_file,'r') as f:
    for line in f.readlines():      
      tokens = line.split(", ")

      if len(tokens) == 2:
        key = tokens[0].replace(" ","")
        freq  = int(tokens[1])
        count[key] = freq

  count['UNK'] =-1

  count_order = [pair[0] for pair in sorted(count.items(), key=lambda item: item[1])]
  count_order = count_order[::-1]

  return count, count_order

# Read the number of unknowns we have
def read_unk_count(unk_file):
  l = 0
  with open(unk_file, 'r') as f:
    l = int(f.readlines()[0])
  return l

# Read the total data count file
def read_total_size(total_file):
  global _total_size
  _total_size = 0
  with open(total_file,'r') as f:
    _total_size = int(f.readlines()[0])

  return _total_size

# Return a random sentence from the current block
def random_sentence():
  global _current_data_block
  
  target = random.randint(0, len(_current_data_block) - 100)
  
  return _current_data_block[target:target+20]




