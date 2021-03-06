#!/usr/bin/env python
#########################################################################################
#
# Warp template and atlas to a given volume (DTI, MT, etc.).
#
# ---------------------------------------------------------------------------------------
# Copyright (c) 2013 Polytechnique Montreal <www.neuro.polymtl.ca>
# Authors: Julien Cohen-Adad
# Modified: 2014-07-20
#
# About the license: see the file LICENSE.TXT
#########################################################################################

from __future__ import absolute_import

import sys, io, os, time

import spinalcordtoolbox.metadata

from spinalcordtoolbox.image import Image

from msct_parser import Parser
import sct_utils as sct

# get path of the script and the toolbox
path_script = os.path.dirname(__file__)
path_sct = os.path.dirname(path_script)


# DEFAULT PARAMETERS
class Param:
    # The constructor
    def __init__(self):
        self.debug = 0
        self.folder_out = 'label'  # name of output folder
        self.path_template = os.path.join(path_sct, "data", "PAM50")
        self.folder_template = 'template'
        self.folder_atlas = 'atlas'
        self.folder_spinal_levels = 'spinal_levels'
        self.file_info_label = 'info_label.txt'
        # self.warp_template = 1
        self.warp_atlas = 1
        self.warp_spinal_levels = 0
        self.list_labels_nn = ['_level.nii.gz', '_levels.nii.gz', '_csf.nii.gz', '_CSF.nii.gz', '_cord.nii.gz']  # list of files for which nn interpolation should be used. Default = linear.
        self.verbose = 1  # verbose
        self.path_qc = None


class WarpTemplate:
    def __init__(self, fname_src, fname_transfo, warp_atlas, warp_spinal_levels, folder_out, path_template, verbose):

        # Initialization
        self.fname_src = fname_src
        self.fname_transfo = fname_transfo
        self.warp_atlas = warp_atlas
        self.warp_spinal_levels = warp_spinal_levels
        self.folder_out = folder_out
        self.path_template = path_template
        self.folder_template = param.folder_template
        self.folder_atlas = param.folder_atlas
        self.folder_spinal_levels = param.folder_spinal_levels
        self.verbose = verbose

        # sct.printv(arguments)
        sct.printv('\nCheck parameters:')
        sct.printv('  Working directory ........ ' + os.getcwd())
        sct.printv('  Destination image ........ ' + self.fname_src)
        sct.printv('  Warping field ............ ' + self.fname_transfo)
        sct.printv('  Path template ............ ' + self.path_template)
        sct.printv('  Output folder ............ ' + self.folder_out + "\n")

        # create output folder
        if not os.path.exists(self.folder_out):
            os.makedirs(self.folder_out)

        # Warp template objects
        sct.printv('\nWARP TEMPLATE:', self.verbose)
        warp_label(self.path_template, self.folder_template, param.file_info_label, self.fname_src, self.fname_transfo, self.folder_out)

        # Warp atlas
        if self.warp_atlas == 1:
            sct.printv('\nWARP ATLAS OF WHITE MATTER TRACTS:', self.verbose)
            warp_label(self.path_template, self.folder_atlas, param.file_info_label, self.fname_src, self.fname_transfo, self.folder_out)

        # Warp spinal levels
        if self.warp_spinal_levels == 1:
            sct.printv('\nWARP SPINAL LEVELS:', self.verbose)
            warp_label(self.path_template, self.folder_spinal_levels, param.file_info_label, self.fname_src, self.fname_transfo, self.folder_out)


def warp_label(path_label, folder_label, file_label, fname_src, fname_transfo, path_out):
    """
    Warp label files according to info_label.txt file
    :param path_label:
    :param folder_label:
    :param file_label:
    :param fname_src:
    :param fname_transfo:
    :param path_out:
    :return:
    """
    # read label file and check if file exists
    sct.printv('\nRead label file...', param.verbose)
    try:
        template_label_ids, template_label_names, template_label_file, combined_labels_ids, combined_labels_names, combined_labels_id_groups, clusters_apriori = spinalcordtoolbox.metadata.read_label_file(os.path.join(path_label, folder_label), file_label)
    except Exception as error:
        sct.printv('\nWARNING: Cannot warp label ' + folder_label + ': ' + str(error), 1, 'warning')
        raise
    else:
        # create output folder
        if not os.path.exists(os.path.join(path_out, folder_label)):
            os.makedirs(os.path.join(path_out, folder_label))
        # Warp label
        for i in range(0, len(template_label_file)):
            fname_label = os.path.join(path_label, folder_label, template_label_file[i])
            # check if file exists
            # sct.check_file_exist(fname_label)
            # apply transfo
            sct.run('sct_apply_transfo -i ' + fname_label + ' -o ' + os.path.join(path_out, folder_label, template_label_file[i]) + ' -d ' + fname_src + ' -w ' + fname_transfo + ' -x ' + get_interp(template_label_file[i]), param.verbose)
        # Copy list.txt
        sct.copy(os.path.join(path_label, folder_label, param.file_info_label), os.path.join(path_out, folder_label))


# Get interpolation method
# ==========================================================================================
def get_interp(file_label):
    # default interp
    interp = 'linear'
    # NN interp
    if any(substring in file_label for substring in param.list_labels_nn):
        interp = 'nn'
    # output
    return interp


# PARSER
# ==========================================================================================
def get_parser():
    # Initialize default parameters
    param_default = Param()
    # Initialize parser
    parser = Parser(__file__)
    parser.usage.set_description('This function warps the template and all atlases to a given image (e.g. fMRI, DTI, MTR, etc.).')
    parser.add_option(name="-d",
                      type_value="file",
                      description="destination image the template will be warped into",
                      mandatory=True,
                      example="dwi_mean.nii.gz")
    parser.add_option(name="-w",
                      type_value="file",
                      description="warping field",
                      mandatory=True,
                      example="warp_template2dmri.nii.gz")
    parser.add_option(name="-a",
                      type_value="multiple_choice",
                      description="warp atlas of white matter",
                      mandatory=False,
                      default_value=str(param_default.warp_atlas),
                      example=['0', '1'])
    parser.add_option(name="-s",
                      type_value="multiple_choice",
                      description="warp spinal levels.",
                      mandatory=False,
                      default_value=str(param_default.warp_spinal_levels),
                      example=['0', '1'])
    parser.add_option(name="-ofolder",
                      type_value="folder_creation",
                      description="name of output folder.",
                      mandatory=False,
                      default_value=param_default.folder_out,
                      example="label")
    parser.add_option(name="-t",
                      type_value="folder",
                      description="Path to template.",
                      mandatory=False,
                      default_value=str(param_default.path_template))
    parser.add_option(name='-qc',
                      type_value='folder_creation',
                      description='The path where the quality control generated content will be saved',
                      default_value=param_default.path_qc)
    parser.add_option(name="-v",
                      type_value="multiple_choice",
                      description="""Verbose.""",
                      mandatory=False,
                      default_value='1',
                      example=['0', '1'])
    return parser


def generate_qc(fn_in, fn_wm, args, path_qc):
    """
    Generate a QC entry allowing to quickly review the warped template.
    """

    import spinalcordtoolbox.reports.qc as qc
    import spinalcordtoolbox.reports.slice as qcslice

    qc.add_entry(
     src=fn_in,
     process="sct_warp_template",
     args=args,
     path_qc=path_qc,
     plane='Axial',
     qcslice=qcslice.Axial([Image(fn_in), Image(fn_wm)]),
     qcslice_operations=[qc.QcImage.template],
     qcslice_layout=lambda x: x.mosaic(),
    )


def main(args=None):

    parser = get_parser()
    param = Param()

    arguments = parser.parse(sys.argv[1:])

    fname_src = arguments["-d"]
    fname_transfo = arguments["-w"]
    warp_atlas = int(arguments["-a"])
    warp_spinal_levels = int(arguments["-s"])
    folder_out = arguments['-ofolder']
    path_template = arguments['-t']
    verbose = int(arguments['-v'])
    path_qc = arguments.get("-qc", None)

    # call main function
    w = WarpTemplate(fname_src, fname_transfo, warp_atlas, warp_spinal_levels, folder_out, path_template, verbose)

    path_template = os.path.join(w.folder_out, w.folder_template)
    if set(spinalcordtoolbox.metadata.get_indiv_label_names(path_template)).issuperset(["white matter", "T2-weighted template", "gray matter"]):

        if path_qc is not None:
            fname_wm = os.path.join(w.folder_out, w.folder_template, spinalcordtoolbox.metadata.get_file_label(path_template, 'white matter'))
            generate_qc(fname_src, fname_wm, sys.argv[1:], os.path.abspath(path_qc))

        sct.display_viewer_syntax(
         [
          fname_src,
          spinalcordtoolbox.metadata.get_file_label(path_template, 'T2-weighted template', output="filewithpath"),
          spinalcordtoolbox.metadata.get_file_label(path_template, 'gray matter', output="filewithpath"),
          spinalcordtoolbox.metadata.get_file_label(path_template, 'white matter', output="filewithpath")
         ],
         colormaps=['gray', 'gray', 'red-yellow', 'blue-lightblue'],
         opacities=['1', '1', '0.5', '0.5'],
         minmax=['', '0,4000', '0.4,1', '0.4,1'],
         verbose=verbose,
        )
    else:
        if path_qc is not None:
            sct.printv("QC not generated since expected labels are missing from template", type="warning" )


if __name__ == "__main__":
    sct.init_sct()
    param = Param()
    main()
