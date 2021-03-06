# Using `2pt_validation` or "How to simulate (and analyze) a catalog as big as LSST's 10 year data in one afternoon (a.k.a. filling up your disk space in a few hours)"

Authors: D. Alonso, J. Sanchez, A. Slosar

This document intends to guide the user in the process of generating mock catalogs and analyzing their 2-point statistics using the scripts provided in this repository and the resources at NERSC (mostly focusing on Cori).

Requirements:

* [CoLoRe](https://github.com/damonge/colore)

* [SACC](https://github.com/LSSTDESC/sacc)

* [fastcat](https://github.com/slosar/fastcat)

* [NaMaster](https://github.com/damonge/namaster)

Optional requirements (only necessary for cosmological parameter retrieval):

* [CCL](https://github.com/LSSTDESC/CCL)

* [LSSLike](https://github.com/LSSTDESC/LSSLike)

Each one of the required pieces of software has its own installation procedure. If you find any bugs or problems please contact the authors.

## Step 1) Generation of the cosmological mocks using CoLoRe

[CoLoRe](https://github.com/damonge/colore) is a highly parallel software capable of generating fast cosmological mocks using three different approaches: lognormal, 1-loop LPT, and 2-loop LPT. These mocks can include different properly correlated tracers with their corresponding bias. CoLoRe is also able to generate the corresponding convergence and shear maps, intensity mapping and ISW effect. All you have to do is to input the proper `param.cfg` file and run `./CoLoRe param.cfg`.

In our case, we restrict our analysis to a single galaxy population with the fiducial LSST N(z) and b(z). We generate 100 realizations of a simulation with 3072^3 pixels from redshift 0.001 to 2.5 using a Planck-2015 fiducial input cosmology. We select the 2-loop 2LPT method with no smoothing and generate lens planes from z=0 to z=2.4 at redshift intervals of 0.2.

To run this part, assuming that you have CoLoRe properly installed and running at Cori, you have to connect to Cori and in a terminal follow these steps:

* Go to the folder `drive_CoLoRe`.
* Open `launch_run_colore.sh` with your favorite text editor.
* Modify line 1 and select the range of the for loop in which you want to run the simulations. By default is set from 17 to 88 (so in total you are trying to submit 71 jobs each of them requiring 32 nodes) but you will need to modify this in order to be able to allocate it in the production queue. See the [queuing policy at Cori](http://www.nersc.gov/users/computational-systems/cori/running-jobs/queues-and-policies/) to check how many jobs you can submit at once (in normal conditions you should not be able to submit more than 50). 
* Edit line 7 to modify the output path. We recommend using your $SCRATCH space at NERSC since these simulations are quite big.
* Edit line 14 to include the path to the input power-spectrum that you want to use. The format is the same as CAMB outputs, i.e., an ASCII file with two columns, the first one includes k in units of h/Mpc and the second P(k) in units of (h/Mpc)^3.
* Edit lines 75 and 79 to include the path to the input N(z) and b(z) files that you want to use. The formats are similar in both cases. You need two ASCII files with two columns, in the first one you include z and in the second one N (or b in the case of the bias input file) at that redshift.
* Type `/bin/bash launch_run_colore.sh`.

This bash script will create the necessary parameter files for CoLoRe and submit the jobs to the queue. Each one of these simulations takes less than 15 minutes to finish. However, depending on the status of the queue the jobs might be pending for a while before the start running. You can change the priority by uncommenting line 96 of `launch_run_colore.sh` (just leave on #). This process can also be done in Edison but due to its smaller memory per node you might need to change considerably `launch_run_colore.sh` to be able to successfully run the simulations using Edison.

Expect each realization to need ~135 GB.

_This process will change once we update the script `vc.py` in the folder `drive_CoLoRe`_.

The outputs from this step can be found at `/global/cscratch1/sd/jsanch87/CoLoRe_LN100/Mock*.h5` (89 realizations x 32 files/each)

## Step 2) Generation of the catalogs

Once we have the cosmological mocks generated by CoLoRe, we want to add several observational effects. In order to do so, we use [fastcat](https://github.com/slosar/fastcat). This program allows the user to include several flavors of depth variations/footprints, photometric redshifts and stellar contamination among others. It is heavily parallelized and able to write the outputs into a single file (using h5py-parallel) or different chunks (recommended). In our case, we restrict our analysis to Gaussian photo-z with a width of 0.05(1+z), and use the depth variations implemented by Humna Awan. We do not include stars in this iteration although we are planning to do so in the near future.

To generate the catalogs you have to do the following:

* Go to the directory `fastcat_CoLore`.
* Open `run_all.sh` in any text editor.
* Go to line 11 and change the relevant paths and options to get your desired output catalog.
* The option `--params_file` selects the input CoLoRe parameter file to generate the realization that you want to pass through `fastcat`.
* The option `--opath` selects the ouput path for your `fastcat` catalog. Each realization needs ~19 GB.
* The option `--pz_type` selects the flavor of photometric redshift that you want to use. It can be: none,gauss, twopop, hiddenvar, franzona,sed.
* The option `--pz_sigma` selects the width of the Gaussian in case of choosing a Gaussian photo-z.
* The option `--oextra` adds extra information to the output directory (you should put the name or number of the realization that you are considering).
* The option `--mpi` enables MPI parallel processing.
* Once you modified `run_all.sh` just do `sbatch run_all.sh` to submit your job.

As you can see, what `run_all.sh` does is just to submit the slurm job by calling the python script `mkcat.py` which is the interface with fastcat.

The outputs from this step can be found at `/global/cscratch1/sd/jsanch87/CoLoRe_LN100/fastcat_outputs/170522+GaussPZ_0.05+hpix_nodither_0.1+catalog*/fastcat_catalog0.*` (89 realizations x 32 files)

## Step 3) Computing the power-spectra using NaMaster

Now that you have your source catalogs you can try to analyze their 2-point statistics. In order to do so, we decided to use [NaMaster](https://github.com/damonge/namaster). `NaMaster` is an implementation of the `Master` algorithm by D. Alonso using unbiased pseudo-Cl estimation and able to perform mode projection. We use `NaMaster` through `namaster_interface.py`. This program reads each one of our `fastcat` catalogs and generates `HEALpix` maps using the binning in redshift specified by an ASCII file that also includes the maximum `l` at which we want to calculate the power-spectra. The program outputs a [SACC](https://github.com/LSSTDESC/SACC) file containing the results for the different tracers and information about the binning, N(z), etc.

To compute the power-spectra you have to follow these steps:

* Go to the directory `namaster_fastcat`.
* Open the file `run_all.sh`.
* Modify the relevant paths and options for `namaster_interface.py`. 
* The option `--input-file` specifies the name of the input fastcat catalog. If there are multiple parts you only have to specify the root (usually the full path to the file called `fastcat_catalog0.h5`).
* The option `--output-file` specifies the output name.
* The option `--nz-bins-file` specifies the name of the file containing the binning information.
* The option `--templates` selects the templates in which you want to perform mode projection.
* The option `--delta-ell` selects the binning in `l`.
* The option `--nside` specifies the resolution (in terms of the HEALpix Nside parameter) of the maps. If you are generating simulations with `n_grid=3072`, 2048 is an adecquate value.
* The option `--mpi` enables parallel MPI processing.
* Once you have modified `run_all.sh` to your liking you just have to type: `sbatch run_all.sh` to submit your job.

The outputs from this step can be found at `/global/cscratch1/sd/jsanch87/2pt_namaster_output/catalog*.sacc`

## Step 4) Compute the theoretical prediction (Optional)

If you want you can compute the theoretical prediction for the sample SACC file just typing `python mk_theory.py` in the directory `namaster_fastcat`. You can modify the relevant paths in the file if you want to calculate the theoretical prediction for the power-spectra for other cases.

To account for the different interpolation/gridding operations that take place within CoLoRe, the P(k) used to compute the theoretical predictions should be smoothed with a Gaussian radius given by:
  R_smooth = (R_s^2 + (0.5*a_grid)^2)^1/2
where R_s is the smoothing scale parmeter passed to CoLoRe and a_grid is the grid size (this is reported by CoLoRe, and can be computed as 2*chi(z_max)*(1+2/Ngrid)/Ngrid, where Ngrid is the number of grid cells per dimension and chi(z) is the radial comoving distance to redshift z.


### Final notes and disclaimer

We recommend to use the anaconda distribution in Cori and install the relevant python packages using the option `python setup.py install --user` since this makes the installation/update process easier. Please, post issues or send your questions or comments to any of the authors.


