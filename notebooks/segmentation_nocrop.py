# -*- coding: utf-8 -*-
# <nbformat>3.0</nbformat>

# <codecell>

%load_ext autoreload
%autoreload 2

from preamble import *

# <codecell>

# Over-segment the image into superpixels using SLIC (http://ivrg.epfl.ch/research/superpixels)

from skimage.segmentation import slic, mark_boundaries
from skimage.util import img_as_ubyte, pad

masked_image = dm.image.copy()

# approx_bg_intensity = dm.image[10:20, 10:20].mean()
# masked_image[~dm.mask] = approx_bg_intensity

masked_image[~dm.mask] = 0

segmentation = slic(gray2rgb(masked_image), n_segments=int(dm.segm_params['n_superpixels']), 
                    max_iter=10, 
                    compactness=float(dm.segm_params['slic_compactness']), 
                    sigma=float(dm.segm_params['slic_sigma']), 
                    enforce_connectivity=True)

# <codecell>

display(mark_boundaries(masked_image, segmentation))

# <codecell>

n = len(np.unique(segmentation))

def f(i):
    m = dm.mask[segmentation == i]
    return np.count_nonzero(m)/float(len(m)) < .8
        
q = Parallel(n_jobs=16)(delayed(f)(i) for i in range(n))
                        
masked_segmentation = segmentation.copy()
for i in np.where(q)[0]:
    masked_segmentation[segmentation == i] = -1

# <codecell>

display(mark_boundaries(masked_image, masked_segmentation))

# <codecell>

from skimage.segmentation import relabel_sequential

try:
    masked_segmentation_relabeled = dm.load_pipeline_result('segmentation', 'npy')

except:

    # segmentation starts from 0
    masked_segmentation_relabeled, fw, inv = relabel_sequential(masked_segmentation + 1)

    # make background label -1
    masked_segmentation_relabeled -= 1

    dm.save_pipeline_result(masked_segmentation_relabeled, 'segmentation', 'npy')

# <codecell>

from joblib import Parallel, delayed

sp_props = regionprops(masked_segmentation_relabeled + 1, intensity_image=dm.image, cache=True)

def obtain_props_worker(i):
    return sp_props[i].centroid, sp_props[i].area, sp_props[i].mean_intensity, sp_props[i].bbox

r = Parallel(n_jobs=16)(delayed(obtain_props_worker)(i) for i in range(len(sp_props)))

sp_centroids = np.array([s[0] for s in r])
sp_areas = np.array([s[1] for s in r])
sp_mean_intensity = np.array([s[2] for s in r])
sp_bbox = np.array([s[3] for s in r])

sp_properties = np.column_stack([sp_centroids, sp_areas, sp_mean_intensity, sp_bbox])

dm.save_pipeline_result(sp_properties, 'spProps', 'npy')

# <codecell>

n_superpixels = len(np.unique(masked_segmentation_relabeled)) - 1

img_superpixelized = mark_boundaries(dm.image, masked_segmentation_relabeled)
img_superpixelized_with_text = img_as_ubyte(img_superpixelized)

for s in range(n_superpixels):
    img_superpixelized_with_text = cv2.putText(img_superpixelized_with_text, str(s), 
                                               tuple(np.floor(sp_centroids[s][::-1]).astype(np.int)), 
                                               cv2.FONT_HERSHEY_COMPLEX_SMALL,
                                               .5, ((255,0,255)), 1)

dm.save_pipeline_result(img_superpixelized_with_text, 'segmentationWithText', 'jpg')

# <codecell>

display(img_superpixelized_with_text)

# <codecell>

# Compute neighbor lists and connectivity matrix

from skimage.morphology import disk
from skimage.filter.rank import gradient

try:
    neighbors = dm.load_pipeline_result('neighbors', 'npy')

except:

    edge_map = gradient(masked_segmentation_relabeled.astype(np.uint8), disk(3))
    neighbors = [set() for i in range(n_superpixels)]

    for y,x in zip(*np.nonzero(edge_map)):
        neighbors[masked_segmentation_relabeled[y,x]] |= set(masked_segmentation_relabeled[y-2:y+2,x-2:x+2].ravel())

    for i in range(n_superpixels):
        neighbors[i] -= set([i])

    dm.save_pipeline_result(neighbors, 'neighbors', 'npy')
