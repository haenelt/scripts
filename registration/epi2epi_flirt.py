"""
EPI <-> EPI

The purpose of the following script is to compute the deformation field for the registration 
between different epi time series. The script consists of the following steps:
    1. set output folder structure
    2. n4 correction epi
    3. clean ana (remove ceiling and normalise)
    4. mask epi
    5. flirt
    6. get deformation
    7. apply deformations

At the moment, we perform flirt on the unpeeled bias corrected source and target images.

Before running the script, login to queen via ssh and set the freesurfer and ANTS environments by 
calling FREESURFER and ANTSENV in the terminal.

created by Daniel Haenelt
Date created: 13-01-2020
Last modified: 13-01-2020
"""
import os
import shutil as sh
from nipype.interfaces.ants import N4BiasFieldCorrection
from nipype.interfaces.fsl import FLIRT
from nipype.interfaces.fsl import ConvertXFM
from nipype.interfaces.fsl.preprocess import ApplyXFM
from nighres.registration import apply_coordinate_mappings
from lib.registration.mask_ana import mask_ana
from lib.registration.mask_epi import mask_epi
from lib.registration.clean_ana import clean_ana
from lib.cmap.generate_coordinate_mapping import generate_coordinate_mapping

# input data
file_mean_epi_source = "/data/pt_01880/Experiment1_ODC/p3/odc/SE_EPI1/diagnosis/mean_data.nii"
file_mean_epi_target = "/data/pt_01880/Experiment1_ODC/p3/odc/GE_EPI2/diagnosis/mean_data.nii"
file_t1 = "/data/pt_01880/Experiment1_ODC/p3/anatomy/S22_MP2RAGE_0p7_T1_Images_2.45.nii"
file_mask = "/data/pt_01880/Experiment1_ODC/p3/anatomy/skull/skullstrip_mask.nii"
path_output = "/data/pt_01880/odc_temp/deformation/test"
cleanup = False

# parameters for epi skullstrip
niter_mask = 3
sigma_mask = 3

""" do not edit below """

"""
set folder structure
"""
path_temp = os.path.join(path_output,"temp")
path_epi_source = os.path.join(path_temp,"epi_source")
path_epi_target = os.path.join(path_temp,"epi_target")
path_t1 = os.path.join(path_temp,"t1")
path_flirt = os.path.join(path_temp,"flirt")

if not os.path.exists(path_output):
    os.makedirs(path_output)

if not os.path.exists(path_temp):
    os.makedirs(path_temp)

if not os.path.exists(path_epi_source):
    os.makedirs(path_epi_source)

if not os.path.exists(path_epi_target):
    os.makedirs(path_epi_target)

if not os.path.exists(path_t1):
    os.makedirs(path_t1)

if not os.path.exists(path_flirt):
    os.makedirs(path_flirt)

# copy input files
sh.copyfile(file_mean_epi_source, os.path.join(path_epi_source,"epi.nii"))
sh.copyfile(file_mean_epi_target, os.path.join(path_epi_target,"epi.nii"))
sh.copyfile(file_t1, os.path.join(path_t1,"T1.nii"))
sh.copyfile(file_mask, os.path.join(path_t1,"mask.nii"))

"""
bias field correction to epi
"""
path = [path_epi_source, path_epi_target]
for i in range(len(path)):
    n4 = N4BiasFieldCorrection()
    n4.inputs.dimension = 3
    n4.inputs.input_image = os.path.join(path[i],"epi.nii")
    n4.inputs.bias_image = os.path.join(path[i],'n4bias.nii')
    n4.inputs.output_image = os.path.join(path[i],"bepi.nii")
    n4.run()

"""
clean ana
"""
clean_ana(os.path.join(path_t1,"T1.nii"), 1000.0, 4095.0, overwrite=True)

"""
mask t1 and epi
"""
mask_ana(os.path.join(path_t1,"T1.nii"),os.path.join(path_t1,"mask.nii"))
for i in range(len(path)):
    mask_epi(os.path.join(path[i],"bepi.nii"), 
             os.path.join(path_t1,"pT1.nii"), 
             os.path.join(path_t1,"mask.nii"), 
             niter_mask, sigma_mask)

"""
flirt
"""
os.chdir(path_flirt)
flirt = FLIRT()
flirt.inputs.cost_func = "corratio"
flirt.inputs.dof = 6
flirt.inputs.interp = "trilinear" # trilinear, nearestneighbour, sinc or spline
flirt.inputs.in_file = os.path.join(path_epi_target,"bepi.nii")
flirt.inputs.reference = os.path.join(path_epi_source,"bepi.nii")
flirt.inputs.output_type = "NIFTI"
flirt.inputs.out_file = os.path.join(path_flirt, "flirt.nii")
flirt.inputs.out_matrix_file = os.path.join(path_flirt,"flirt_matrix.mat")
flirt.run()

"""
invert matrix
"""
invt = ConvertXFM()
invt.inputs.in_file = os.path.join(path_flirt, "flirt_matrix.mat")
invt.inputs.invert_xfm = True
invt.inputs.out_file = os.path.join(path_flirt, "flirt_inv_matrix.mat")
invt.run()

"""
get cmap
"""
generate_coordinate_mapping(os.path.join(path_epi_target, "bepi.nii"), 
                            pad = 0, 
                            path_output = path_flirt, 
                            suffix = "target", 
                            time = False, 
                            write_output = True)

generate_coordinate_mapping(os.path.join(path_epi_source, "bepi.nii"), 
                            pad = 0, 
                            path_output = path_flirt, 
                            suffix = "source", 
                            time = False, 
                            write_output = True)

"""
apply flirt to cmap
"""
applyxfm = ApplyXFM()
applyxfm.inputs.in_file = os.path.join(path_flirt,"cmap_target.nii")
applyxfm.inputs.reference = os.path.join(path_epi_source,"bepi.nii")
applyxfm.inputs.in_matrix_file = os.path.join(path_flirt, "flirt_matrix.mat")
applyxfm.inputs.interp = "trilinear"
applyxfm.inputs.padding_size = 0
applyxfm.inputs.output_type = "NIFTI_GZ"
applyxfm.inputs.out_file = os.path.join(path_output, "target2source.nii.gz")
applyxfm.inputs.apply_xfm = True
applyxfm.run() 

applyxfm = ApplyXFM()
applyxfm.inputs.in_file = os.path.join(path_flirt,"cmap_source.nii")
applyxfm.inputs.reference = os.path.join(path_epi_target,"bepi.nii")
applyxfm.inputs.in_matrix_file = os.path.join(path_flirt, "flirt_inv_matrix.mat")
applyxfm.inputs.interp = "trilinear"
applyxfm.inputs.padding_size = 0
applyxfm.inputs.output_type = "NIFTI_GZ"
applyxfm.inputs.out_file = os.path.join(path_output, "source2target.nii.gz")
applyxfm.inputs.apply_xfm = True
applyxfm.run() 

"""
apply deformation
"""
# orig -> epi
apply_coordinate_mappings(file_mean_epi_source, # input 
                          os.path.join(path_output,"source2target.nii.gz"), # cmap
                          interpolation = "linear", # nearest or linear
                          padding = "zero", # closest, zero or max
                          save_data = True, # save output data to file (boolean)
                          overwrite = True, # overwrite existing results (boolean)
                          output_dir = path_output, # output directory
                          file_name = "source2target_example" # base name with file extension for output
                          )

# epi -> orig
apply_coordinate_mappings(file_mean_epi_target, # input 
                          os.path.join(path_output,"target2source.nii.gz"), # cmap
                          interpolation = "linear", # nearest or linear
                          padding = "zero", # closest, zero or max
                          save_data = True, # save output data to file (boolean)
                          overwrite = True, # overwrite existing results (boolean)
                          output_dir = path_output, # output directory
                          file_name = "target2source_example" # base name with file extension for output
                          )

# rename final deformation examples
os.rename(os.path.join(path_output,"source2target_example_def-img.nii.gz"),
          os.path.join(path_output,"source2target_example.nii.gz"))
os.rename(os.path.join(path_output,"target2source_example_def-img.nii.gz"),
          os.path.join(path_output,"target2source_example.nii.gz"))

# clean intermediate files
if cleanup:
    sh.rmtree(path_temp, ignore_errors=True)