import os
import argparse
import time
import logging
import shutil
import numpy as np

import pyemma.coordinates as coor

# TODO: Make complementary plotting script for:
#   - PMF of TICA 1
#   - PMF of TICA 1 vs Q.
#   - PMF of TICA 1 vs TICA 2 (if possible).
#   - TICA eigenvalues
# Take correlation with Q to determine which way is 'folded'
# Q = np.hstack([ np.loadtxt("%s/Q.dat" % x) for x in dirs])

if __name__ == "__main__":
    starttime = time.time()

    parser = argparse.ArgumentParser(description='.')
    parser.add_argument('--temps', type=str, required=True, help='File holding directory names.')
    parser.add_argument('--lag', type=int, required=True, help='Lag to use for TICA.')
    parser.add_argument('--stride', type=int, required=True, help='Stride to use for TICA.')
    parser.add_argument('--feature', type=str, required=True, help='Input feature to TICA.')
    args = parser.parse_args()

    tempsfile = args.temps
    lag = args.lag
    stride = args.stride
    feature = args.feature
    
    available_features = ["native_contacts","all_contacts"]
    if feature not in available_features:
        raise IOError("--feature should be in: %s" % available_features.__str__())

    if feature == "all_contacts":
        prefix = "all"
    else:
        prefix = "nat"

    if not os.path.exists("tica_%s_%d_%d" % (prefix,lag,stride)):
        os.mkdir("tica_%s_%d_%d" % (prefix,lag,stride))

    logging.basicConfig(filename="tica_%s_%d_%d/tica.log" % (prefix,lag,stride),
                        filemode="w",
                        format="%(levelname)s:%(name)s:%(asctime)s: %(message)s",
                        datefmt="%H:%M:%S",
                        level=logging.DEBUG)

    # Have to use local logger so as not to conflict with pyemma's logging.
    logger = logging.getLogger('calcTICA')

    temps = [ x.rstrip("\n") for x in open(tempsfile,"r").readlines() ]
    uniq_Tlist = []
    Qlist = []
    Tlist = []
    for i in range(len(temps)):
        T = temps[i].split("_")[0]
        if T not in uniq_Tlist:
            uniq_Tlist.append(T)
            Tlist.append([temps[i]])
        else:
            idx = uniq_Tlist.index(T)
            Tlist[idx].append(temps[i])

    logger.info("TICA inputs")
    logger.info("  lag       = %d" % lag)
    logger.info("  stride    = %d" % stride)

    # For each unique temperature. Run TICA
    for i in range(len(Tlist)):
        dirs = Tlist[i]
        logger.info("Running TICA T = %s" % uniq_Tlist[i])

        traj_list = [ "%s/traj.xtc" % x for x in dirs ]
        topfile = "%s/Native.pdb" % dirs[0]
        n_residues = len(open(topfile,"r").readlines()) - 1

        logger.info("  picking features: ")
        if feature == "all_contacts":
            logger.info("    contacts between all pairs")
            pairs = []
            for n in range(n_residues):
                for m in range(n + 4,n_residues):
                    pairs.append([n,m])
            pairs = np.array(pairs)
            threshold = 0.8
            scale = 0.3
        else:
            # Use native contact distance as threshold for native pairs.
            logger.info("    contacts between native pairs")
            pairs = np.loadtxt("%s/native_contacts.ndx" % dirs[0],dtype=int,skiprows=1) - 1
            threshold = np.loadtxt("%s/pairwise_params" % dirs[0],usecols=(4,))[1:2*pairs.shape[0]:2] + 0.1
            scale = 0.3

        # Featurizer parameterizes a pipeline to read in trajectory in chunks.
        feat = coor.featurizer(topfile)
        feat.add_tanh_contacts(pairs,threshold=threshold,scale=scale,periodic=False)

        # Source trajectories
        logger.info("  sourcing trajectories: %s" % traj_list.__str__())
        inp = coor.source(traj_list, feat)

        # Stride has a drastic influence on the number of acceptable eigenvalues.
        logger.info("  computing TICA")
        tica_obj = coor.tica(inp, lag=lag, stride=stride, var_cutoff=0.9, kinetic_map=True)

        # Check if eigenvalues go negative at some point. Truncate before that if necessary.
        first_neg_eigval = np.where(tica_obj.eigenvalues < 0)[0][0]
        keep_dims = min([tica_obj.dimension(),first_neg_eigval])
        logger.info("  TICA done")
        logger.info("    number of dimensions: %d" % tica_obj.dimension())
        logger.info("    first negative eigenvalue: %d" % first_neg_eigval)

        # Save principal TICA coordinate(s) in each subdirectory
        logger.info("  getting output from TICA object")
        if keep_dims >= 2:
            Y = tica_obj.get_output(dimensions=np.arange(2)) # get tica coordinates
        else:
            Y = tica_obj.get_output(dimensions=np.arange(1)) # get tica coordinates

        tica1_weights = np.vstack((pairs[:,0],pairs[:,1],tica_obj.eigenvectors[:,0])).T
        if keep_dims >= 2:
            tica2_weights = np.vstack((pairs[:,0],pairs[:,1],tica_obj.eigenvectors[:,1])).T
    
        # Save general TICA info
        logger.info("  saving TICA weights")
        os.chdir("tica_%s_%d_%d" % (prefix,lag,stride))
        if os.path.exists("TICA_parameters"):
            shutil.move("TICA_parameters","old_TICA_parameters")
        with open("TICA_parameters","w") as fout:
            fout.write("prefix     %s\n" % prefix)
            fout.write("feature    %s\n" % feature)
            fout.write("lag        %d\n" % lag)
            fout.write("stride     %d\n" % stride)
            if prefix == "all":
                fout.write("threshold  %e\n" % threshold)
            else:
                fout.write("threshold  native r0\n")
            fout.write("scale      %e\n" % scale)
            fout.write("keep dims  %d\n" % keep_dims)

        np.savetxt("eigenvalues.dat",tica_obj.eigenvalues)
        np.savetxt("tica1_%s_%d_%d_weights.dat" % (prefix,lag,stride),tica1_weights)
        if keep_dims >= 2:
            np.savetxt("tica2_%s_%d_%d_weights.dat" % (prefix,lag,stride),tica2_weights)
        os.chdir("..")

        logger.info("  saving TICA timeseries in directories")
        for n in range(len(dirs)):
            os.chdir(dirs[n])
            np.savetxt("tica1_%s_%d_%d.dat" % (prefix,lag,stride),Y[n][:,0])
            if keep_dims >= 2:
                np.savetxt("tica2_%s_%d_%d.dat" % (prefix,lag,stride),Y[n][:,1])
            os.chdir("..")
    dt = time.time() - starttime
    logger.info("Running took: %.4f sec   %.4f min" % (dt,dt/60.))
