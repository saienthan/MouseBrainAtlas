import os
import sys

os.chdir(sys.argv[1])
prefix = sys.argv[2]
for i in range(99):
	if os.path.isfile(prefix+'_%04d.tif'%i):
		os.mkdir('%04d'%i)
		os.rename(prefix+'_%04d.tif'%i, '%04d/'%i+prefix+'_%04d.tif'%i)
