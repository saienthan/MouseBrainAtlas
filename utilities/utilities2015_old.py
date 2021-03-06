from skimage.filters import threshold_otsu, threshold_adaptive, gaussian_filter
from skimage.color import color_dict, gray2rgb, label2rgb, rgb2gray
from skimage.segmentation import clear_border
from skimage.morphology import binary_dilation, binary_erosion, watershed, remove_small_objects
from skimage.measure import regionprops, label
from skimage.restoration import denoise_bilateral
from skimage.util import img_as_ubyte, img_as_float
from skimage.io import imread, imsave
from skimage.transform import rescale
from scipy.spatial.distance import cdist, pdist
import numpy as np
import os
import csv
import sys
from operator import itemgetter
import json
import cPickle as pickle
import datetime

import cv2

from tables import open_file, Filters, Atom
import bloscpack as bp

from subprocess import check_output, call

import matplotlib.pyplot as plt

from ipywidgets import FloatProgress
from IPython.display import display

########### Data Directories #############

import subprocess
hostname = subprocess.check_output("hostname", shell=True).strip()

if hostname.endswith('sdsc.edu'):
    print 'Setting environment for Gordon'
    atlasAlignParams_rootdir = '/oasis/projects/nsf/csd395/yuncong/CSHL_atlasAlignParams_atlas'
    volume_dir = '/oasis/projects/nsf/csd395/yuncong/CSHL_volumes/'
    labelingViz_root = '/oasis/projects/nsf/csd395/yuncong/CSHL_annotationsViz'
    scoremaps_rootdir = '/oasis/projects/nsf/csd395/yuncong/CSHL_scoremaps_lossless_svm_Sat16ClassFinetuned_v3/'
    scoremapViz_rootdir = '/oasis/projects/nsf/csd395/yuncong/CSHL_scoremapViz_svm_Sat16ClassFinetuned_v3'
else:
    print 'Setting environment for Brainstem workstation or Local'
    volume_dir = '/home/yuncong/CSHL_volumes/'
    mesh_rootdir = '/home/yuncong/CSHL_meshes'

############ Class Labels #############

volume_landmark_names_unsided = ['12N', '5N', '6N', '7N', '7n', 'AP', 'Amb', 'LC',
                                 'LRt', 'Pn', 'R', 'RtTg', 'Tz', 'VLL', 'sp5']
linear_landmark_names_unsided = ['outerContour']

labels_unsided = volume_landmark_names_unsided + linear_landmark_names_unsided
labels_unsided_indices = dict((j, i+1) for i, j in enumerate(labels_unsided))  # BackG always 0

labelMap_unsidedToSided = {'12N': ['12N'],
                            '5N': ['5N_L', '5N_R'],
                            '6N': ['6N_L', '6N_R'],
                            '7N': ['7N_L', '7N_R'],
                            '7n': ['7n_L', '7n_R'],
                            'AP': ['AP'],
                            'Amb': ['Amb_L', 'Amb_R'],
                            'LC': ['LC_L', 'LC_R'],
                            'LRt': ['LRt_L', 'LRt_R'],
                            'Pn': ['Pn_L', 'Pn_R'],
                            'R': ['R_L', 'R_R'],
                            'RtTg': ['RtTg'],
                            'Tz': ['Tz_L', 'Tz_R'],
                            'VLL': ['VLL_L', 'VLL_R'],
                            'sp5': ['sp5'],
                           'outerContour': ['outerContour']}

labelMap_sidedToUnsided = {n: nu for nu, ns in labelMap_unsidedToSided.iteritems() for n in ns}

from itertools import chain
labels_sided = list(chain(*(labelMap_unsidedToSided[name_u] for name_u in labels_unsided)))
labels_sided_indices = dict((j, i+1) for i, j in enumerate(labels_sided)) # BackG always 0


############ Physical Dimension #############

section_thickness = 20 # in um
xy_pixel_distance_lossless = 0.46
xy_pixel_distance_tb = xy_pixel_distance_lossless * 32 # in um, thumbnail

#######################################


from enum import Enum
    
class PolygonType(Enum):
    CLOSED = 'closed'
    OPEN = 'open'
    TEXTURE = 'textured'
    TEXTURE_WITH_CONTOUR = 'texture with contour'
    DIRECTION = 'directionality'

def create_if_not_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)
    return path

def execute_command(cmd):
    print cmd

    try:
        retcode = call(cmd, shell=True)
        if retcode < 0:
            print >>sys.stderr, "Child was terminated by signal", -retcode
        else:
            print >>sys.stderr, "Child returned", retcode
    except OSError as e:
        print >>sys.stderr, "Execution failed:", e
        raise e

def draw_arrow(image, p, q, color, arrow_magnitude=9, thickness=5, line_type=8, shift=0):
    # adapted from http://mlikihazar.blogspot.com.au/2013/02/draw-arrow-opencv.html

    import cv2

    # draw arrow tail
    cv2.line(image, p, q, color, thickness, line_type, shift)
    # calc angle of the arrow 
    angle = np.arctan2(p[1]-q[1], p[0]-q[0])
    # starting point of first line of arrow head 
    p = (int(q[0] + arrow_magnitude * np.cos(angle + np.pi/4)),
    int(q[1] + arrow_magnitude * np.sin(angle + np.pi/4)))
    # draw first half of arrow head
    cv2.line(image, p, q, color, thickness, line_type, shift)
    # starting point of second line of arrow head 
    p = (int(q[0] + arrow_magnitude * np.cos(angle - np.pi/4)),
    int(q[1] + arrow_magnitude * np.sin(angle - np.pi/4)))
    # draw second half of arrow head
    cv2.line(image, p, q, color, thickness, line_type, shift)


def save_hdf(data, fn, complevel=9):
    filters = Filters(complevel=complevel, complib='blosc')
    with open_file(fn, mode="w") as f:
        _ = f.create_carray('/', 'data', Atom.from_dtype(data.dtype), filters=filters, obj=data)

def load_hdf(fn):
    with open_file(fn, mode="r") as f:
        data = f.get_node('/data').read()
    return data


def unique_rows(a, return_index=True):
    # http://stackoverflow.com/questions/16970982/find-unique-rows-in-numpy-array   
    b = np.ascontiguousarray(a).view(np.dtype((np.void, a.dtype.itemsize * a.shape[1])))
    _, idx = np.unique(b, return_index=True)
    unique_a = a[idx]
    if return_index:
        return unique_a, idx
    else:
        return unique_a
    
def unique_rows2(a):
    ind = np.lexsort(a.T)
    return a[np.concatenate(([True],np.any(a[ind[1:]]!=a[ind[:-1]],axis=1)))]
    

def order_nodes(sps, neighbor_graph, verbose=False):

    from networkx.algorithms import dfs_successors, dfs_postorder_nodes


    subg = neighbor_graph.subgraph(sps)
    d_suc = dfs_successors(subg)
    
    x = [(a,b) for a,b in d_suc.iteritems() if len(b) == 2]
    
    if verbose:
        print 'root, two_leaves', x
    
    if len(x) == 0:
        trav = list(dfs_postorder_nodes(subg))
    else:
        if verbose:
            print 'd_succ'
            for it in d_suc.iteritems():
                print it
        
        root, two_leaves = x[0]

        left_branch = []
        right_branch = []

        c = two_leaves[0]
        left_branch.append(c)
        while c in d_suc:
            c = d_suc[c][0]
            left_branch.append(c)

        c = two_leaves[1]
        right_branch.append(c)
        while c in d_suc:
            c = d_suc[c][0]
            right_branch.append(c)

        trav = left_branch[::-1] + [root] + right_branch
        
        if verbose:
            print 'left_branch', left_branch
            print 'right_branch', right_branch
        
    return trav

def find_score_peaks(scores, min_size = 4, min_distance=10, threshold_rel=.3, threshold_abs=0, peakedness_lim=0,
                    peakedness_radius=1, verbose=False):

    from skimage.feature import peak_local_max

    scores2 = scores.copy()
    scores2[np.isnan(scores)] = np.nanmin(scores)
    scores = scores2
    
    if len(scores) > min_size:
    
        scores_shifted = scores[min_size-1:]
        scores_shifted_positive = scores_shifted - scores_shifted.min()

        peaks_shifted = np.atleast_1d(np.squeeze(peak_local_max(scores_shifted_positive, 
                                    min_distance=min_distance, threshold_abs=threshold_abs-scores_shifted.min(), exclude_border=False)))

        # print peaks_shifted

        if len(peaks_shifted) == 0:
            high_peaks_sorted = np.array([np.argmax(scores)], np.int)
            high_peaks_peakedness = np.inf

        else:
            peaks_shifted = peaks_shifted[scores_shifted[peaks_shifted] >= np.max(scores_shifted) - threshold_rel]
            peaks_shifted = np.unique(np.r_[peaks_shifted, np.argmax(scores_shifted)])

            if verbose:
                print 'raw peaks', np.atleast_1d(np.squeeze(min_size - 1 + peaks_shifted))

            if len(peaks_shifted) > 0:
                peaks = min_size - 1 + peaks_shifted
            else:
                peaks = np.array([np.argmax(scores[min_size-1:]) + min_size-1], np.int)

            peakedness = np.zeros((len(peaks),))
            for i, p in enumerate(peaks):
                nbrs = np.r_[scores[max(min_size-1, p-peakedness_radius):p], scores[p+1:min(len(scores), p+1+peakedness_radius)]]
                assert len(nbrs) > 0
                peakedness[i] = scores[p]-np.mean(nbrs)

            if verbose:
                print 'peakedness', peakedness
                print 'filtered peaks', np.atleast_1d(np.squeeze(peaks))

            high_peaks = peaks[peakedness > peakedness_lim]
            high_peaks = np.unique(np.r_[high_peaks, min_size - 1 + np.argmax(scores_shifted)])

            high_peaks_order = scores[high_peaks].argsort()[::-1]
            high_peaks_sorted = high_peaks[high_peaks_order]

            high_peaks_peakedness = np.zeros((len(high_peaks),))
            for i, p in enumerate(high_peaks):
                nbrs = np.r_[scores[max(min_size-1, p-peakedness_radius):p], scores[p+1:min(len(scores), p+1+peakedness_radius)]]
                assert len(nbrs) > 0
                high_peaks_peakedness[i] = scores[p]-np.mean(nbrs)

    else:
        high_peaks_sorted = np.array([np.argmax(scores)], np.int)
        high_peaks_peakedness = np.inf
    
    return high_peaks_sorted, high_peaks_peakedness    



all_stacks = ['MD589', 'MD594', 'MD593', 'MD585', 'MD592', 'MD590', 'MD591', 'MD589', 'MD595', 'MD598', 'MD602', 'MD603']

section_number_lookup = {'MD589': 445, 'MD594': 432, 'MD593': 448, 'MD585': 440, 'MD592': 454, \
                        'MD590': 419, 'MD591': 452, 'MD589': 445, 'MD595': 441, 'MD598': 430, 'MD602': 420, 'MD603': 432}
section_range_lookup = {'MD589': (93, 368), 'MD594': (93, 364), 'MD593': (69,350), 'MD585': (78, 347), 'MD592':(91,371), \
                        'MD590':(80,336), 'MD591': (98,387), 'MD589':(93,368), 'MD595': (67,330), 'MD598': (95,354), 'MD602':(96,352), 'MD603':(60,347)}

# xmin, ymin, w, h
brainstem_bbox_lookup = {'MD585': (610,113,445,408), 'MD593': (645,128,571,500), 'MD592': (807,308,626,407), 'MD590': (652,156,601,536), 'MD591': (697,194,550,665), \
                        'MD594': (616,144,451,362), 'MD595': (645,170,735,519), 'MD598': (680,107,695,459), 'MD602': (641,76,761,474), 'MD589':(643,145,419,367), 'MD603':(621,189,528,401)}

# xmin, ymin, w, h
detect_bbox_lookup = {'MD585': (16,144,411,225), 'MD593': (31,120,368,240), 'MD592': (43,129,419,241), 'MD590': (45,124,411,236), 'MD591': (38,117,410,272), \
                        'MD594': (29,120,422,242), 'MD595': (60,143,437,236), 'MD598': (48,118,450,231), 'MD602': (56,117,468,219), 'MD589': (0,137,419,230), 'MD603': (0,165,528,236)}

detect_bbox_range_lookup = {'MD585': (132,292), 'MD593': (127,294), 'MD592': (147,319), 'MD590': (135,280), 'MD591': (150,315), \
                        'MD594': (143,305), 'MD595': (115,279), 'MD598': (150,300), 'MD602': (147,302), 'MD589': (150,316), 'MD603': (130,290)}
# midline_section_lookup = {'MD589': 114, 'MD594': 119}

class DataManager(object):

    # def reload_labelings(stack):
    #     # if not hasattr(self, 'result_list'):
    #     from collections import defaultdict

    #     # self.result_list = defaultdict(lambda: defaultdict(list))
    #     DataManager.result_list = defaultdict(list)

    #     if os.path.exists(self.labelings_dir):
    #         for fn in os.listdir(self.labelings_dir):
    #             st, se, us, ts, suf = fn[:-4].split('_')
    #             # self.result_list[us][ts].append(suf)
    #             DataManager.result_list[us].append(ts)

    # @classmethod
    # def load_proposal_review_result(cls, stack, section, username, timestamp, suffix):

    #     if not hasattr(self, 'result_list') or len(self.result_list[username]) == 0:
    #         self.reload_labelings()

    #     if username is not None:
    #         if len(self.result_list[username]) == 0:
    #             sys.stderr.write('username %s does not have any annotations for current section %d \n' % (username, section))
    #             return None

    #     if suffix == 'all':
    #         results = []
    #         for suf in self.result_list[username][timestamp]:
    #             ret = cls.load_review_result_path(stack=stack, section=section, username=username, timestamp=timestamp, suffix=suf)
    #             if ret is None:
    #                 return None
    #             else:
    #                 path, usr, ts = ret
    #                 results.append((username, timestamp, suf, pickle.load(open(path, 'r'))))
    #         return results
    #     else:
    #         ret = cls.load_review_result_path(stack=stack, section=section, username=username, timestamp=timestamp, suffix=suffix)
    #         if ret is None:
    #             return None
    #         else:
    #             path, usr, ts = ret
    #             return (usr, ts, suffix, pickle.load( open(path, 'r')))


    # @staticmethod
    # def load_review_result_path(stack, section, username, timestamp, suffix=''):
        
    #     if not hasattr(self, 'result_list') or len(self.result_list[username]) == 0:
    #         self.reload_labelings()

    #     if username is None: # search labelings of any user
    #         self.result_list_flatten = [(usr, ts) for usr, timestamps in self.result_list.iteritems() for ts in timestamps ] # [(username, timestamp)..]
    #         if len(self.result_list_flatten) == 0:
    #             # sys.stderr.write('username is empty\n')
    #             return None
        
    #     if timestamp == 'latest':
    #         if username is not None:
                
    #             if len(self.result_list[username]) == 0:
    #                 return None

    #             timestamps_sorted = map(itemgetter(1), sorted(map(lambda s: (datetime.datetime.strptime(s, "%m%d%Y%H%M%S"), s), self.result_list[username]), reverse=True))
    #             timestamp = timestamps_sorted[0]
    #         else:
    #             ts_str_usr_sorted = sorted([(datetime.datetime.strptime(ts, "%m%d%Y%H%M%S"), ts, usr) for usr, ts in self.result_list_flatten], reverse=True)
    #             timestamp = ts_str_usr_sorted[0][1]
    #             username = ts_str_usr_sorted[0][2]

    #     return os.path.join(self.labelings_dir, '_'.join([stack, '%04d'%section, username, timestamp]) + '_'+suffix+'.pkl'), username, timestamp

    
    @staticmethod
    def get_image_filepath(stack, section, version, resol=None):

        data_dir = os.environ['DATA_DIR']

        if resol is None:
            resol = 'lossless'
            
        slice_str = '%04d' % section

        if version == 'rgb-jpg':
            image_dir = os.path.join(data_dir, stack+'_'+resol+'_aligned_cropped_downscaled')
            image_name = '_'.join([stack, slice_str, resol, 'aligned_cropped_downscaled'])
            image_path = os.path.join(image_dir, image_name + '.jpg')
        # elif version == 'gray-jpg':
        #     image_dir = os.path.join(self.data_dir, stack+'_'+resol+'_cropped_grayscale_downscaled')
        #     image_name = '_'.join([stack, slice_str, resol, 'warped'])
        #     image_path = os.path.join(image_dir, image_name + '.jpg')
        elif version == 'gray':
            image_dir = os.path.join(data_dir, stack+'_'+resol+'_aligned_cropped_grayscale')
            image_name = '_'.join([stack, slice_str, resol, 'aligned_cropped_grayscale'])
            image_path = os.path.join(image_dir, image_name + '.tif')
        elif version == 'rgb':
            image_dir = os.path.join(data_dir, stack+'_'+resol+'_aligned_cropped')
            image_name = '_'.join([stack, slice_str, resol, 'aligned_cropped'])
            image_path = os.path.join(image_dir, image_name + '.tif')

        elif version == 'stereotactic-rgb-jpg':
            image_dir = os.path.join(data_dir, stack+'_'+resol+'_aligned_cropped_downscaled_stereotactic')
            image_name = '_'.join([stack, slice_str, resol, 'aligned_cropped_downscaled_stereotactic'])
            image_path = os.path.join(image_dir, image_name + '.jpg')
         
        return image_path

    def __init__(self, data_dir=os.environ['DATA_DIR'], 
                 repo_dir=os.environ['REPO_DIR'], 
                 labeling_dir=os.environ['LABELING_DIR'],
                 gabor_params_id=None, 
                 segm_params_id='tSLIC200', 
                 vq_params_id=None,
                 stack=None,
                 resol='lossless',
                 section=None,
                 load_mask=False):

        self.data_dir = data_dir
        self.repo_dir = repo_dir
        self.params_dir = os.path.join(repo_dir, 'params')

        self.root_labelings_dir = labeling_dir

        # self.labelnames_path = os.path.join(labeling_dir, 'labelnames.txt')
    
        # if os.path.isfile(self.labelnames_path):
        #     with open(self.labelnames_path, 'r') as f:
        #         self.labelnames = [n.strip() for n in f.readlines()]
        #         self.labelnames = [n for n in self.labelnames if len(n) > 0]
        # else:
        #     self.labelnames = []

        # self.root_results_dir = result_dir

        self.slice_ind = None
        self.image_name = None

        if gabor_params_id is None:
            self.set_gabor_params('blueNisslWide')
        else:
            self.set_gabor_params(gabor_params_id)

        if segm_params_id is None:
            self.set_segmentation_params('blueNisslRegular')
        else:
            self.set_segmentation_params(segm_params_id)

        if vq_params_id is None:
            self.set_vq_params('blueNissl')
        else:
            self.set_vq_params(vq_params_id)
            
        if stack is not None:
            self.set_stack(stack)

        if resol is not None:
            self.set_resol(resol)

        if self.resol == 'lossless':
            if hasattr(self, 'stack') and self.stack is not None:
                self.image_dir = os.path.join(self.data_dir, self.stack+'_'+self.resol+'_aligned_cropped')
                self.image_rgb_jpg_dir = os.path.join(self.data_dir, self.stack+'_'+self.resol+'_aligned_cropped_downscaled')

        if section is not None:
            self.set_slice(section)
        else:
            try:
                random_image_fn = os.listdir(self.image_dir)[0]
                self.image_width, self.image_height = map(int, check_output("identify -format %%Wx%%H %s" % os.path.join(self.image_dir, random_image_fn), shell=True).split('x'))
            except:
                
                d = os.path.join(self.data_dir, 'MD589_lossless_aligned_cropped_downscaled')
                if os.path.exists(d):
                    random_image_fn = os.listdir(d)[0]
                    self.image_width, self.image_height = map(int, check_output("identify -format %%Wx%%H %s" % os.path.join(d, random_image_fn), shell=True).split('x'))

        if load_mask:
            self.thumbmail_mask = imread(self.data_dir+'/%(stack)s_thumbnail_aligned_cropped_mask/%(stack)s_%(slice_str)s_thumbnail_aligned_cropped_mask.png' % {'stack': self.stack, 'slice_str': self.slice_str})
            self.mask = rescale(self.thumbmail_mask.astype(np.bool), 32).astype(np.bool)
            # self.mask[:500, :] = False
            # self.mask[:, :500] = False
            # self.mask[-500:, :] = False
            # self.mask[:, -500:] = False

            xs_valid = np.any(self.mask, axis=0)
            ys_valid = np.any(self.mask, axis=1)
            self.xmin = np.where(xs_valid)[0][0]
            self.xmax = np.where(xs_valid)[0][-1]
            self.ymin = np.where(ys_valid)[0][0]
            self.ymax = np.where(ys_valid)[0][-1]

            self.h = self.ymax-self.ymin+1
            self.w = self.xmax-self.xmin+1



    def load_thumbnail_mask(self):
        self.thumbmail_mask = imread(self.data_dir+'/%(stack)s_thumbnail_aligned_mask_cropped/%(stack)s_%(slice_str)s_thumbnail_aligned_mask_cropped.png' % {'stack': self.stack, 
            'slice_str': self.slice_str}).astype(np.bool)
        return self.thumbmail_mask

    def add_labelnames(self, labelnames, filename):
        existing_labelnames = {}
        with open(filename, 'r') as f:
            for ln in f.readlines():
                abbr, fullname = ln.split('\t')
                existing_labelnames[abbr] = fullname.strip()

        with open(filename, 'a') as f:
            for abbr, fullname in labelnames.iteritems():
                if abbr not in existing_labelnames:
                    f.write(abbr+'\t'+fullname+'\n')

    def set_stack(self, stack):
        self.stack = stack
        self.get_image_dimension()
#         self.stack_path = os.path.join(self.data_dir, self.stack)
#         self.slice_ind = None
        
    def set_resol(self, resol):
        self.resol = resol
    
    def get_image_dimension(self):

        try:
            if hasattr(self, 'image_path') and os.path.exists(self.image_path):
                self.image_width, self.image_height = map(int, check_output("identify -format %%Wx%%H %s" % self.image_path, shell=True).split('x'))
            else:
                # sys.stderr.write('original TIFF image is not available. Loading downscaled jpg instead...')
                
                # if section is specified, use that section; otherwise use a random section in the brainstem range
                if hasattr(self, 'slice_ind') and self.slice_ind is not None:
                    sec = self.slice_ind
                else:
                    sec = section_range_lookup[self.stack][0]

                self.image_width, self.image_height = map(int, check_output("identify -format %%Wx%%H %s" % self._get_image_filepath(section=sec, version='rgb-jpg'), shell=True).split('x'))

        except Exception as e:
            print e
            sys.stderr.write('Cannot find image\n')

        return self.image_height, self.image_width

    def set_slice(self, slice_ind):
        assert self.stack is not None and self.resol is not None, 'Stack is not specified'
        self.slice_ind = slice_ind
        self.slice_str = '%04d' % slice_ind
        if self.resol == 'lossless':
            self.image_dir = os.path.join(self.data_dir, self.stack+'_'+self.resol+'_aligned_cropped')
            self.image_name = '_'.join([self.stack, self.slice_str, self.resol])
            self.image_path = os.path.join(self.image_dir, self.image_name + '_aligned_cropped.tif')

        try:
            if os.path.exists(self.image_path):
                self.image_width, self.image_height = map(int, check_output("identify -format %%Wx%%H %s" % self.image_path, shell=True).split('x'))
            else:
                # sys.stderr.write('original TIFF image is not available. Loading downscaled jpg instead...')
                self.image_width, self.image_height = map(int, check_output("identify -format %%Wx%%H %s" % self._get_image_filepath(version='rgb-jpg'), shell=True).split('x'))
        except Exception as e:
            print e
            sys.stderr.write('Cannot find image\n')

        # self.labelings_dir = os.path.join(self.image_dir, 'labelings')

        if hasattr(self, 'result_list'):
            del self.result_list

        self.labelings_dir = os.path.join(self.root_labelings_dir, self.stack, self.slice_str)
        # if not os.path.exists(self.labelings_dir):
        #     os.makedirs(self.labelings_dir)
        
#         self.results_dir = os.path.join(self.image_dir, 'pipelineResults')
        
        # self.results_dir = os.path.join(self.root_results_dir, self.stack, self.slice_str)
        # if not os.path.exists(self.results_dir):
        #     os.makedirs(self.results_dir)

    # def set_image(self, stack, slice_ind):
    #     self.set_stack(stack)
    #     self.set_slice(slice_ind)
    #     self._load_image()

    def superpixels_in_polygon(vertices):
        from matplotlib.path import Path
        self.load_multiple_results(['spCentroids'])
        pp = Path(vertices)
        return np.where([pp.contains_point(s) for s in self.sp_centroids[:,::-1]])[0]


    def download_result(self, result):
        filename = self._get_result_filename(result, include_path=False)
        cmd = "rsync -az yuncong@gcn-20-33.sdsc.edu:%(gordon_result_dir)s/%(stack)s/%(section)s/%(filename)s %(local_result_dir)s/%(stack)s/%(section)s/ " % {'gordon_result_dir':os.environ['GORDON_RESULT_DIR'],
                                                                            'local_result_dir':os.environ['LOCAL_RESULT_DIR'],
                                                                            'stack': self.stack,
                                                                            'section': self.slice_str,
                                                                            'filename': filename
                                                                            }
        os.system(cmd)


    def download_results(self, results):
        for result_name in results:
            filename = self._get_result_filename(result_name, include_path=False)
            cmd = "rsync -az yuncong@gcn-20-33.sdsc.edu:%(gordon_result_dir)s/%(stack)s/%(section)s/%(filename)s %(local_result_dir)s/%(stack)s/%(section)s/ " % {'gordon_result_dir':os.environ['GORDON_RESULT_DIR'],
                                                                                'local_result_dir':os.environ['LOCAL_RESULT_DIR'],
                                                                                'stack': self.stack,
                                                                                'section': self.slice_str,
                                                                                'filename': filename
                                                                                }
            # print cmd
            os.system(cmd)

    def load_multiple_results(self, results, download_if_not_exist=False):

        from networkx import from_dict_of_lists

        if download_if_not_exist:
            for r in results:
                if not self.check_pipeline_result(r):
                    self.download_result(r)

        if 'texHist' in results and not hasattr(self, 'texton_hists'):

            self.texton_hists = self.load_pipeline_result('texHist')

        if 'segmentation' in results and not hasattr(self, 'segmentation'):
            self.segmentation = self.load_pipeline_result('segmentation')
            self.n_superpixels = self.segmentation.max() + 1
        
        if 'texMap' in results and not hasattr(self, 'textonmap'):
            # if self.check_pipeline_result('texMap'):
            self.textonmap = self.load_pipeline_result('texMap')
            self.n_texton = self.textonmap.max() + 1
            # else:
                # self.download_result('texMap')
                # missing.append('texMap')

        if 'spCentroids' in results and not hasattr(self, 'sp_centroids'):
            # if self.check_pipeline_result('spCentroids'):
            self.sp_centroids = self.load_pipeline_result('spCentroids')
            # else:
            #     self.download_result('spCentroids')
                # missing.append('spCentroids')

        if 'spCoords' in results and not hasattr(self, 'sp_coords'):
            # if self.check_pipeline_result('spCoords'):
            self.sp_coords = self.load_pipeline_result('spCoords')
            # except:
            #     self.download_result('spCoords')
            #     # missing.append('spCoords')

        if 'spAreas' in results and not hasattr(self, 'sp_areas'):
            # try:
            self.sp_areas = self.load_pipeline_result('spAreas')
            # except:
            #     self.download_result('spAreas')
            #     self.sp_areas = self.load_pipeline_result('spAreas')
            #     # missing.append('spAreas')

        if 'edgeCoords' in results and not hasattr(self, 'edge_coords'):
            # try:
            self.edge_coords = dict(self.load_pipeline_result('edgeCoords'))
            # except:
            #     missing.append('edgeCoords')

        if 'edgeMidpoints' in results and not hasattr(self, 'edge_midpoints'):
            # try:
            self.edge_midpoints = dict(self.load_pipeline_result('edgeMidpoints'))
            # except:
            #     missing.append('edgeMidpoints')

        if 'edgeEndpoints' in results and not hasattr(self, 'edge_endpoints'):
            # try:
            self.edge_endpoints = dict(self.load_pipeline_result('edgeEndpoints'))
            # except:
            #     missing.append('edgeEndpoints')

        if 'neighbors' in results and not  hasattr(self, 'neighbors'):
            # try:
            self.neighbors = self.load_pipeline_result('neighbors')
            self.neighbor_graph = from_dict_of_lists(dict(enumerate(self.neighbors)))
            if not hasattr(self, 'edge_coords'):
                # try:
                self.edge_coords = dict(self.load_pipeline_result('edgeCoords'))
                # except:
                #     missing.append('edgeCoords')

            self.neighbors_long = dict([(s, set([n for n in nbrs if len(self.edge_coords[frozenset([s,n])]) > 10])) 
                       for s, nbrs in enumerate(self.neighbors)])
            self.neighbor_long_graph = from_dict_of_lists(self.neighbors_long)
            # except:
            #     missing.append('neighbors')

        if 'spCentroids' in results and not hasattr(self, 'sp_centroids'):
            # try:
            self.sp_centroids = self.load_pipeline_result('spCentroids')
            # except:
                # missing.append('spCentroids')
        
        if 'edgeNeighbors' in results and not hasattr(self, 'edge_neighbors'):
            # try:
            self.edge_neighbors = self.load_pipeline_result('edgeNeighbors')
            # except:
            #     missing.append('edgeNeighbors')

        if 'dedgeNeighbors' in results and not hasattr(self, 'dedge_neighbors'):
            # try:
            self.dedge_neighbors = self.load_pipeline_result('dedgeNeighbors')
            self.dedge_neighbor_graph = from_dict_of_lists(self.dedge_neighbors)
            # except:
            #     missing.append('dedgeNeighbors')

        if 'dedgeVectors' in results and not hasattr(self, 'dedge_vectors'):
            self.dedge_vectors = self.load_pipeline_result('dedgeVectors')


    def compute_cluster_score(self, cluster, seed=None, seed_weight=0, verbose=False, method='rc-mean', thresh=.2):
        
        self.load_multiple_results(['neighbors', 'spCentroids', 'texHist'])

        # try:
                
        cluster_list = list(cluster)
        assert len(cluster_list) > 0
        cluster_avg = self.texton_hists[cluster_list].mean(axis=0)

        surrounds = set([i for i in set.union(*[self.neighbors[c] for c in cluster]) if i not in cluster and i != -1])
        
        if len(surrounds) == 0: # single sp on background
            return np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan

        surrounds_list = list(surrounds)

        # if verbose:
        #     print 'min', surrounds_list[ds.argmin()]

        ds = np.atleast_1d(np.squeeze(chi2s([cluster_avg], self.texton_hists[surrounds_list])))

        if method == 'min':
            surround_dist = ds.min()
            if verbose:
                print 'min', surrounds_list[ds.argmin()]
            score = surround_dist

        elif method == 'mean':
            surround_dist = ds.mean()
            score = surround_dist

        elif method == 'percentage':
            surround_dist = np.count_nonzero(ds > thresh) / float(len(ds)) # hard
            score = surround_dist

        elif method == 'percentage-soft':        
            sigma = .01
            surround_dist = np.sum(1./(1+np.exp((thresh - ds)/sigma)))/len(ds); #soft        
            if verbose:
                for t in sorted(zip(surrounds_list, ds), key=itemgetter(1)):
                    print t
                plt.hist(ds, bins=np.linspace(0,1,50));
                plt.show();

            score = surround_dist

        elif method == 'rc-min' or method == 'rc-mean':

            sigs_front = []
            if len(cluster) > 1:
                
                # frontiers = set.union(*[set(self.neighbors[s]) for s in surrounds_list]) & set(cluster_list)
                frontiers = cluster
                for f in frontiers:
                    if len(surrounds & set(self.neighbors[f])) > 0:
                        alternative_sps = list((surrounds & set(self.neighbors[f])) - {-1})
                    else:
                        q = list(surrounds-{-1})
                        alternative_sps = [q[np.squeeze(cdist([self.sp_centroids[f]], self.sp_centroids[q])).argmin()]]
                        
                    # alternative_dist = np.atleast_1d(np.squeeze(chi2s([self.texton_hists[f]], 
                    #                                 self.texton_hists[alternative_sps+[f]].mean(axis=0)))).min()
                    # alternative_dist = np.min([chi2(self.texton_hists[f], self.texton_hists[[s,f]].mean(axis=0)) for s in alternative_sps])
                    assert len(alternative_sps) > 0
                    alternative_dist = np.mean([chi2(self.texton_hists[f], self.texton_hists[[s,f]].mean(axis=0)) for s in alternative_sps])

                    # interior_neighbors = list((set(cluster_list) & set(self.neighbors[f])) - {-1})
                    # interior_avg = self.texton_hists[interior_neighbors + [f]].mean(axis=0)
                    # curr_dist = .5 * chi2(self.texton_hists[f], interior_avg) + .5 * chi2(self.texton_hists[f], cluster_avg)
                    
                    if seed is not None:
                        curr_dist = chi2(self.texton_hists[f], seed_weight*self.texton_hists[seed]+(1.-seed_weight)*self.texton_hists[cluster_list].mean(axis=0))                        
                    else:
                        curr_dist = chi2(self.texton_hists[f], self.texton_hists[cluster_list].mean(axis=0))

                    sig = alternative_dist - curr_dist
                    sigs_front.append(sig)

                if verbose:
                    print 'frontiers advantages'
                    print zip(list(frontiers), sigs_front)

            sigs_sur = []
            for s in surrounds:
                sur_neighbors = self.neighbors[s] - set(cluster)
                assert len(sur_neighbors) > 0
                alternative_dist = np.mean([chi2(self.texton_hists[s], self.texton_hists[[s,n]].mean(axis=0)) for n in sur_neighbors])

                if seed is not None:
                    curr_dist = chi2(self.texton_hists[s], seed_weight*self.texton_hists[seed]+(1.-seed_weight)*self.texton_hists[cluster_list+[s]].mean(axis=0))
                else:
                    curr_dist = chi2(self.texton_hists[s], self.texton_hists[cluster_list+[s]].mean(axis=0))

                sig = curr_dist - alternative_dist
                sigs_sur.append(sig)

            if verbose:
                print 'surround advantages'
                print zip(list(surrounds), sigs_sur)

            # sigs_sur = np.array(sigs_sur)
            # sigs_front = np.array(sigs_front)

            # thresh = .2
            # # sig = int(sig > thresh)
            # sigma = .025
            # sigs = 1./(1+np.exp((thresh - sigs)/sigma)); #soft

            if method == 'rc-min':
                if len(sigs_front) > 0:
                    score = min(np.min(sigs_sur), np.min(sigs_front))
                    s1_max = np.max(sigs_sur)
                    s1_min = np.min(sigs_sur)
                    s2_max = np.max(sigs_front)
                    s2_min = np.min(sigs_front)
                else:
                    score = np.min(sigs_sur)
                    s1_max = np.max(sigs_sur)
                    s1_min = np.min(sigs_sur)
                    s2_max = np.nan
                    s2_min = np.nan

                # score = .5*np.min(sigs_sur)+.5*np.min(sigs_front) if len(sigs_front) > 0 else 0                
            elif method == 'rc-mean':
                if len(sigs_front) > 0:
                    # print np.mean(sigs_sur), np.mean(sigs_front)
                    score = .5*np.mean(sigs_sur)+.5*np.mean(sigs_front)
                    # score = max(np.mean(sigs_sur), np.mean(sigs_front))
                    s1_max = np.max(sigs_sur)
                    s1_min = np.min(sigs_sur)
                    s2_max = np.max(sigs_front)
                    s2_min = np.min(sigs_front)
                else:
                    score = np.mean(sigs_sur)
                    s1_max = np.max(sigs_sur)
                    s1_min = np.min(sigs_sur)
                    s2_max = np.nan
                    s2_min = np.nan

        else:
            raise 'unrecognized method'
                # print list(frontiers)[np.argmin(sigs)]

        if len(cluster) > 1:
            inter_sp_dists = np.atleast_1d(np.squeeze(pdist(self.texton_hists[list(cluster)], chi2)))
            inter_sp_dist = inter_sp_dists.mean()
        else:
            inter_sp_dist = 0

        if seed is not None:
            seed_dist = chi2(cluster_avg, self.texton_hists[seed])
        else:
            seed_dist = np.nan

        # except Exception as e:
        #     sys.stderr.write('ERROR %d\n' % seed)
        #     raise e

        if method == 'rc-min' or method == 'rc-mean':
            if len(sigs_front) > 0:
                return score,  np.mean(sigs_sur),  np.mean(sigs_front), inter_sp_dist, seed_dist, s1_max, s1_min, s2_max, s2_min
            else:
                return score,  np.mean(sigs_sur),  np.nan, inter_sp_dist, seed_dist, s1_max, s1_min, s2_max, s2_min
        else:
            return score,  np.nan, np.nan, inter_sp_dist, seed_dist, np.nan, np.nan, np.nan, np.nan


    # def plot_scores(self, peaks, clusters_allhistory, scores, margin=300, visualize_peaks=False,
    #                 xmin=None, ymin=None, xmax=None, ymax=None, ncol=4, sort_by_score=True):
    def plot_scores(self, peaks1, peaks2, clusters_allhistory, scores, margin=300, visualize_peaks=False,
                    xmin=None, ymin=None, xmax=None, ymax=None, ncol=4, sort_by_score=True):

        fig, axes = plt.subplots(7,1, squeeze=True, sharex=True, figsize=(20,40))

        axes = np.atleast_1d(axes)

        peaks = np.unique(np.r_[peaks1, peaks2])

        scores_to_plot = scores[:,1]
        axes[0].plot(scores_to_plot);
        for p in peaks:
            axes[0].vlines(p, ymin=scores_to_plot.min(), ymax=scores_to_plot.max(), colors='r');
        axes[0].set_xlabel('iteration');
        axes[0].set_ylabel('significance score', fontsize=20);

        s1_mean = scores[:,2]
        axes[1].plot(s1_mean);
        for p in peaks1:
            axes[1].vlines(p, ymin=s1_mean.min(), ymax=s1_mean.max(), colors='r');
        axes[1].set_xlabel('iteration');
        axes[1].set_ylabel('surround keep outside', fontsize=20);

        s2_mean = scores[:,3]
        axes[2].plot(s2_mean);
        for p in peaks2:
            axes[2].vlines(p, ymin=np.nanmin(s2_mean), ymax=np.nanmax(s2_mean), colors='r');
        axes[2].set_xlabel('iteration');
        axes[2].set_ylabel('frontier keep inside', fontsize=20);

        # s1_mean = scores[:,2]
        # s1_max = scores[:,6]
        # s1_min = scores[:,7]
        # axes[3].plot(s1_mean);
        # axes[3].plot(s1_max, 'g');
        # axes[3].plot(s1_min, 'g');
        # for p in peaks1:
        #     axes[3].vlines(p, ymin=s1_mean.min(), ymax=s1_mean.max(), colors='r');
        # axes[3].set_xlabel('iteration');
        # axes[3].set_ylabel('surround keep outside', fontsize=20);

        # s2_mean = scores[:,3]
        # s2_max = scores[:,8]
        # s2_min = scores[:,9]
        # axes[4].plot(s2_mean);
        # axes[4].plot(s2_max, 'g');
        # axes[4].plot(s2_min, 'g');
        # for p in peaks2:
        #     axes[4].vlines(p, ymin=np.nanmin(s2_mean), ymax=np.nanmax(s2_mean), colors='r');
        # axes[4].set_xlabel('iteration');
        # axes[4].set_ylabel('frontier keep inside', fontsize=20);

        scores_to_plot = scores[:,4]
        axes[5].plot(scores_to_plot);
        for p in peaks:
            axes[5].vlines(p, ymin=np.nanmin(scores_to_plot), ymax=np.nanmax(scores_to_plot), colors='r');
        axes[5].set_xlabel('iteration');
        axes[5].set_ylabel('mean interior distance', fontsize=20);

        scores_to_plot = scores[:,5]
        axes[6].plot(scores_to_plot);
        for p in peaks:
            axes[6].vlines(p, ymin=scores_to_plot.min(), ymax=scores_to_plot.max(), colors='r');
        axes[6].set_xlabel('iteration');
        axes[6].set_ylabel('seed-avg distance', fontsize=20);

        if not sort_by_score:
            peaks = sorted(peaks)

        if len(peaks) > 0:    
            if visualize_peaks:
                self.visualize_clusters_in_subplots([clusters_allhistory[p] for p in peaks], 
                        ['peak %d, score %.3f'%(pk, sc) for pi, (pk, sc) in enumerate(zip(peaks, scores[peaks,1]))],
                        ncol=ncol)
        

    def visualize_clusters_in_subplots(self, clusters, titles=None, ncol=3, 
                                    xmin=None, ymin=None, xmax=None, ymax=None, fname=None):

        margin = 300
        ncol = min(ncol, len(clusters))

        if xmin is None:
            self.load_multiple_results(['spCentroids'])

            xmin = np.inf
            ymin = np.inf
            xmax = 0
            ymax = 0

            for cl in clusters:
                centroids = self.sp_centroids[list(cl), ::-1]
                xmin = min(xmin, centroids[:,0].min(axis=0))
                xmax = max(xmax, centroids[:,0].max(axis=0))
                ymin = min(ymin, centroids[:,1].min(axis=0))
                ymax = max(ymax, centroids[:,1].max(axis=0))

            xmin = int(max(0, xmin - margin))
            ymin = int(max(0, ymin - margin))
            xmax = int(min(self.image_width, xmax + margin))
            ymax = int(min(self.image_height, ymax + margin))

        n_cls = len(clusters)
        fig, axes = plt.subplots(int((n_cls-1)/ncol)+1, ncol, figsize=(20,20), squeeze=False)

        for ci, cl in enumerate(clusters):
            viz = self.visualize_cluster(cl, highlight_seed=True, seq_text=True,
                                       ymin=ymin, xmin=xmin, ymax=ymax, xmax=xmax)
            ax = axes[ci/ncol, ci%ncol]
            ax.imshow(viz)
            ax.axis('off')
            if titles is not None:
                ax.set_title(titles[ci])
        
        if fname is not None:
            fig.savefig(fname)
            plt.close()
        else:
            plt.show()

    def grow_cluster(self, seed, seed_weight=.5,
                    verbose=False, all_history=True, 
                     num_sp_percentage_limit=0.05,
                     min_size=1, min_distance=3, thresh=.4,
                     threshold_abs=-0.05, threshold_rel=.4,
                     peakedness_limit=0.001, method='rc-min',
                     seed_dist_lim = 0.2,
                     inter_sp_dist_lim=0.3):

        from networkx import from_dict_of_lists, Graph, adjacency_matrix, connected_components

        from itertools import chain
        from skimage.feature import peak_local_max
        from scipy.spatial import ConvexHull
        from matplotlib.path import Path

        sys.stderr.write('%d\n'%seed)

        self.load_multiple_results(['neighbors', 'texHist', 'segmentation'])

        neighbor_long_graph = from_dict_of_lists(self.neighbors_long)

        visited = set([])
        curr_cluster = set([])

        candidate_scores = [0]
        candidate_sps = [seed]

        score_tuples = []
        added_sps = []
        n_sps = []

        cluster_list = []
        addorder_list = []

        iter_ind = 0

        hull_begin = False

        nearest_surrounds = []
        toadd_list = []

        while len(candidate_sps) > 0:

            if verbose:
                print '\niter', iter_ind

            best_ind = np.argmax(candidate_scores)

            just_added_score = candidate_scores[best_ind]
            sp = candidate_sps[best_ind]

            del candidate_scores[best_ind]
            del candidate_sps[best_ind]

            if sp in curr_cluster:
                continue

            curr_cluster.add(sp)
            added_sps.append(sp)

            extra_sps = []

            sg = self.neighbor_long_graph.subgraph(list(set(range(self.n_superpixels)) - curr_cluster))
            for c in connected_components(sg):
                if len(c) < 10: # holes
                    extra_sps.append(c)

            extra_sps = list(chain(*extra_sps))
            curr_cluster |= set(extra_sps)
            added_sps += extra_sps

            tt = self.compute_cluster_score(curr_cluster, seed=seed, seed_weight=seed_weight, verbose=verbose, thresh=thresh, method=method)

            # nearest_surround = compute_nearest_surround(curr_cluster, neighbors, texton_hists)
            # nearest_surrounds.append(nearest_surround)

            tot, s1, s2, inter_sp_dist, seed_dist, s1_max, s1_min, s2_max, s2_min = tt

            cluster_avg = self.texton_hists[list(curr_cluster)].mean(axis=0)

            if (len(curr_cluster) > 5 and (seed_dist > seed_dist_lim or inter_sp_dist > inter_sp_dist_lim)) or (len(curr_cluster) > int(self.n_superpixels * num_sp_percentage_limit)):
                # if verbose:
                if len(curr_cluster) > int(self.n_superpixels * num_sp_percentage_limit):
                    # if verbose:
                    print seed, 'terminate due to over-size'
                elif seed_dist > .2 :
                    # if verbose:
                    print seed, 'terminate due to seed_dist exceeds threshold', seed_dist
                elif inter_sp_dist > .3:
                    # if verbose:
                    print seed, 'terminate due to inter_sp_dist exceeds threshold', inter_sp_dist
                break

            if np.isnan(tot):
                return [seed], -np.inf
            score_tuples.append(np.r_[just_added_score, tt])

            n_sps.append(len(curr_cluster))

            # just_added_score, curr_total_score, exterior_score, interior_score, compactness_score, surround_pval,
            # interior_pval, size_prior

            if verbose:
                print 'add', sp
                print 'extra', extra_sps
                print 'added_sps', added_sps
                print 'curr_cluster', curr_cluster
                print 'n_sps', n_sps
                print 'tt', tot
                if len(curr_cluster) != len(added_sps):
                    print len(curr_cluster), len(added_sps)
                    raise

            cluster_list.append(curr_cluster.copy())
            addorder_list.append(added_sps[:])
            candidate_sps = (set(candidate_sps) | \
                             (set.union(*[self.neighbors_long[i] for i in list(extra_sps)+[sp]]) - {-1})) - curr_cluster

            if len(candidate_sps) == 0:
                return [], []

            candidate_sps = list(candidate_sps)

            # for c in candidate_sps:
            #     int_dist = chi2(self.texton_hists[c], self.texton_hists[list(curr_cluster)+[c]].mean(axis=0))
            #     ext_neighbors = self.neighbors[c] - set(curr_cluster)
            #     chi2(self.texton_hists[c], self.texton_hists[s+[c]]) for s in ext_neighbors

            candidate_scores = []
            candidate_seed_dists = []
            for c in candidate_sps:
                int_neighbors = list(set(curr_cluster) & self.neighbors[c])
                assert len(int_neighbors) > 0
                int_dist = chi2(self.texton_hists[c], self.texton_hists[int_neighbors + [c]].mean(axis=0))
                curr_dist = chi2(self.texton_hists[c], self.texton_hists[list(curr_cluster)+[c]].mean(axis=0))
                seed_dist = chi2(self.texton_hists[c], self.texton_hists[seed])
                sc = .1 * int_dist + .3* curr_dist + .6*seed_dist
                candidate_seed_dists.append(seed_dist)
                candidate_scores.append(-sc)

            if np.min(candidate_seed_dists) > .4:
                if verbose:
                    print 'iter', iter_ind, 'closest seed_dist', np.min(candidate_seed_dists)
                break
                
            # h_avg = self.texton_hists[list(curr_cluster)].mean(axis=0)
            # candidate_scores = -.5*chi2s([h_avg], self.texton_hists[candidate_sps])-\
            #                 .5*chi2s([self.texton_hists[seed]], self.texton_hists[candidate_sps])

            # candidate_scores = candidate_scores.tolist()

            if verbose:
    #                 print 'candidate', candidate_sps
                print 'candidate\n'

                for i,j in sorted(zip(candidate_scores, candidate_sps), reverse=True):
                    print i, j
                print 'best', candidate_sps[np.argmax(candidate_scores)]

            toadd_list.append(candidate_sps[np.argmax(candidate_scores)])

            iter_ind += 1

        score_tuples = np.array(score_tuples)

        # peaks_sorted, peakedness_sorted = find_score_peaks(score_tuples[:,1], min_size=min_size, min_distance=min_distance,
        #                                                     threshold_abs=threshold_abs, threshold_rel=threshold_rel, 
        #                                                     peakedness_lim=peakedness_limit,
        #                                                     verbose=verbose)

        if np.all(np.isnan(score_tuples[:,2])):
            peaks_sorted1 = []
            peakedness_sorted1 = []
        else:        
            peaks_sorted1, peakedness_sorted1 = find_score_peaks(score_tuples[:,2], min_size=min_size, min_distance=min_distance,
                                                                threshold_abs=threshold_abs, threshold_rel=threshold_rel, 
                                                                peakedness_lim=peakedness_limit,
                                                                verbose=verbose)


        if np.all(np.isnan(score_tuples[:,3])):
            peaks_sorted2 = []
            peakedness_sorted2 = []
        else:
            peaks_sorted2, peakedness_sorted2 = find_score_peaks(score_tuples[:,3], min_size=min_size, min_distance=min_distance,
                                                            threshold_abs=threshold_abs, threshold_rel=threshold_rel, 
                                                            peakedness_lim=peakedness_limit,
                                                            verbose=verbose)

        peaks_sorted = np.atleast_1d(np.unique(np.r_[peaks_sorted1, peaks_sorted2]).astype(np.int))
        peakedness_sorted = np.atleast_1d(np.unique(np.r_[peakedness_sorted1, peakedness_sorted2]))

        if all_history:
            return addorder_list, score_tuples, peaks_sorted, peakedness_sorted, toadd_list, peaks_sorted1, peaks_sorted2
        else:
            return [addorder_list[i] for i in peaks_sorted], score_tuples[peaks_sorted, 1]


    def convert_cluster_to_descriptor(self, cluster, verbose=False):

        self.load_multiple_results(['neighbors', 'dedgeNeighbors', 'texHist', 'edgeCoords', 'spAreas'])

        dedge_set = self.find_boundary_dedges_ordered(cluster, verbose=verbose)
        
        interior_texture = self.texton_hists[list(cluster)].mean(axis=0)

        surrounds = [e[0] for e in dedge_set]
        exterior_textures = np.array([self.texton_hists[s] if s!=-1 else np.nan * np.ones((self.texton_hists.shape[1],)) 
                                      for s in surrounds])

        points = np.array([self.edge_coords[frozenset(e)].mean(axis=0) for e in dedge_set])
        center = points.mean(axis=0)

        area = self.sp_areas[cluster].sum()
        
        return (dedge_set, interior_texture, exterior_textures, points, center, area)


    def find_boundary_dedges_ordered(self, cluster, verbose=False):

        self.load_multiple_results(['neighbors', 'dedgeNeighbors', 'edgeCoords'])

        surrounds = set([i for i in set.union(*[self.neighbors[c] for c in cluster]) if i not in cluster])
        surrounds = set([i for i in surrounds if any([n not in cluster for n in self.neighbors[i]])])
        
        non_border_dedges = [(s, int_sp) for s in surrounds for int_sp in set.intersection(set(cluster), self.neighbors[s]) 
                             if int_sp != -1 and s != -1]
        border_dedges = [(-1,f) for f in cluster if -1 in self.neighbors[f]] if -1 in surrounds else []

        dedges_cluster = non_border_dedges + border_dedges
        # dedges_cluster_long = [dedge for dedge in dedges_cluster if len(self.edge_coords[frozenset(dedge)]) > 10]

        if verbose:
            print 'surrounds', surrounds
            # print 'non_border_dedges', non_border_dedges
            # print 'border_dedges', border_dedges
            print 'dedges_cluster', dedges_cluster
            # print 'dedges_cluster_long', dedges_cluster_long

        # dedges_cluster_long_sorted = order_nodes(dedges_cluster_long, self.dedge_neighbor_graph, verbose=verbose)    
        dedges_cluster_sorted = order_nodes(dedges_cluster, self.dedge_neighbor_graph, verbose=verbose)    
        
        # missing = set(dedges_cluster_long) - set(dedges_cluster_long_sorted)
        # assert len(missing) == 0, missing
        missing = set(dedges_cluster) - set(dedges_cluster_sorted)
        if len(missing) > 0:
            print 'dedges missing', len(missing), '%d%%'%(100*len(missing)/float(len(dedges_cluster)))
            dedges_cluster_sorted += missing
        
        return dedges_cluster_sorted
        # return dedges_cluster_long_sorted


    def _get_image_filepath(self, stack=None, resol='lossless', section=None, version='rgb-jpg'):
        if stack is None:
            stack = self.stack
        if resol is None:
            resol = self.resol
        if section is None:
            section = self.slice_ind
            
        slice_str = '%04d' % section

        if version == 'rgb-jpg':
            image_dir = os.path.join(self.data_dir, stack+'_'+resol+'_aligned_cropped_downscaled')
            image_name = '_'.join([stack, slice_str, resol, 'aligned_cropped_downscaled'])
            image_path = os.path.join(image_dir, image_name + '.jpg')
        # elif version == 'gray-jpg':
        #     image_dir = os.path.join(self.data_dir, stack+'_'+resol+'_cropped_grayscale_downscaled')
        #     image_name = '_'.join([stack, slice_str, resol, 'warped'])
        #     image_path = os.path.join(image_dir, image_name + '.jpg')
        elif version == 'gray':
            image_dir = os.path.join(self.data_dir, stack+'_'+resol+'_aligned_cropped_grayscale')
            image_name = '_'.join([stack, slice_str, resol, 'aligned_cropped_grayscale'])
            image_path = os.path.join(image_dir, image_name + '.tif')
        elif version == 'rgb':
            image_dir = os.path.join(self.data_dir, stack+'_'+resol+'_aligned_cropped')
            image_name = '_'.join([stack, slice_str, resol, 'aligned_cropped'])
            image_path = os.path.join(image_dir, image_name + '.tif')

        elif version == 'stereotactic-rgb-jpg':
            image_dir = os.path.join(self.data_dir, stack+'_'+resol+'_aligned_cropped_downscaled_stereotactic')
            image_name = '_'.join([stack, slice_str, resol, 'aligned_cropped_downscaled_stereotactic'])
            image_path = os.path.join(image_dir, image_name + '.jpg')
         
        return image_path
    
    def _read_image(self, image_filename):
        if image_filename.endswith('tif') or image_filename.endswith('tiff'):
            from PIL.Image import open
            img = np.array(open(image_filename))/255.
        else:
            img = imread(image_filename)
        return img

    def _load_image(self, versions=['rgb', 'gray', 'rgb-jpg'], force_reload=True):
        
        assert self.image_name is not None, 'Image is not specified'

        if 'rgb-jpg' in versions:
            if force_reload or not hasattr(self, 'image_rgb_jpg'):
                image_filename = self._get_image_filepath(version='rgb-jpg')
                # assert os.path.exists(image_filename), "Image '%s' does not exist" % (self.image_name + '.tif')
                self.image_rgb_jpg = self._read_image(image_filename)
        
        if 'rgb' in versions:
            if force_reload or not hasattr(self, 'image_rgb'):
                image_filename = self._get_image_filepath(version='rgb')
                # assert os.path.exists(image_filename), "Image '%s' does not exist" % (self.image_name + '.tif')
                self.image_rgb = self._read_image(image_filename)

        if 'gray' in versions and not hasattr(self, 'image'):
            if force_reload or not hasattr(self, 'gray'):
                image_filename = self._get_image_filepath(version='gray')
                # assert os.path.exists(image_filename), "Image '%s' does not exist" % (self.image_name + '.tif')
                self.image = self._read_image(image_filename)

    def set_gabor_params(self, gabor_params_id):
        
        self.gabor_params_id = gabor_params_id
        # self._generate_kernels(self.gabor_params)
    
    def _generate_kernels(self, gabor_params_id=None):
        
        from skimage.filter import gabor_kernel

        if gabor_params_id is None:
            assert hasattr(self, 'gabor_params_id')
            gabor_params_id = self.gabor_params_id

        self.gabor_params = json.load(open(os.path.join(self.params_dir, 'gabor', 'gabor_' + gabor_params_id + '.json'), 'r')) if gabor_params_id is not None else None
        
        theta_interval = self.gabor_params['theta_interval']
        self.n_angle = int(180/theta_interval)
        freq_step = self.gabor_params['freq_step']
        freq_max = 1./self.gabor_params['min_wavelen']
        freq_min = 1./self.gabor_params['max_wavelen']
        bandwidth = self.gabor_params['bandwidth']
        self.n_freq = int(np.log(freq_max/freq_min)/np.log(freq_step)) + 1
        self.frequencies = freq_max/freq_step**np.arange(self.n_freq)
        self.angles = np.arange(0, self.n_angle)*np.deg2rad(theta_interval)

        kernels = [gabor_kernel(f, theta=t, bandwidth=bandwidth) for f in self.frequencies for t in self.angles]
        kernels = map(np.real, kernels)

        biases = np.array([k.sum() for k in kernels])
        mean_bias = biases.mean()
        self.kernels = [k/k.sum()*mean_bias for k in kernels] # this enforces all kernel sums to be identical, but non-zero

        # kernels = [k - k.sum()/k.size for k in kernels] # this enforces all kernel sum to be zero

        self.n_kernel = len(kernels)
        self.max_kern_size = np.max([kern.shape[0] for kern in self.kernels])

    def print_gabor_info(self):
        print 'num. of kernels: %d' % (self.n_kernel)
        print 'frequencies:', self.frequencies
        print 'wavelength (pixels):', 1/self.frequencies
        print 'max kernel matrix size:', self.max_kern_size
        
    def set_segmentation_params(self, segm_params_id):
        
        self.segm_params_id = segm_params_id
        if segm_params_id == 'gridsize200':
            self.grid_size = 200
        elif segm_params_id == 'gridsize100':
            self.grid_size = 100
        elif segm_params_id == 'gridsize50':
            self.grid_size = 50
        elif segm_params_id == 'tSLIC200':
            pass
        else:
            self.segm_params = json.load(open(os.path.join(self.params_dir, 'segm', 'segm_' + segm_params_id + '.json'), 'r')) if segm_params_id is not None else None

    def set_vq_params(self, vq_params_id):
        
        self.vq_params_id = vq_params_id
        self.vq_params = json.load(open(os.path.join(self.params_dir, 'vq', 'vq_' + vq_params_id + '.json'), 'r')) if vq_params_id is not None else None
        
    
    def _param_str(self, param_dependencies):
        param_strs = []
        if 'gabor' in param_dependencies:
            param_strs.append('gabor-' + self.gabor_params_id)
        if 'segm' in param_dependencies:
            param_strs.append('segm-' + self.segm_params_id)
        if 'vq' in param_dependencies:
            param_strs.append('vq-' + self.vq_params_id)
        return '-'.join(param_strs)
        
    def _refresh_result_info(self):
        with open(self.repo_dir + '/results.csv', 'r') as f:
            f.readline()
            self.result_info = {}
            for row in csv.DictReader(f, delimiter=' '):
                self.result_info[row['name']] = row
        
        
    def _get_result_filename(self, result_name, include_path=True):

        if not hasattr(self, 'result_info'):
            with open(self.repo_dir + '/results.csv', 'r') as f:
                f.readline()
                self.result_info = {}
                for row in csv.DictReader(f, delimiter=' '):
                    self.result_info[row['name']] = row
                
        info = self.result_info[result_name]
        
        if info['dir'] == '0':
            result_dir = self.results_dir
            prefix = self.image_name
        elif info['dir'] == '1':
            result_dir = os.path.join(self.root_results_dir, self.stack)
            prefix = self.stack + '_' + self.resol

        else:
            raise Exception('unrecognized result dir specification')
            
        if info['param_dep'] == '0':
            param_dep = ['gabor']
        elif info['param_dep'] == '1':
            param_dep = ['segm']
        elif info['param_dep'] == '2':
            param_dep = ['gabor', 'vq']
        elif info['param_dep'] == '3':
            param_dep = ['gabor', 'segm', 'vq']
        else:
            raise Exception('unrecognized result param_dep specification')
        
        if include_path:
            result_filename = os.path.join(result_dir, '_'.join([prefix, self._param_str(param_dep), 
                                                             result_name + '.' + info['extension']]))
        else:
            result_filename = '_'.join([prefix, self._param_str(param_dep), result_name + '.' + info['extension']])

        return result_filename
            
    def check_pipeline_result(self, result_name):
#         if REGENERATE_ALL_RESULTS:
#             return False
        result_filename = self._get_result_filename(result_name)
        return os.path.exists(result_filename)

    def load_pipeline_result(self, result_name, is_rgb=None, section=None):
        
        result_filename = self._get_result_filename(result_name)
        ext = self.result_info[result_name]['extension']
        
        if ext == 'npy':
            assert os.path.exists(result_filename), "%d: Pipeline result '%s' does not exist, trying to find %s" % (self.slice_ind, result_name + '.' + ext, result_filename)
            data = np.load(result_filename)
        elif ext == 'tif' or ext == 'png' or ext == 'jpg':
            data = imread(result_filename, as_grey=False)
            data = self._regulate_image(data, is_rgb)
        elif ext == 'pkl':
            data = pickle.load(open(result_filename, 'r'))
        elif ext == 'hdf':
            with open_file(result_filename, mode="r") as f:
                data = f.get_node('/data').read()
        elif ext == 'bp':
            data = bp.unpack_ndarray_file(result_filename)

        # print 'loaded %s' % result_filename

        return data
        
    def save_pipeline_result(self, data, result_name, is_rgb=None, section=None):
        
        result_filename = self._get_result_filename(result_name)
        ext = self.result_info[result_name]['extension']

        if ext == 'npy':
            np.save(result_filename, data)
        elif ext == 'tif' or ext == 'jpg':
            data = self._regulate_image(data, is_rgb)
            imsave(result_filename, data)
        elif ext == 'png': # cv2
            data = self._regulate_image(data, is_rgb)
            cv2.imwrite(result_filename, data)
        elif ext == 'pkl':
            pickle.dump(data, open(result_filename, 'w'))
        elif ext == 'hdf':
            filters = Filters(complevel=9, complib='blosc')
            with open_file(result_filename, mode="w") as f:
                _ = f.create_carray('/', 'data', Atom.from_dtype(data.dtype), filters=filters, obj=data)
        elif ext == 'bp':
            bp.pack_ndarray_file(data, result_filename)
            
        print 'saved %s' % result_filename



    # def load_review_result_paths(self, username, timestamp, stack=None, section=None, suffix=''):

    #     if stack is None:
    #         stack = self.stack
    #     if section is None:
    #         section = self.slice_ind

    #     if not hasattr(self, 'result_list'):
    #         self.reload_labelings()

    #     if username is not None:
    #         if len(self.result_list[username]) == 0:
    #             return None
    #     else: # search labelings of any user
    #         self.result_list_flatten = [(usr, ts) for usr, timestamps in self.result_list.iteritems() for ts in timestamps ] # [(username, timestamp)..]
    #         if len(self.result_list_flatten) == 0:
    #             return None

    #     if timestamp == 'latest':
    #         if username is not None:
    #             timestamps_sorted = map(itemgetter(1), sorted(map(lambda s: (datetime.datetime.strptime(s, "%m%d%Y%H%M%S"), s), self.result_list[username]), reverse=True))
    #             timestamp = timestamps_sorted[0]
    #         else:
    #             ts_str_usr_sorted = sorted([(datetime.datetime.strptime(ts, "%m%d%Y%H%M%S"), ts, usr) for usr, ts in self.result_list_flatten], reverse=True)
    #             timestamp = ts_str_usr_sorted[0][1]
    #             username = ts_str_usr_sorted[0][2]

    #     return os.path.join(self.labelings_dir, '_'.join([stack, '%04d'%section, username, timestamp]) + '_'+suffix+'.pkl')


    def load_review_result_path(self, username, timestamp, stack=None, section=None, suffix=''):
        if stack is None:
            stack = self.stack
        if section is None:
            section = self.slice_ind

        if not hasattr(self, 'result_list') or len(self.result_list[username]) == 0:
            self.reload_labelings()

        if username is None: # search labelings of any user
            self.result_list_flatten = [(usr, ts) for usr, timestamps in self.result_list.iteritems() for ts in timestamps ] # [(username, timestamp)..]
            if len(self.result_list_flatten) == 0:
                # sys.stderr.write('username is empty\n')
                return None
        
        if timestamp == 'latest':
            if username is not None:
                
                if len(self.result_list[username]) == 0:
                    return None

                timestamps_sorted = map(itemgetter(1), sorted(map(lambda s: (datetime.datetime.strptime(s, "%m%d%Y%H%M%S"), s), self.result_list[username]), reverse=True))
                timestamp = timestamps_sorted[0]
            else:
                ts_str_usr_sorted = sorted([(datetime.datetime.strptime(ts, "%m%d%Y%H%M%S"), ts, usr) for usr, ts in self.result_list_flatten], reverse=True)
                timestamp = ts_str_usr_sorted[0][1]
                username = ts_str_usr_sorted[0][2]

        return os.path.join(self.labelings_dir, '_'.join([stack, '%04d'%section, username, timestamp]) + '_'+suffix+'.pkl'), username, timestamp


    def save_proposal_review_result(self, result, username, timestamp, suffix, stack=None, section=None):

        if stack is None:
            stack = self.stack

        if section is None:
            section = self.slice_ind

        path = os.path.join(self.labelings_dir, '_'.join([stack, '%04d'%section, username, timestamp]) + '_'+suffix+'.pkl')

        # path = self.load_review_result_path(username, timestamp, suffix=suffix)

        path_to_dir = os.path.dirname(path)
        if not os.path.exists(path_to_dir):
            os.makedirs(path_to_dir)

        pickle.dump(result, open(path, 'w'))
        print 'Labeling saved to', path

        return path

    def reload_labelings(self):
        # if not hasattr(self, 'result_list'):
        from collections import defaultdict

        # self.result_list = defaultdict(lambda: defaultdict(list))
        self.result_list = defaultdict(list)

        if os.path.exists(self.labelings_dir):
            for fn in os.listdir(self.labelings_dir):
                st, se, us, ts, suf = fn[:-4].split('_')
                # self.result_list[us][ts].append(suf)
                self.result_list[us].append(ts)

    # def reload_labelings_all(self):
    #     # if not hasattr(self, 'result_list'):
    #     from collections import defaultdict

    #     for stack, (first, last) in detect_bbox_range_lookup.iteritems():

    #         self.result_list = defaultdict(list)

    #         for os.listdir():


    #         if os.path.exists(self.labelings_dir):
    #             for fn in os.listdir(self.labelings_dir):
    #                 st, se, us, ts, suf = fn[:-4].split('_')
    #                 # self.result_list[us][ts].append(suf)
    #                 self.result_list[us].append((st, se, ts))

    def load_proposal_review_result(self, username, timestamp, suffix, stack=None, section=None):

        if stack is None:
            stack = self.stack
        if section is None:
            section = self.slice_ind

        if not hasattr(self, 'result_list') or len(self.result_list[username]) == 0:
            self.reload_labelings()

        if username is not None:
            if len(self.result_list[username]) == 0:
                sys.stderr.write('username %s does not have any annotations for current section %d \n' % (username, self.slice_ind))
                return None

        if suffix == 'all':
            results = []
            for suf in self.result_list[username][timestamp]:
                ret = self.load_review_result_path(username=username, timestamp=timestamp, suffix=suf, stack=stack, section=section)
                if ret is None:
                    return None
                else:
                    path, usr, ts = ret
                    results.append((username, timestamp, suf, pickle.load(open(path, 'r'))))
            return results
        else:
            ret = self.load_review_result_path(username=username, timestamp=timestamp, suffix=suffix, stack=stack, section=section)
            if ret is None:
                return None
            else:
                path, usr, ts = ret
                return (usr, ts, suffix, pickle.load( open(path, 'r')))


    def load_labeling(self, stack=None, section=None, labeling_name=None):
        labeling_fn = self._load_labeling_path(stack, section, labeling_name)
        labeling = pickle.load(open(labeling_fn, 'r'))
        return labeling


    def _load_labeling_preview_path(self, stack=None, section=None, labeling_name=None):
        if stack is None:
            stack = self.stack
        if section is None:
            section = self.slice_ind

        if labeling_name.endswith('pkl'): # full filename
            return os.path.join(self.labelings_dir, labeling_name[:-4]+'.jpg')
        else:
            return os.path.join(self.labelings_dir, '_'.join([stack, '%04d'%section, labeling_name]) + '.jpg')
        
    def _load_labeling_path(self, stack=None, section=None, labeling_name=None):
        if stack is None:
            stack = self.stack
        if section is None:
            section = self.slice_ind

        if labeling_name.endswith('pkl'): # full filename
            return os.path.join(self.labelings_dir, labeling_name)
        else:
            return os.path.join(self.labelings_dir, '_'.join([stack, '%04d'%section, labeling_name]) + '.pkl')
        

    def load_labeling_preview(self, stack=None, section=None, labeling_name=None):
        return imread(self._load_labeling_preview_path(stack, section, labeling_name))

    def save_labeling(self, labeling, new_labeling_name, labelmap_vis):
        
        try:
            os.makedirs(self.labelings_dir)
        except:
            pass

        new_labeling_fn = self._load_labeling_path(labeling_name=new_labeling_name)
        # os.path.join(self.labelings_dir, self.image_name + '_' + new_labeling_name + '.pkl')
        pickle.dump(labeling, open(new_labeling_fn, 'w'))
        print 'Labeling saved to', new_labeling_fn

        # new_preview_fn = self._load_labeling_preview_path(labeling_name=new_labeling_name)

        # # os.path.join(self.labelings_dir, self.image_name + '_' + new_labeling_name + '.tif')
        # data = self._regulate_image(labelmap_vis, is_rgb=True)
        # imsave(new_preview_fn, data)
        # print 'Preview saved to', new_preview_fn

        return new_labeling_fn
        
    def _regulate_image(self, img, is_rgb=None):
        """
        Ensure the image is of type uint8.
        """

        if not np.issubsctype(img, np.uint8):
            try:
                img = img_as_ubyte(img)
            except:
                img_norm = (img-img.min()).astype(np.float)/(img.max() - img.min())    
                img = img_as_ubyte(img_norm)

        if is_rgb is not None:
            if img.ndim == 2 and is_rgb:
                img = gray2rgb(img)
            elif img.ndim == 3 and not is_rgb:
                img = rgb2gray(img)

        return img
    
    
    # def visualize_segmentation(self, bg='rgb-jpg', show_sp_index=True):

    #     if bg == 'originalImage':
    #         if not hasattr(self, 'image'):
    #             self._load_image(format='rgb-jpg')
    #         viz = self.image
    #     elif bg == 'transparent':


    #     img_superpixelized = mark_boundaries(viz, self.segmentation)
    #     img_superpixelized = img_as_ubyte(img_superpixelized)
    #     dm.save_pipeline_result(img_superpixelized, 'segmentationWithoutText')

    #     for s in range(n_superpixels):
    #         cv2.putText(img_superpixelized, str(s), 
    #                     tuple(np.floor(sp_centroids[s][::-1]).astype(np.int) - np.array([10,-10])), 
    #                     cv2.FONT_HERSHEY_DUPLEX, .5, ((255,0,255)), 1)


    def visualize_edge_set(self, edges, bg=None, show_edge_index=False, c=None, tight=False,
                        ymin=None, xmin=None, ymax=None, xmax=None, linewidth=5):
        
        if tight:
            self.load_multiple_results(['edgeCoords'])
            cs = np.vstack(self.edge_coords[frozenset(e)] for e in edges)
            tight_xmin, tight_ymin = cs.min(axis=0).astype(np.int) - 300
            tight_xmax, tight_ymax = cs.max(axis=0).astype(np.int) + 300

        if ymin is None:
            ymin = tight_ymin if tight else self.ymin
        if xmin is None:
            xmin = tight_xmin if tight else self.xmin
        if ymax is None:
            ymax = tight_ymax if tight else self.ymax
        if xmax is None:
            xmax = tight_xmax if tight else self.xmax

        import cv2

        self.load_multiple_results(['edgeCoords', 'edgeMidpoints', 'dedgeVectors'])

        if bg == 'originalImage':
            if not hasattr(self, 'image_rgb_jpg'):
                self._load_image(versions=['rgb-jpg'])
            segmentation_viz = self.image_rgb_jpg
        elif bg == 'segmentationWithText':
            if not hasattr(self, 'segmentation_vis'):
                self.segmentation_viz = self.load_pipeline_result('segmentationWithText')
            segmentation_viz = self.segmentation_viz
        elif bg == 'segmentationWithoutText':
            if not hasattr(self, 'segmentation_notext_vis'):
                self.segmentation_notext_viz = self.load_pipeline_result('segmentationWithoutText')
            segmentation_viz = self.segmentation_notext_viz
        else:
            segmentation_viz = bg
            
        vis = img_as_ubyte(segmentation_viz[ymin:ymax+1, xmin:xmax+1])
        
        directed = isinstance(list(edges)[0], tuple)
        
        if c is None:
            c = [255,0,0]
        
        for e_ind, edge in enumerate(edges):
                
            if directed:
                e = frozenset(edge)
                midpoint = self.edge_midpoints[e]
                end = midpoint + 10 * self.dedge_vectors[edge]
                cv2.line(vis, tuple((midpoint-(xmin, ymin)).astype(np.int)), 
                         tuple((end-(xmin, ymin)).astype(np.int)), 
                         (c[0],c[1],c[2]), 2)

                cv2.circle(vis, tuple((end-(xmin, ymin)).astype(np.int)), 3,
                         (c[0],c[1],c[2]), -1)

                stroke_pts = self.edge_coords[e]
            else:
                stroke_pts = self.edge_coords[edge]

            for x, y in stroke_pts:
                cv2.circle(vis, (x-xmin, y-ymin), linewidth, c, -1)

            if show_edge_index:
                cv2.putText(vis, str(e_ind), 
                            tuple(np.floor(midpoint + [-50, 30] - (xmin, ymin)).astype(np.int)), 
                            cv2.FONT_HERSHEY_DUPLEX, 1, ((c[0],c[1],c[2])), 3)
        
        return vis
    
    
    def visualize_edge_sets(self, edge_sets, bg='segmentationWithText', show_set_index=0, colors=None, neighbors=None, labels=None,
                            ymin=None, xmin=None, ymax=None, xmax=None, linewidth=5):
        '''
        Return a visualization of multiple sets of edgelets
        '''

        if ymin is None:
            ymin = self.ymin
        if xmin is None:
            xmin = self.xmin
        if ymax is None:
            ymax = self.ymax
        if xmax is None:
            xmax = self.xmax
        
        import cv2
        
        if not hasattr(self, 'edge_coords'):
            self.edge_coords = self.load_pipeline_result('edgeCoords')
           
        if not hasattr(self, 'edge_midpoints'):
            self.edge_midpoints = self.load_pipeline_result('edgeMidpoints')
            
        if not hasattr(self, 'dedge_vectors'):
            self.dedge_vectors = self.load_pipeline_result('dedgeVectors')

        if colors is None:
            colors = np.uint8(np.loadtxt(os.environ['GORDON_REPO_DIR'] + '/visualization/100colors.txt') * 255)
        elif isinstance(colors[0], int):
            colors = [colors] * len(edge_sets)

        
        if bg == 'originalImage':
            if not hasattr(self, 'image_rgb_jpg'):
                self._load_image(versions=['rgb-jpg'])
            segmentation_viz = self.image_rgb_jpg
        elif bg == 'segmentationWithText':
            if not hasattr(self, 'segmentation_vis'):
                self.segmentation_viz = self.load_pipeline_result('segmentationWithText')
            segmentation_viz = self.segmentation_viz
        elif bg == 'segmentationWithoutText':
            if not hasattr(self, 'segmentation_notext_vis'):
                self.segmentation_notext_viz = self.load_pipeline_result('segmentationWithoutText')
            segmentation_viz = self.segmentation_notext_viz
        else:
            segmentation_viz = bg
            
        vis = img_as_ubyte(segmentation_viz[ymin:ymax+1, xmin:xmax+1])
            
        # if input are tuples, draw directional sign
        if len(edge_sets) == 0:
            return vis
        else:
            directed = isinstance(list(edge_sets[0])[0], tuple)
            
        for edgeSet_ind, edges in enumerate(edge_sets):
            
#             junction_pts = []
            
            if labels is None:
                s = str(edgeSet_ind)
                c = colors[edgeSet_ind%len(colors)].astype(np.int)
            else:
                s = labels[edgeSet_ind]
                c = colors[int(s)%len(colors)].astype(np.int)
            
            for e_ind, edge in enumerate(edges):
                
                if directed:
                    e = frozenset(edge)
                    midpoint = self.edge_midpoints[e]
                    end = midpoint + 10 * self.dedge_vectors[edge]
                    cv2.line(vis, tuple((midpoint-(xmin, ymin)).astype(np.int)), 
                             tuple((end-(xmin, ymin)).astype(np.int)), 
                             (c[0],c[1],c[2]), 2)

                    cv2.circle(vis, tuple((end-(xmin, ymin)).astype(np.int)), 3,
                             (c[0],c[1],c[2]), -1)
                    stroke_pts = self.edge_coords[e]
                else:
                    stroke_pts = self.edge_coords[edge]
                
                for x, y in stroke_pts:
                    cv2.circle(vis, (x-xmin, y-ymin), linewidth, c, -1)

                    # vis[max(0, y-5):min(self.image_height, y+5), 
                    #     max(0, x-5):min(self.image_width, x+5)] = (c[0],c[1],c[2],1) if vis.shape[2] == 4 else c
                                                
#                 if neighbors is not None:
#                     nbrs = neighbors[degde]
#                     for nbr in nbrs:
#                         pts2 = self.edge_coords[frozenset(nbr)]
#                         am = np.unravel_index(np.argmin(cdist(pts[[0,-1]], pts2[[0,-1]]).flat), (2,2))
# #                         print degde, nbr, am
#                         junction_pt = (pts[-1 if am[0]==1 else 0] + pts2[-1 if am[1]==1 else 0])/2
#                         junction_pts.append(junction_pt)
                 
            if show_set_index:

                if directed:
                    centroid = np.mean([self.edge_midpoints[frozenset(e)] for e in edges], axis=0)
                else:
                    centroid = np.mean([self.edge_midpoints[e] for e in edges], axis=0)

                cv2.putText(vis, s, 
                            tuple(np.floor(centroid + [-100, 100] - (xmin, ymin)).astype(np.int)), 
                            cv2.FONT_HERSHEY_DUPLEX,
                            3, ((c[0],c[1],c[2])), 3)
            
#             for p in junction_pts:
#                 cv2.circle(vis, tuple(np.floor(p).astype(np.int)), 5, (255,0,0), -1)
        
        return vis

    
    def visualize_kernels(self):
        fig, axes = plt.subplots(self.n_freq, self.n_angle, figsize=(20,20))

        for i, kern in enumerate(self.kernels):
            r, c = np.unravel_index(i, (self.n_freq, self.n_angle))
            axes[r,c].matshow(kern, cmap=plt.cm.gray)
        #     axes[r,c].colorbar()
        plt.show()


    def visualize_cluster(self, cluster, bg='segmentationWithText', seq_text=False, highlight_seed=True,
                         ymin=None, xmin=None, ymax=None, xmax=None, tight=False):

        if tight:
            self.load_multiple_results(['spCentroids'])
            cs = self.sp_centroids[cluster]
            tight_ymin, tight_xmin = cs.min(axis=0).astype(np.int) - 300
            tight_ymax, tight_xmax = cs.max(axis=0).astype(np.int) + 300

        if ymin is None:
            ymin = tight_ymin if tight else self.ymin
        if xmin is None:
            xmin = tight_xmin if tight else self.xmin
        if ymax is None:
            ymax = tight_ymax if tight else self.ymax
        if xmax is None:
            xmax = tight_xmax if tight else self.xmax
        
        if not hasattr(self, 'sp_coords'):
            self.sp_coords = self.load_pipeline_result('spCoords')
                    
        if bg == 'originalImage':
            if not hasattr(self, 'image_rgb_jpg'):
                self._load_image(versions=['rgb-jpg'])
            segmentation_viz = self.image_rgb_jpg
        elif bg == 'segmentationWithText':
            if not hasattr(self, 'segmentation_vis'):
                self.segmentation_viz = self.load_pipeline_result('segmentationWithText')
            segmentation_viz = self.segmentation_viz
        elif bg == 'segmentationWithoutText':
            if not hasattr(self, 'segmentation_notext_vis'):
                self.segmentation_notext_viz = self.load_pipeline_result('segmentationWithoutText')
            segmentation_viz = self.segmentation_notext_viz
        else:
            segmentation_viz = bg

        msk = -1*np.ones((self.image_height, self.image_width), np.int8)

        for i, c in enumerate(cluster):
            rs = self.sp_coords[c][:,0]
            cs = self.sp_coords[c][:,1]
            if highlight_seed and i == 0:
                msk[rs, cs] = 1
            else:
                msk[rs, cs] = 0

        viz_msk = label2rgb(msk[ymin:ymax+1, xmin:xmax+1], image=segmentation_viz[ymin:ymax+1, xmin:xmax+1])

        if seq_text:
            viz_msk = img_as_ubyte(viz_msk[...,::-1])

            if not hasattr(self, 'sp_centroids'):
                self.sp_centroids = self.load_pipeline_result('spCentroids')

            import cv2
            for i, sp in enumerate(cluster):
                cv2.putText(viz_msk, str(i), tuple((self.sp_centroids[sp, ::-1] - (xmin, ymin) - (10,-10)).astype(np.int)), cv2.FONT_HERSHEY_DUPLEX, 1., ((0,255,255)), 1)

        return viz_msk

    
    def visualize_edges_and_superpixels(self, edge_sets, clusters, colors=None):
        if colors is None:
            colors = np.loadtxt(os.environ['GORDON_REPO_DIR'] + '/visualization/100colors.txt')
            
        vis = self.visualize_multiple_clusters(clusters, colors=colors)
        viz = self.visualize_edge_sets(edge_sets, directed=True, img=vis, colors=colors)
        return viz
        
    
    def visualize_multiple_clusters(self, clusters, bg='segmentationWithText', alpha_blend=False, colors=None,
                                    show_cluster_indices=False,
                                    ymin=None, xmin=None, ymax=None, xmax=None,
                                    labels=None):
        
        if ymin is None:
            ymin = self.ymin
        if xmin is None:
            xmin = self.xmin
        if ymax is None:
            ymax = self.ymax
        if xmax is None:
            xmax = self.xmax

        self.load_multiple_results(['segmentation'])

        if len(clusters) == 0:
            return segmentation_vis
        
        if colors is None:
            colors = np.loadtxt(os.environ['GORDON_REPO_DIR'] + '/visualization/100colors.txt')
                    
        if bg == 'originalImage':
            if not hasattr(self, 'image_rgb_jpg'):
                self._load_image(versions=['rgb-jpg'])
            segmentation_viz = self.image_rgb_jpg
        elif bg == 'segmentationWithText':
            if not hasattr(self, 'segmentation_vis'):
                self.segmentation_viz = self.load_pipeline_result('segmentationWithText')
            segmentation_viz = self.segmentation_viz
        elif bg == 'segmentationWithoutText':
            if not hasattr(self, 'segmentation_notext_vis'):
                self.segmentation_notext_viz = self.load_pipeline_result('segmentationWithoutText')
            segmentation_viz = self.segmentation_notext_viz
        else:
            segmentation_viz = bg

        if alpha_blend:

            mask_alpha = .4
            
            for ci, c in enumerate(clusters):
                m =  np.zeros((self.n_superpixels,), dtype=np.float)
                m[list(c)] = mask_alpha
                alpha = m[self.segmentation[ymin:ymax+1, xmin:xmax+1]]
                alpha[~self.mask[ymin:ymax+1, xmin:xmax+1]] = 0
                
                mm = np.zeros((self.n_superpixels,3), dtype=np.float)
                mm[list(c)] = colors[ci]
                blob = mm[self.segmentation[ymin:ymax+1, xmin:xmax+1]]
                
                if ci == 0:
                    vis = alpha_blending(blob, segmentation_viz[ymin:ymax+1, xmin:xmax+1], alpha, 1.)
                else:
                    vis = alpha_blending(blob, vis[..., :-1], alpha, vis[..., -1])

        else:
        
            sp_labels = -1*np.ones((self.n_superpixels,), dtype=np.int)

            for ci, c in enumerate(clusters):
                sp_labels[list(c)] = ci

            labelmap = sp_labels[self.segmentation[ymin:ymax+1, xmin:xmax+1]]
            labelmap[~self.mask[ymin:ymax+1, xmin:xmax+1]] = -1

            vis = label2rgb(labelmap, image=segmentation_viz[ymin:ymax+1, xmin:xmax+1])

        vis = img_as_ubyte(vis)

        if show_cluster_indices:
            if not hasattr(self, 'sp_centroids'):
                self.sp_centroids = self.load_pipeline_result('spCentroids')

            for ci, cl in enumerate(clusters):
                # cluster_center_yx = self.sp_centroids[cl].mean(axis=0).astype(np.int)
                # cv2.putText(vis, str(ci), tuple(cluster_center_yx[::-1] - np.array([10,-10])), 
                #             cv2.FONT_HERSHEY_DUPLEX, 1., ((0,255,255)), 1)

                for i, sp in enumerate(cl):
                    if labels is not None:
                        cv2.putText(vis, labels[ci][i], tuple((self.sp_centroids[sp][::-1] - (xmin, ymin) - [10,-10]).astype(np.int)), 
                                      cv2.FONT_HERSHEY_DUPLEX, 1., (0,0,0), 1)
                    else:
                        cv2.putText(vis, str(i), tuple((self.sp_centroids[sp][::-1] - (xmin, ymin) - [10,-10]).astype(np.int)), 
                                      cv2.FONT_HERSHEY_DUPLEX, 1., (0,0,0), 1)
        
        return vis.copy()


    def vertices_from_dedges(self, dedges, sparsify=True):

        self.load_multiple_results(['edgeMidpoints', 'edgeEndpoints'])

        vertices = []
        for de_ind, de in enumerate(dedges):
            midpt = self.edge_midpoints[frozenset(de)]
            endpts = self.edge_endpoints[frozenset(de)]
            endpts_next_dedge = self.edge_endpoints[frozenset(dedges[(de_ind+1)%len(dedges)])]

            dij = cdist([endpts[0], endpts[-1]], [endpts_next_dedge[0], endpts_next_dedge[-1]])
            i,j = np.unravel_index(np.argmin(dij), (2,2))
            if i == 0:
                vertices += [endpts[-1], midpt, endpts[0]]
            else:
                vertices += [endpts[0], midpt, endpts[-1]]
    
        if sparsify:
            # keep only vertices that are far enough apart
            vertices = np.array(vertices)
            distance_to_next_point = np.sqrt(np.sum(np.r_[vertices[1:] - vertices[:-1], [vertices[0] - vertices[-1]]]**2, axis=1))
            vertices = vertices[distance_to_next_point > 20]
            vertices = vertices.tolist()

        return vertices

def fit_ellipse_to_points(pts):

    pts = np.array(list(pts) if isinstance(pts, set) else pts)

    c0 = pts.mean(axis=0)

    coords0 = pts - c0

    U,S,V = np.linalg.svd(np.dot(coords0.T, coords0)/coords0.shape[0])
    v1 = U[:,0]
    v2 = U[:,1]
    s1 = np.sqrt(S[0])
    s2 = np.sqrt(S[1])

    return v1, v2, s1, s2, c0


def scores_to_vote(scores):
    vals = np.unique(scores)
    d = dict(zip(vals, np.linspace(0, 1, len(vals))))
    votes = np.array([d[s] for s in scores])
    votes = votes/votes.sum()
    return votes


def display_image(vis, filename='tmp.jpg'):
    
    if vis.dtype != np.uint8:
        imsave(filename, img_as_ubyte(vis))
    else:
        imsave(filename, vis)
            
    from IPython.display import FileLink
    return FileLink(filename)

def display_images_in_grids(vizs, nc, titles=None, export_fn=None):

    n = len(vizs)
    nr = int(np.ceil(n/float(nc)))
    aspect_ratio = vizs[0].shape[1]/float(vizs[0].shape[0]) # width / height

    fig, axes = plt.subplots(nr, nc, figsize=(nc*5*aspect_ratio, nr*5))
    axes = axes.flatten()

    for i in range(len(axes)):
        if i >= n:
            axes[i].axis('off');
        else:
            axes[i].imshow(vizs[i]);
            if titles is not None:
                axes[i].set_title(titles[i], fontsize=20);
            axes[i].set_xticks([]);
            axes[i].set_yticks([]);
            
    fig.tight_layout();
    
    if export_fn is not None:
        plt.savefig(export_fn);

    plt.show();

# <codecell>

# import numpy as np
# from scipy.ndimage.filters import maximum_filter
# from scipy.ndimage.morphology import generate_binary_structure, binary_erosion

# def detect_peaks(image):
#     """
#     Takes an image and detect the peaks usingthe local maximum filter.
#     Returns a boolean mask of the peaks (i.e. 1 when
#     the pixel's value is the neighborhood maximum, 0 otherwise)
#     """

#     # define an 8-connected neighborhood
#     neighborhood = generate_binary_structure(2,2)

#     #apply the local maximum filter; all pixel of maximal value 
#     #in their neighborhood are set to 1
#     local_max = maximum_filter(image, footprint=neighborhood)==image
#     #local_max is a mask that contains the peaks we are 
#     #looking for, but also the background.
#     #In order to isolate the peaks we must remove the background from the mask.

#     #we create the mask of the background
#     background = (image==0)

#     #a little technicality: we must erode the background in order to 
#     #successfully subtract it form local_max, otherwise a line will 
#     #appear along the background border (artifact of the local maximum filter)
#     eroded_background = binary_erosion(background, structure=neighborhood, border_value=1)

#     #we obtain the final mask, containing only peaks, 
#     #by removing the background from the local_max mask
#     detected_peaks = local_max - eroded_background

#     return detected_peaks

# <codecell>

# def visualize_cluster(scores, cluster='all', title='', filename=None):
#     '''
#     Generate black and white image with the cluster of superpixels highlighted
#     '''
    
#     vis = scores[segmentation]
#     if cluster != 'all':
#         cluster_selection = np.equal.outer(segmentation, cluster).any(axis=2)
#         vis[~cluster_selection] = 0
    
#     plt.matshow(vis, cmap=plt.cm.Greys_r);
#     plt.axis('off');
#     plt.title(title)
#     if filename is not None:
#         plt.savefig(os.path.join(result_dir, 'stages', filename + '.png'), bbox_inches='tight')
# #     plt.show()
#     plt.close();
    

def paint_superpixels_on_image(superpixels, segmentation, img):
    '''
    Highlight a cluster of superpixels on the real image
    '''    

    cluster_map = -1*np.ones_like(segmentation)
    for s in superpixels:
        cluster_map[segmentation==s] = 1
    vis = label2rgb(cluster_map, image=img)
    return vis
    
def paint_superpixel_groups_on_image(sp_groups, segmentation, img, colors):
    '''
    Highlight multiple superpixel groups with different colors on the real image
    '''
    
    cluster_map = -1*np.ones_like(segmentation)
    for i, sp_group in enumerate(sp_groups):
        for j in sp_group:
            cluster_map[segmentation==j] = i
    vis = label2rgb(cluster_map, image=img, colors=colors)
    return vis

# <codecell>

def kl(a,b):
    m = (a!=0) & (b!=0)
    return np.sum(a[m]*np.log(a[m]/b[m]))

def js(u,v):
    m = .5 * (u + v)
    r = .5 * (kl(u,m) + kl(v,m))
    return r

# <codecell>

def chi2(u,v):
    """
    Compute Chi^2 distance between two distributions.
    
    Empty bins are ignored.
    
    """
    
    u[u==0] = 1e-6
    v[v==0] = 1e-6
    r = np.sum(((u-v)**2).astype(np.float)/(u+v))

    # m = (u != 0) & (v != 0)
    # r = np.sum(((u[m]-v[m])**2).astype(np.float)/(u[m]+v[m]))
    
    # r = np.nansum(((u-v)**2).astype(np.float)/(u+v))
    return r


def chi2s(h1s, h2s):
    '''
    h1s is n x n_texton
    MUST be float type
    '''    
    return np.sum((h1s-h2s)**2/(h1s+h2s+1e-10), axis=1)

# def chi2s(h1s, h2s):
#     '''
#     h1s is n x n_texton
#     '''
#     s = (h1s+h2s).astype(np.float)
#     with np.errstate(divide='ignore', invalid='ignore'):
#         ss = (h1s-h2s)**2/s
#     ss[s==0] = 0
#     return np.sum(ss, axis=1)


def alpha_blending(src_rgb, dst_rgb, src_alpha, dst_alpha):
    
    
    if src_rgb.dtype == np.uint8:
        src_rgb = img_as_float(src_rgb)

    if dst_rgb.dtype == np.uint8:
        dst_rgb = img_as_float(dst_rgb)
        
    if isinstance(src_alpha, float) or  isinstance(src_alpha, int):
        src_alpha = src_alpha * np.ones((src_rgb.shape[0], src_rgb.shape[1]))

    if isinstance(dst_alpha, float) or  isinstance(dst_alpha, int):
        dst_alpha = dst_alpha * np.ones((dst_rgb.shape[0], dst_rgb.shape[1]))

    out_alpha = src_alpha + dst_alpha * (1. - src_alpha)
    out_rgb = (src_rgb * src_alpha[..., None] +
               dst_rgb * dst_alpha[..., None] * (1. - src_alpha[..., None])) / out_alpha[..., None]
    
    out = np.zeros((src_rgb.shape[0], src_rgb.shape[1], 4))
        
    out[..., :3] = out_rgb
    out[..., 3] = out_alpha
    
    return out


def bbox_2d(img):
    rows = np.any(img, axis=1)
    cols = np.any(img, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]

    return cmin, cmax, rmin, rmax

def bbox_3d(img):

    r = np.any(img, axis=(1, 2))
    c = np.any(img, axis=(0, 2))
    z = np.any(img, axis=(0, 1))

    rmin, rmax = np.where(r)[0][[0, -1]]
    cmin, cmax = np.where(c)[0][[0, -1]]
    zmin, zmax = np.where(z)[0][[0, -1]]

    return cmin, cmax, rmin, rmax, zmin, zmax



def find_z_section_map(stack, volume_zmin, downsample_factor = 16):

    section_thickness = 20 # in um
    xy_pixel_distance_lossless = 0.46
    xy_pixel_distance_tb = xy_pixel_distance_lossless * 32 # in um, thumbnail
    # factor = section_thickness/xy_pixel_distance_lossless

    xy_pixel_distance_downsampled = xy_pixel_distance_lossless * downsample_factor
    z_xy_ratio_downsampled = section_thickness / xy_pixel_distance_downsampled

    section_bs_begin, section_bs_end = section_range_lookup[stack]

    map_z_to_section = {}
    for s in range(section_bs_begin, section_bs_end+1):
        for z in range(int(z_xy_ratio_downsampled*s) - volume_zmin, 
                       int(z_xy_ratio_downsampled*(s+1)) - volume_zmin + 1):
            map_z_to_section[z] = s
            
    return map_z_to_section