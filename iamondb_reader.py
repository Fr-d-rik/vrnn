from __future__ import print_function
import os
import fnmatch
import xml.etree.ElementTree as ET
import numpy as np
import matplotlib.pyplot as plt


def xml_to_mat(xml_path, interpolate=False, max_dist=300):
    """ read data from an xml file, turn into numpy array of relative steps, cut to max step size """
    if interpolate:
        raise NotImplementedError

    root = ET.parse(xml_path).getroot()

    stroke_set = root.find('StrokeSet')
    stroke_mat_list = []
    for stroke in stroke_set:
        point_list = []
        for point in stroke:
            coords = (point.attrib['x'], point.attrib['y'], 0)
            point_list.append(coords)
        stroke_mat = np.asarray(point_list, dtype=int)
        stroke_mat[-1, 2] = 1  # mark end of character

        stroke_mat_list.append(stroke_mat)

    mat = np.concatenate(stroke_mat_list, axis=0)

    mat[1:, :2] = mat[1:, :2] - mat[:-1, :2]
    mat[0, :2] = 0

    mat = np.maximum(mat, -max_dist)
    mat = np.minimum(mat, max_dist)
    return mat


def mat_to_plot(mat, meanx=0., meany=0., stdx=1., stdy=1.):
    """ takes preprocessed sequence, renormalizes and re-computes absolute from relative positions. plots result """
    # add third row if missing
    if mat.shape[1] == 2:
        mat = np.concatenate([mat, np.zeros((mat.shape[0], 1))], axis=1)
    else:
        mat[:, 2] = np.ceil(mat[:, 2] - 0.5)
    mat[-1, -1] = 1.0

    # renorm
    mat[:, 0] = mat[:, 0] * stdx + meanx
    mat[:, 1] = mat[:, 1] * stdy + meany

    for idx in range(2, mat.shape[0]):
        mat[idx, :2] = mat[idx, :2] + mat[idx - 1, :2]

    mat[:, 1] = - mat[:, 1]  # flip y axis for accurate plot

    stroke_ends = np.argwhere(mat[:, 2])  # single out individual strokes
    begin = 0
    for end in stroke_ends:
        end = int(end)
        plt.axis('equal')
        plt.plot(mat[begin:end, 0], mat[begin:end, 1], c='blue')
        begin = end + 1
    plt.show()


def parse_data_set(target_dir, root_dir='data/handwriting/xml_data_root/lineStrokes/',
                   testset_spec='data/handwriting/testsetspecs.txt'):
    """ load train an test xml files, accumulate into data mats, storing sequence lengths separately """
    if testset_spec is not None:
        with open(testset_spec) as f:
            test_dirs = [k.rstrip() for k in f.readlines()]
    else:
        test_dirs = []

    train_matches = []
    test_matches = []
    for root, _, file_names in os.walk(root_dir):
        if root.split('/')[-1] in test_dirs:
            for filename in fnmatch.filter(file_names, '*.xml'):
                test_matches.append(os.path.join(root, filename))
        else:
            for filename in fnmatch.filter(file_names, '*.xml'):
                train_matches.append(os.path.join(root, filename))
    print(len(train_matches))
    print(train_matches[0])

    print(len(test_matches))
    print(test_matches[0])

    train_mat_list = []
    for f in train_matches:
        mat = xml_to_mat(f)
        train_mat_list.append(mat)
        if len(train_mat_list) % 500 == 0:
            print('loaded ' + str(len(train_mat_list)) + '/' + str(len(train_matches)) + ' train files')

    len_list = [k.shape[0] for k in train_mat_list]
    train_sequence_indices = np.asarray(len_list)
    train_sequences = np.concatenate(train_mat_list, axis=0)
    np.save(target_dir + '/train_sequence_indices.npy', train_sequence_indices)
    np.save(target_dir + '/train_sequences.npy', train_sequences)

    plt.hist(len_list, 50, normed=1, facecolor='green', alpha=0.75)
    plt.show()

    test_mat_list = []
    for f in test_matches:
        mat = xml_to_mat(f)
        test_mat_list.append(mat)
        if len(test_mat_list) % 100 == 0:
            print('loaded ' + str(len(test_mat_list)) + '/' + str(len(test_matches)) + ' test files')

    len_list = [k.shape[0] for k in test_mat_list]
    train_sequence_indices = np.asarray(len_list)
    train_sequences = np.concatenate(test_mat_list, axis=0)
    np.save(target_dir + '/test_sequence_indices.npy', train_sequence_indices)
    np.save(target_dir + '/test_sequences.npy', train_sequences)

    plt.hist(len_list, 50, normed=1, facecolor='green', alpha=0.75)
    plt.show()


def load_sequences(source_dir, seq_file='sequences.npy', idx_file='sequence_indices.npy'):
    """ load data mat and length max, add lengths up to get indices """
    seq_mat = np.load(source_dir + '/' + seq_file)
    idx_mat = np.load(source_dir + '/' + idx_file)
    # plt.hist(idx_mat, 50, normed=1, facecolor='green', alpha=0.75)
    # plt.show()
    for idx in range(1, idx_mat.shape[0]):
        idx_mat[idx] = idx_mat[idx] + idx_mat[idx - 1]

    return seq_mat, idx_mat


def load_and_cut_sequences(source_dir, seq_file='sequences.npy', idx_file='sequence_indices.npy', cut_len=500,
                           normalize=True, mask=True, mask_value=500):
    """ loads sequences, cuts to certain lenght. optionally normalizing and masking them """
    if not mask:
        mask_value = 0

    seq_mat, idx_mat = load_sequences(source_dir, seq_file, idx_file)

    split_list = np.split(seq_mat.astype(float), idx_mat[1:], axis=0)

    # cut sequences to maximum length
    cut_list = []
    for mat in split_list:
        if mat.shape[0] > cut_len:
            cut_list.append(mat[:cut_len, :])
        else:
            cut_list.append(mat)

    cut_seq_mat = np.concatenate(cut_list, axis=0)

    # compute adequate mean and std-dev
    if normalize:
        if mask:
            cut_mat = cut_seq_mat.astype(float)
        else:  # append as many zeros, as will be padded to cut_seq_mat
            zero_shape = (len(cut_list) * cut_len - cut_seq_mat.shape[0], cut_seq_mat.shape[1])
            cut_mat = np.concatenate([cut_seq_mat.astype(float), np.zeros(zero_shape, dtype=float)], axis=0)

        mean = np.mean(cut_mat, axis=0)
        std = np.std(cut_mat, axis=0)
        # for idx in [0, 1]:
        #     mat[:, idx] = (mat[:, idx] - mean[idx]) / std[idx]

    else:
        mean = [0., 0., 0.]
        std = [1., 1., 1.]

    # normalize and pad sequences
    for idx, mat in enumerate(cut_list):
        if normalize:
            mat[:, 0] = (mat[:, 0] - mean[0]) / std[0]
            mat[:, 1] = (mat[:, 1] - mean[1]) / std[1]

        if mat.shape[0] < cut_len:
            padded = np.zeros((cut_len, 3), dtype=float) + mask_value
            padded[:mat.shape[0], :] = mat
            mat = padded

        cut_list[idx] = mat

    data_mat = np.asarray(cut_list)
    data_mat = np.swapaxes(data_mat, 0, 1)
    return data_mat, mean, std


def no_values_check(val):
    """ sanity check to make sure for no entry in the data x = y = val (so val is a valid masking constant)"""
    seq, idx = load_sequences('data/handwriting')
    seq = seq[:, :2]
    seq = (seq == val)
    seq = np.sum(seq, 1)
    print(np.sum(seq))
    print(np.sum(seq == 2*val))


def get_list_of_seqs(source_dir, seq_file='sequences.npy', idx_file='sequence_indices.npy', normalize=True):
    """ load sequences as list (now unused) """
    seq_mat, idx_mat = load_sequences(source_dir, seq_file, idx_file)
    seq_mat = seq_mat.astype(float)
    if normalize:
        mean = np.mean(seq_mat, axis=0)
        std = np.std(seq_mat, axis=0)
        seq_mat[:, 0] = (seq_mat[:, 0] - mean[0]) / std[0]
        seq_mat[:, 1] = (seq_mat[:, 1] - mean[1]) / std[1]
    split_list = np.split(seq_mat, idx_mat[1:], axis=0)
    return split_list

# no_values_check(500)

# mat_to_plot(a)
# parse_data_set('data/handwriting')
# print(load_and_cut_sequences('data/handwriting').shape)
# mat, m, s = load_and_cut_sequences('data/handwriting', seq_file='test_sequences.npy',
#                                    idx_file='test_sequence_indices.npy',
#                                    cut_len=500, mask=True, normalize=True)
# np.save('data/handwriting/test_cut_500_pad_500_max_300_norm.npy', mat)
# print(m)
# print(s)
# mat_to_plot(mat[:, 1, :], m[0], m[1], s[0], s[1])

# a = np.load('data/handwriting/rough_cut_500_pad_500_max_300_norm.npy')
# print(np.min(a))
# m = [7.61830955,  0.54058467,  0.03867651]  # [0., 0.]  #
# s = [33.74283029,  36.72359088,   0.19282281]  # [1., 1.]  #


# mask 200 cut
# [ 7.65791469  0.54339499  0.03887757]
# [ 33.82594281  36.81890347   0.19330315]

# no mask 200 cut
# [ 7.61830955  0.54058467  0.03867651]
# [ 33.74283029  36.72359088   0.19282281]

# no mask 500 cut
# [ 7.53910619  0.27981927  0.03798622]
# [ 33.89499853  35.08117997   0.19116294]

# mask 500 cut
# [ 7.97040614,  0.29582727,  0.04015935]
# [ 34.80169994,  36.07062753,   0.19633283]

# mask 500 cut train
# [ 7.94481711,  0.29089536,  0.04015935]
# [ 34.73663681,  35.96986879,   0.19633283]

# mask 500 cut test
# [ 9.00034885  0.49240353  0.04721629]
# [ 37.33186456  39.92153479   0.21210118]