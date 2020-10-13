# -*- coding: utf-8 -*-

# python standard library inputs
import os
import shutil as sh

# external inputs
import nibabel as nb
from nipype.interfaces.ants import N4BiasFieldCorrection
from nighres.registration import embedded_antsreg, apply_coordinate_mappings

# local inputs
from fmri_tools.cmap.clean_coordinate_mapping import clean_coordinate_mapping
from fmri_tools.cmap.expand_coordinate_mapping import expand_coordinate_mapping
from fmri_tools.skullstrip.skullstrip_refined import skullstrip_refined
from fmri_tools.registration.mask_ana import mask_ana
from fmri_tools.registration.mask_epi import mask_epi
from fmri_tools.registration.clean_ana import clean_ana


"""
EPI <-> EPI <-> ANA registration

The purpose of the following script is to compute the deformation field for the 
registration between antomy and EPI in native space via a registration between 
two EPIs and application of an already existing EPI <-> ANA deformation. The 
mask should be in ana space. Optionally, a second mask can be applied which must 
be in orig space. The script consists of the following steps:
    1. enhance brainmask if second mask is given (brain.finalsurf.mgz)
    2. set output folder structure
    3. n4 correction epi
    4. clean ana (remove ceiling and normalise)
    5. mask epi
    6. antsreg
    7. merge deformations
    8. clean deformations
    9. expand deformations
    10. apply deformations

The script needs an installation of freesurfer and ants.

created by Daniel Haenelt
Date created: 31-01-2020
Last modified: 13-10-2020
"""

# input data
file_mean_epi_source = "/data/pt_01880/Experiment3_Stripes/p3/colour/GE_EPI1/diagnosis/mean_data.nii"
file_mean_epi_target = ""
file_t1 = "/data/pt_01880/Experiment3_Stripes/p3/anatomy/S7_MP2RAGE_0p7_T1_Images_2.45_gnlcorr.nii"
file_mask1 = "/data/pt_01880/Experiment3_Stripes/p3/anatomy/skull/skullstrip_mask.nii" # skullstrip_mask
file_mask2 = "/data/pt_01880/Experiment3_Stripes/p3/anatomy/freesurfer/mri/brain.finalsurfs.mgz" # brain.finalsurfs
file_ana2epi = "/data/pt_01880/Experiment2_Rivalry/p3/deformation/odc/GE_EPI1/orig2epi.nii.gz"
file_epi2ana = "/data/pt_01880/Experiment2_Rivalry/p3/deformation/odc/GE_EPI1/epi2orig.nii.gz"
file_cmap = "" # ana -> epi cmap (optional)
path_output = "/data/pt_01880/Experiment3_Stripes/p3/deformation/colour/GE_EPI1"
clean_cmap = True
expand_cmap = True
cleanup = False

# parameters for epi skullstrip
niter_mask = 3
sigma_mask = 3

# parameters for syn 
run_rigid = True
rigid_iterations = 1000 
run_affine = False 
affine_iterations = 1000 
run_syn = True
coarse_iterations = 50 
medium_iterations = 150 
fine_iterations = 100 
cost_function = 'CrossCorrelation' 
interpolation = 'Linear' 

# do not edit below

# enhance brainmask
if file_mask2 is not None:
    file_mask1 = skullstrip_refined(file_mask1, file_mask2)

# set folder structure
path_temp = os.path.join(path_output,"temp")
path_epi_source = os.path.join(path_temp,"epi_source")
path_epi_target = os.path.join(path_temp,"epi_target")
path_t1_source = os.path.join(path_temp,"t1_source")
path_t1_target = os.path.join(path_temp,"t1_target")
path_syn = os.path.join(path_temp,"syn")

if not os.path.exists(path_output):
    os.makedirs(path_output)

if not os.path.exists(path_temp):
    os.makedirs(path_temp)

if not os.path.exists(path_epi_source):
    os.makedirs(path_epi_source)

if not os.path.exists(path_epi_target):
    os.makedirs(path_epi_target)

if not os.path.exists(path_t1_source):
    os.makedirs(path_t1_source)
    
if not os.path.exists(path_t1_target):
    os.makedirs(path_t1_target)

if not os.path.exists(path_syn):
    os.makedirs(path_syn)

path_t1 = [path_t1_source, path_t1_target]
path_epi = [path_epi_source, path_epi_target]

# copy input files
sh.copyfile(file_mean_epi_source, os.path.join(path_epi_source,"epi.nii"))
sh.copyfile(file_mean_epi_target, os.path.join(path_epi_target,"epi.nii"))
sh.copyfile(file_t1, os.path.join(path_t1_source,"T1.nii"))
sh.copyfile(file_mask1, os.path.join(path_t1_source,"mask.nii"))
sh.copyfile(file_t1, os.path.join(path_t1_target,"T1.nii"))
sh.copyfile(file_mask1, os.path.join(path_t1_target,"mask.nii"))

# bias field correction to epi
for i in range(len(path_epi)):
    n4 = N4BiasFieldCorrection()
    n4.inputs.dimension = 3
    n4.inputs.input_image = os.path.join(path_epi[i],"epi.nii")
    n4.inputs.bias_image = os.path.join(path_epi[i],'n4bias.nii')
    n4.inputs.output_image = os.path.join(path_epi[i],"bepi.nii")
    n4.run()

# clean ana
for i in range(len(path_t1)):
    clean_ana(os.path.join(path_t1[i],"T1.nii"), 1000.0, 4095.0, overwrite=True)

# mask t1 and epi
for i in range(len(path_t1)):
    mask_ana(os.path.join(path_t1[i],"T1.nii"),
             os.path.join(path_t1[i],"mask.nii"), 
             background_bright=False)

for i in range(len(path_epi)):
    mask_epi(os.path.join(path_epi[i],"bepi.nii"), 
             os.path.join(path_t1[i],"pT1.nii"), 
             os.path.join(path_t1[i],"mask.nii"), 
             niter_mask, sigma_mask, file_cmap)

# syn
embedded_antsreg(os.path.join(path_epi_target,"pbepi.nii"), # source image
                 os.path.join(path_epi_source,"pbepi.nii"), # target image 
                 run_rigid, # whether or not to run a rigid registration first 
                 rigid_iterations, # number of iterations in the rigid step
                 run_affine, # whether or not to run an affine registration first
                 affine_iterations, # number of iterations in the affine step
                 run_syn, # whether or not to run a SyN registration
                 coarse_iterations, # number of iterations at the coarse level
                 medium_iterations, # number of iterations at the medium level
                 fine_iterations, # number of iterations at the fine level
                 cost_function, # CrossCorrelation or MutualInformation
                 interpolation, # interpolation for registration result (NeareastNeighbor or Linear)
                 convergence = 1e-6, # threshold for convergence (can make algorithm very slow)
                 ignore_affine = False, # ignore the affine matrix information extracted from the image header 
                 ignore_header = False, # ignore the orientation information and affine matrix information extracted from the image header
                 save_data = True, # save output data to file
                 overwrite = True, # overwrite existing results 
                 output_dir = path_syn, # output directory
                 file_name = "syn", # output basename
                 )

# merge deformations
# ana -> epi
apply_coordinate_mappings(file_ana2epi, # input 
                          os.path.join(path_syn,"syn_ants-map.nii.gz"), # cmap
                          interpolation = "linear", # nearest or linear
                          padding = "zero", # closest, zero or max
                          save_data = True, # save output data to file (boolean)
                          overwrite = True, # overwrite existing results (boolean)
                          output_dir = path_output, # output directory
                          file_name = "ana2epi" # base name with file extension for output
                          )

# epi -> ana
apply_coordinate_mappings(os.path.join(path_syn,"syn_ants-invmap.nii.gz"), # input
                          file_epi2ana, # cmap
                          interpolation = "linear", # nearest or linear
                          padding = "zero", # closest, zero or max
                          save_data = True, # save output data to file (boolean)
                          overwrite = True, # overwrite existing results (boolean)
                          output_dir = path_output, # output directory
                          file_name = "epi2ana" # base name with file extension for output
                          )

# rename final deformations
os.rename(os.path.join(path_output,"ana2epi_def-img.nii.gz"),
          os.path.join(path_output,"ana2epi.nii.gz"))
os.rename(os.path.join(path_output,"epi2ana_def-img.nii.gz"),
          os.path.join(path_output,"epi2ana.nii.gz"))

# clean deformation
if clean_cmap:
    epi2ana_cleaned = clean_coordinate_mapping(os.path.join(path_output,"ana2epi.nii.gz"), 
                                               os.path.join(path_output,"epi2ana.nii.gz"), 
                                               overwrite_file=True,
                                               save_mask=False)
    
    # write mask
    nb.save(epi2ana_cleaned["mask"], os.path.join(path_output,"epi2ana_mask.nii.gz"))

# expand deformation
if expand_cmap:
    _ = expand_coordinate_mapping(os.path.join(path_output, "ana2epi.nii.gz"),
                                  path_output, 
                                  name_output="ana2epi", 
                                  write_output=True)
    
    _ = expand_coordinate_mapping(os.path.join(path_output, "epi2ana.nii.gz"),
                                  path_output, 
                                  name_output="epi2ana", 
                                  write_output=True)

# apply deformation
# ana -> epi
apply_coordinate_mappings(file_t1, # input 
                          os.path.join(path_output,"ana2epi.nii.gz"), # cmap
                          interpolation = "linear", # nearest or linear
                          padding = "zero", # closest, zero or max
                          save_data = True, # save output data to file (boolean)
                          overwrite = True, # overwrite existing results (boolean)
                          output_dir = path_output, # output directory
                          file_name = "ana2epi_example" # base name with file extension for output
                          )

# epi -> ana
apply_coordinate_mappings(file_mean_epi_source, # input 
                          os.path.join(path_output,"epi2ana.nii.gz"), # cmap
                          interpolation = "linear", # nearest or linear
                          padding = "zero", # closest, zero or max
                          save_data = True, # save output data to file (boolean)
                          overwrite = True, # overwrite existing results (boolean)
                          output_dir = path_output, # output directory
                          file_name = "epi2ana_example" # base name with file extension for output
                          )

# rename final deformation examples
os.rename(os.path.join(path_output,"ana2epi_example_def-img.nii.gz"),
          os.path.join(path_output,"ana2epi_example.nii.gz"))
os.rename(os.path.join(path_output,"epi2ana_example_def-img.nii.gz"),
          os.path.join(path_output,"epi2ana_example.nii.gz"))

# clean intermediate files
if cleanup:
    sh.rmtree(path_temp, ignore_errors=True)
