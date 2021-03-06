#!/usr/bin/env python

import os
import sys
import json

sys.path.append(os.environ['REPO_DIR'] + '/utilities/')
from metadata import *

stack = sys.argv[1]
input_dir = sys.argv[2]
output_dir = sys.argv[3]
filename_pairs = json.loads(sys.argv[4])
suffix = 'thumbnail'

parameter_dir = os.path.join(os.environ['REPO_DIR'], "preprocess/parameters")

rg_param = os.path.join(parameter_dir, "Parameters_Rigid.txt")
rg_param_mutualinfo = os.path.join(parameter_dir, "Parameters_Rigid_MutualInfo.txt")
rg_param_noNumberOfSamples = os.path.join(parameter_dir, "Parameters_Rigid_noNumberOfSpatialSamples.txt")
rg_param_requiredRatioOfValidSamples = os.path.join(parameter_dir, "Parameters_Rigid_RequiredRatioOfValidSamples.txt")

for fn_pair in filename_pairs:
	prev_fn = fn_pair['prev_fn']
	curr_fn = fn_pair['curr_fn']

	output_subdir = os.path.join(output_dir, curr_fn + '_to_' + prev_fn)

	if os.path.exists(output_subdir):
		sys.stderr.write('Result for aligning %s to %s already exists.\n' % (curr_fn, prev_fn))
		continue

	execute_command('rm -rf ' + output_subdir)
	os.makedirs(output_subdir)

	execute_command('%(elastix_bin)s -f %(fixed_fn)s -m %(moving_fn)s -out %(output_subdir)s -p %(rg_param)s' % \
			{'elastix_bin': os.environ['ELASTIX_BIN'],
			'rg_param': rg_param,
			'output_subdir': output_subdir,
			'fixed_fn': os.path.join(input_dir, prev_fn + '.tif'),
			'moving_fn': os.path.join(input_dir, curr_fn + '.tif')
			})
