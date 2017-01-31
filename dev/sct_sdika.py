#!/usr/bin/env python
#########################################################################################
#
# Pipeline for the Sdika Project
#           - Import data from /data_shared/sct_testing/large/
#           - Unification of orientation, name convention
#           - Transfert data to ferguson to be process
#           - Compute the metrics / Evaluate the performance of Sdika Algorithm
#
# ---------------------------------------------------------------------------------------
# Authors: Charley
# Modified: 2017-01-25
#
#########################################################################################


# ****************************      IMPORT      *****************************************  
# Utils Imports
import pickle
import os
import nibabel as nib #### A changer en utilisant Image
import shutil
import numpy as np
from math import sqrt
from collections import Counter
import random
import json
import argparse
import seaborn as sns
import matplotlib.pyplot as plt
import itertools

# SCT Imports
from msct_image import Image
import sct_utils as sct
# ***************************************************************************************


TODO_STRING = """\n
            - Export dataset info into a excel file
            - Clean step 3
            - Set code comptatible with CNN approach
            - ...
            \n
            """


# ****************************      UTILS FUNCTIONS      ********************************

def create_folders_local(folder2create_lst):
    """
    
      Create folders if not exist
    
          Inputs:
              - folder2create_lst [list of string]: list of folder paths to create
          Outputs:
              -
    
    """           
    
    for folder2create in folder2create_lst:
        if not os.path.exists(folder2create):
            os.makedirs(folder2create)

# ***************************************************************************************



# ****************************      STEP 0 FUNCTIONS      *******************************

def find_img_testing(path_large, contrast, path_local):
    """
    
      Explore a database folder (path_large)...
      ...and extract path to images for a given contrast (contrast)
    
          Inputs:
              - path_large [string]: path to database
              - contrast [string]: contrast of interest ('t2', 't1', 't2s')
          Outputs:
              - path_img [list of string]: list of image path
              - path_seg [list of string]: list of segmentation path
    
    """   

    center_lst, pathology_lst, path_img, path_seg = [], [], [], []
    for subj_fold in os.listdir(path_large):
        path_subj_fold = path_large + subj_fold + '/'

        if os.path.isdir(path_subj_fold):
            contrast_fold_lst = [contrast_fold for contrast_fold in os.listdir(path_subj_fold) 
                                                    if os.path.isdir(path_subj_fold+contrast_fold+'/')]
            contrast_fold_lst_oI = [contrast_fold for contrast_fold in contrast_fold_lst 
                                                    if contrast_fold==contrast or contrast_fold.startswith(contrast+'_')]
            
            # If this subject folder contains a subfolder related to the contrast of interest
            if len(contrast_fold_lst_oI):

                # Depending on the number of folder of interest:
                if len(contrast_fold_lst_oI)>1:
                    # In our case, we prefer axial images when available
                    ax_candidates = [tt for tt in contrast_fold_lst_oI if 'ax' in tt]
                    if len(ax_candidates):
                        contrast_fold_oI = ax_candidates[0]
                    else:
                        contrast_fold_oI = contrast_fold_lst_oI[0]                                               
                else:
                    contrast_fold_oI = contrast_fold_lst_oI[0]

                # For each subject and for each contrast, we want to pick only one image
                path_contrast_fold = path_subj_fold+contrast_fold_oI+'/'

                # If segmentation_description.json is available
                if os.path.exists(path_contrast_fold+'segmentation_description.json'):

                    with open(path_contrast_fold+'segmentation_description.json') as data_file:    
                        data_seg_description = json.load(data_file)
                        data_file.close()

                    # If manual segmentation of the cord is available
                    if len(data_seg_description['cord']):

                        # Extract data information from the dataset_description.json
                        with open(path_subj_fold+'dataset_description.json') as data_file:    
                            data_description = json.load(data_file)
                            data_file.close()

                        path_img_cur = path_contrast_fold+contrast_fold_oI+'.nii.gz'
                        path_seg_cur = path_contrast_fold+contrast_fold_oI+'_seg_manual.nii.gz'
                        if os.path.exists(path_img_cur) and os.path.exists(path_seg_cur):
                            path_img.append(path_img_cur)
                            path_seg.append(path_seg_cur)
                            center_lst.append(data_description['Center'])
                            pathology_lst.append(data_description['Pathology'])
                        else:
                            print '\nWARNING: file lacks: ' + path_contrast_fold + '\n'


    img_patho_lstoflst = [[i.split('/')[-3].split('.nii.gz')[0].split('_t2')[0], p] for i,p in zip(path_img,pathology_lst)]
    img_patho_dct = {}
    for ii_pp in img_patho_lstoflst:
        if not ii_pp[1] in img_patho_dct:
            img_patho_dct[ii_pp[1]] = []
        img_patho_dct[ii_pp[1]].append(ii_pp[0])
    if '' in img_patho_dct:
        for ii in img_patho_dct['']:
            img_patho_dct['HC'].append(ii)
        del img_patho_dct['']

    fname_pkl_out = path_local + 'patho_dct_' + contrast + '.pkl'
    pickle.dump(img_patho_dct, open(fname_pkl_out, "wb"))

    # Remove duplicates
    center_lst = list(set(center_lst))
    center_lst = [center for center in center_lst if center != ""]
    # Remove HC and non specified pathologies
    pathology_lst = [patho for patho in pathology_lst if patho != "" and patho != "HC"]
    pathology_dct = {x:pathology_lst.count(x) for x in pathology_lst}

    print '\n\n***************Contrast of Interest: ' + contrast + ' ***************'
    print '# of Subjects: ' + str(len(path_img))
    print '# of Centers: ' + str(len(center_lst))
    print 'Centers: ' + ', '.join(center_lst)
    print 'Pathologies:'
    print pathology_dct
    print '\n'

    return path_img, path_seg

def transform_nii_img(img_lst, path_out):
    """
    
      List .nii images which need to be converted to .img format
      + set same orientation RPI
      + set same value format (int16)
    
          Inputs:
              - img_lst [list of string]: list of path to image to transform
              - path_out [string]: path to folder where to save transformed images
          Outputs:
              - path_img2convert [list of string]: list of image paths to convert
    
    """   

    path_img2convert = []
    for img_path in img_lst:
        path_cur = img_path
        path_cur_out = path_out + '_'.join(img_path.split('/')[5:7]) + '.nii.gz'
        if not os.path.isfile(path_cur_out):
            shutil.copyfile(path_cur, path_cur_out)
            sct.run('sct_image -i ' + path_cur_out + ' -type int16 -o ' + path_cur_out)
            sct.run('sct_image -i ' + path_cur_out + ' -setorient RPI -o ' + path_cur_out)
            # os.system('sct_image -i ' + path_cur_out + ' -type int16 -o ' + path_cur_out)
            # os.system('sct_image -i ' + path_cur_out + ' -setorient RPI -o ' + path_cur_out)
        path_img2convert.append(path_cur_out)

    return path_img2convert

def transform_nii_seg(seg_lst, path_out, path_gold):
    """
    
      List .nii segmentations which need to be converted to .img format
      + set same orientation RPI
      + set same value format (int16)
      + set same header than related image
      + extract centerline from '*_seg_manual.nii.gz' to create gold standard
    
          Inputs:
              - seg_lst [list of string]: list of path to segmentation to transform
              - path_out [string]: path to folder where to save transformed segmentations
              - path_gold [string]: path to folder where to save gold standard centerline
          Outputs:
              - path_segs2convert [list of string]: list of segmentation paths to convert
    
    """

    path_seg2convert = []
    for seg_path in seg_lst:
        path_cur = seg_path
        path_cur_out = path_out + '_'.join(seg_path.split('/')[5:7]) + '_seg.nii.gz'
        if not os.path.isfile(path_cur_out):
            shutil.copyfile(path_cur, path_cur_out)
            os.system('sct_image -i ' + path_cur_out + ' -setorient RPI -o ' + path_cur_out)

        path_cur_ctr = path_cur_out.split('.')[0] + '_centerline.nii.gz'
        if not os.path.isfile(path_cur_ctr):
            os.chdir(path_out)
            os.system('sct_process_segmentation -i ' + path_cur_out + ' -p centerline -ofolder ' + path_out)
            os.system('sct_image -i ' + path_cur_ctr + ' -type int16')
            path_input_header = path_cur_out.split('_seg')[0] + '.nii.gz'
            os.system('sct_image -i ' + path_input_header + ' -copy-header ' + path_cur_ctr)

        path_cur_gold = path_gold + '_'.join(seg_path.split('/')[5:7]) + '_centerline_gold.nii.gz'
        if not os.path.isfile(path_cur_gold) and os.path.isfile(path_cur_ctr):
            shutil.copyfile(path_cur_ctr, path_cur_gold)

        if os.path.isfile(path_cur_out):
            path_seg2convert.append(path_cur_out)
        if os.path.isfile(path_cur_ctr):
            path_seg2convert.append(path_cur_ctr)

    return path_seg2convert

def convert_nii2img(path_nii2convert, path_out):
    """
    
      Convert .nii images to .img format
    
          Inputs:
              - path_nii2convert [list of string]: list of path to images to convert
              - path_out [string]: path to folder where to save converted images
          Outputs:
              - fname_img [list of string]: list of converted images (.img format) paths
    
    """ 

    fname_img = []
    for img in path_nii2convert:
        path_cur = img
        path_cur_out = path_out + img.split('.')[0].split('/')[-1] + '.img'
        if not img.split('.')[0].split('/')[-1].endswith('_seg') and not img.split('.')[0].split('/')[-1].endswith('_seg_centerline'):
            fname_img.append(img.split('.')[0].split('/')[-1] + '.img')
        if not os.path.isfile(path_cur_out):
            os.system('sct_convert -i ' + path_cur + ' -o ' + path_cur_out)

    return fname_img

def prepare_dataset(path_local, constrast_lst, path_sct_testing_large):
    """
    
      MAIN FUNCTION OF STEP 0
      Create working subfolders
      + explore database and find images of interest
      + transform images (same orientation, value format...)
      + convert images to .img format
      + save image fname in 'dataset_lst_' + cc + '.pkl'
    
          Inputs:
              - path_local [string]: working folder
              - constrast_lst [list of string]: list of contrast we are interested in
              - path_sct_testing_large [path]: path to database
          Outputs:
              - 
    
    """

    for cc in constrast_lst:
    
        path_local_gold = path_local + 'gold_' + cc + '/'
        path_local_input_nii = path_local + 'input_nii_' + cc + '/'
        path_local_input_img = path_local + 'input_img_' + cc + '/'
        folder2create_lst = [path_local_input_nii, path_local_input_img, path_local_gold]
        create_folders_local(folder2create_lst)

        path_fname_img, path_fname_seg = find_img_testing(path_sct_testing_large, cc, path_local)

        path_img2convert = transform_nii_img(path_fname_img, path_local_input_nii)
        path_seg2convert = transform_nii_seg(path_fname_seg, path_local_input_nii, path_local_gold)
        path_imgseg2convert = path_img2convert + path_seg2convert
        fname_img_lst = convert_nii2img(path_imgseg2convert, path_local_input_img)

        pickle.dump(fname_img_lst, open(path_local + 'dataset_lst_' + cc + '.pkl', 'wb'))

# ******************************************************************************************



# ****************************      STEP 1 FUNCTIONS      *******************************
def prepare_train(path_local, path_outdoor, cc, nb_img):

    print '\nExperiment: '
    print '... contrast: ' + cc
    print '... nb image used for training: ' + str(nb_img) + '\n'

    path_outdoor_cur = path_outdoor + 'input_img_' + cc + '/'

    path_local_res_img = path_local + 'output_img_' + cc + '_'+ str(nb_img) + '/'
    path_local_res_nii = path_local + 'output_nii_' + cc + '_'+ str(nb_img) + '/'
    path_local_res_pkl = path_local + 'output_pkl_' + cc + '_'+ str(nb_img) + '/'
    path_local_train = path_local + 'input_train_' + cc + '_'+ str(nb_img) + '/'
    folder2create_lst = [path_local_train, path_local_res_img, path_local_res_nii, path_local_res_pkl]

    with open(path_local + 'dataset_lst_' + cc + '.pkl') as outfile:    
        fname_subj_lst = pickle.load(outfile)
        outfile.close()

    nb_sub_train = int(float(len(fname_subj_lst))/(50*nb_img))+1
    path_folder_sub_train = []
    for i in range(nb_sub_train):
        path2create = path_local_train + str(i).zfill(3) + '/'
        path_folder_sub_train.append(path2create)
        folder2create_lst.append(path2create)

    create_folders_local(folder2create_lst)

    if os.listdir(path2create) == []: 
        path_fname_img_rdn = [f.split('.')[0] for f in fname_subj_lst]    
        random.shuffle(path_fname_img_rdn)
        tuple_fname_multi = []
        for j in range(0, len(fname_subj_lst), nb_img):
            s = path_fname_img_rdn[j:j+nb_img]
            if len(path_fname_img_rdn[j:j+nb_img])==nb_img:
                tuple_fname_multi.append(s)

        for i, tt in enumerate(tuple_fname_multi):
            stg, stg_seg = '', ''
            for tt_tt in tt:
                stg += path_outdoor_cur + tt_tt + '\n'
                stg_seg += path_outdoor_cur + tt_tt + '_seg' + '\n'
            path2save = path_folder_sub_train[int(float(i)/50)]
            with open(path2save + str(i).zfill(3) + '.txt', 'w') as text_file:
                text_file.write(stg)
                text_file.close()
            with open(path2save + str(i).zfill(3) + '_ctr.txt', 'w') as text_file:
                text_file.write(stg_seg)
                text_file.close()

    return path_local_train

def send_data2ferguson(path_local, path_ferguson, cc, nb_img):
    """
    
      MAIN FUNCTION OF STEP 1
      Prepare training strategy and save it in 'ferguson_config.pkl'
      + send data to ferguson
      + send training files to ferguson
      + send training strategy to ferguson
    
          Inputs:
              - path_local [string]: working folder
              - path_ferguson [string]: ferguson working folder
              - cc [string]: contrast of interest
              - nb_img [int]: nb of images for training
          Outputs:
              - 
    
    """



    path_local_train_cur = prepare_train(path_local, path_ferguson, cc, nb_img)

    pickle_ferguson = {
                        'contrast': cc,
                        'nb_image_train': nb_img
                        }
    path_pickle_ferguson = path_local + 'ferguson_config.pkl'
    output_file = open(path_pickle_ferguson, 'wb')
    pickle.dump(pickle_ferguson, output_file)
    output_file.close()

    os.system('scp -r ' + path_local + 'input_img_' + contrast_of_interest + '/' + ' ferguson:' + path_ferguson)
    os.system('scp -r ' + path_local_train_cur + ' ferguson:' + path_ferguson)
    os.system('scp ' + path_pickle_ferguson + ' ferguson:' + path_ferguson)


# ******************************************************************************************



# ****************************      STEP 2 FUNCTIONS      *******************************

def pull_img_convert_nii_remove_img(path_local, path_ferguson, cc, nb_img):

    path_ferguson_res = path_ferguson + 'output_img_' + cc + '_'+ str(nb_img) + '/'
    path_local_res_img = path_local + 'output_img_' + cc + '_'+ str(nb_img) + '/'
    path_local_res_nii = path_local + 'output_nii_' + cc + '_'+ str(nb_img) + '/'

    # Pull .img results from ferguson
    os.system('scp -r ferguson:' + path_ferguson_res + ' ' + '/'.join(path_local_res_img.split('/')[:-2]) + '/')

    # Convert .img to .nii
    # Remove .img files
    for f in os.listdir(path_local_res_img):
        if not f.startswith('.'):
            path_res_cur = path_local_res_nii + f + '/'
            if not os.path.exists(path_res_cur):
                os.makedirs(path_res_cur)

            training_subj = f.split('__')

            if os.path.isdir(path_local_res_img+f):
                for ff in os.listdir(path_local_res_img+f):
                    if ff.endswith('_ctr.hdr'):

                        path_cur = path_local_res_img + f + '/' + ff
                        path_cur_out = path_res_cur + ff.split('_ctr')[0] + '_centerline_pred.nii.gz'
                        img = nib.load(path_cur)
                        nib.save(img, path_cur_out)

                    elif ff == 'time.txt':
                        os.rename(path_local_res_img + f + '/time.txt', path_local_res_nii + f + '/time.txt')

                os.system('rm -r ' + path_local_res_img + f)

# ******************************************************************************************



# ****************************      STEP 3 FUNCTIONS      *******************************

def _compute_stats(img_pred, img_true, img_seg_true):
    """
        -> mse = Mean Squared Error on distance between predicted and true centerlines
        -> maxmove = Distance max entre un point de la centerline predite et de la centerline gold standard
        -> zcoverage = Pourcentage des slices de moelle ou la centerline predite est dans la sc_seg_manual
    """

    stats_dct = {
                    'mse': None,
                    'maxmove': None,
                    'zcoverage': None
                }


    count_slice, slice_coverage = 0, 0
    mse_dist = []
    for z in range(img_true.dim[2]):

        if np.sum(img_true.data[:,:,z]):
            x_true, y_true = [np.where(img_true.data[:,:,z] > 0)[i][0] 
                                for i in range(len(np.where(img_true.data[:,:,z] > 0)))]
            x_pred, y_pred = [np.where(img_pred.data[:,:,z] > 0)[i][0]
                                for i in range(len(np.where(img_pred.data[:,:,z] > 0)))]
           
            xx_seg, yy_seg = np.where(img_seg_true.data[:,:,z]==1.0)
            xx_yy = [[x,y] for x, y in zip(xx_seg,yy_seg)]
            if [x_pred, y_pred] in xx_yy:
                slice_coverage += 1

            x_true, y_true = img_true.transfo_pix2phys([[x_true, y_true, z]])[0][0], img_true.transfo_pix2phys([[x_true, y_true, z]])[0][1]
            x_pred, y_pred = img_pred.transfo_pix2phys([[x_pred, y_pred, z]])[0][0], img_pred.transfo_pix2phys([[x_pred, y_pred, z]])[0][1]

            dist = ((x_true-x_pred))**2 + ((y_true-y_pred))**2
            mse_dist.append(dist)

            count_slice += 1

    if len(mse_dist):
        stats_dct['mse'] = sqrt(sum(mse_dist)/float(count_slice))
        stats_dct['maxmove'] = sqrt(max(mse_dist))
        stats_dct['zcoverage'] = float(slice_coverage*100.0)/count_slice

    return stats_dct

def _compute_stats_file(fname_ctr_pred, fname_ctr_true, fname_seg_true, folder_out, fname_out):

    img_pred = Image(fname_ctr_pred)
    img_true = Image(fname_ctr_true)
    img_seg_true = Image(fname_seg_true)

    stats_file_dct = _compute_stats(img_pred, img_true, img_seg_true)

    create_folders_local([folder_out])

    pickle.dump(stats_file_dct, open(fname_out, "wb"))


def _compute_stats_folder(subj_name_lst, training_subj, time_info, folder_subpkl_out, fname_out):

    stats_folder_dct = {}
    stats_folder_dct['iteration'] = training_subj
    stats_folder_dct['boostrap_time'] = time_info

    mse_lst, maxmove_lst, zcoverage_lst = [], [], []
    for subj in subj_name_lst:
        with open(folder_subpkl_out + 'res_' + subj + '.pkl') as outfile:    
            subj_metrics = pickle.load(outfile)
            outfile.close()
        mse_lst.append(subj_metrics['mse'])
        maxmove_lst.append(subj_metrics['maxmove'])
        zcoverage_lst.append(subj_metrics['zcoverage'])

    stats_folder_dct['avg_mse'] = round(np.mean(mse_lst),2)
    stats_folder_dct['avg_maxmove'] = round(np.mean(maxmove_lst),2)
    stats_folder_dct['cmpt_fail_subj_test'] = round(sum(elt >= 10.0 for elt in maxmove_lst)*100.0/len(maxmove_lst),2)
    stats_folder_dct['avg_zcoverage'] = round(np.mean(zcoverage_lst),2)

    print stats_folder_dct
    pickle.dump(stats_folder_dct, open(fname_out, "wb"))

def compute_dataset_stats(path_local, cc, nb_img):
    """
        MAIN FUNCTION OF STEP 3
        Compute validation metrics for each subjects
        + Save avg results in a pkl file for each subject
        + Save results in a pkl for each tuple (training subj, testing subj)

        Inputs:
              - path_local [string]: working folder
              - cc [string]: contrast of interest
              - nb_img [int]: nb of images for training
        Outputs:
              - 

    """

    path_local_nii = path_local + 'output_nii_' + cc + '_'+ str(nb_img) + '/'
    path_local_res_pkl = path_local + 'output_pkl_' + cc + '_'+ str(nb_img) + '/'
    path_local_gold = path_local + 'gold_' + cc + '/'
    path_local_seg = path_local + 'input_nii_' + cc + '/'
    fname_pkl_out = path_local_res_pkl + 'res_'

    for f in os.listdir(path_local_nii):
        if not f.startswith('.'):
            print path_local_nii + f + '/'
            path_res_cur = path_local_nii + f + '/'

            training_subj = f.split('__')

            time_info = 0.0
            folder_subpkl_out = path_local_res_pkl + f + '/'
            subj_name_lst = []
            for ff in os.listdir(path_local_nii+f):
                if ff.endswith('_centerline_pred.nii.gz'):
                    subj_name_cur = ff.split('_centerline_pred.nii.gz')[0]
                    fname_subpkl_out = folder_subpkl_out + 'res_' + subj_name_cur + '.pkl'
                    
                    if not os.path.isfile(fname_subpkl_out):
                        subj_name_lst.append(subj_name_cur)
                        path_cur_pred = path_res_cur + ff
                        path_cur_gold = path_local_gold + subj_name_cur + '_centerline_gold.nii.gz'
                        path_cur_gold_seg = path_local_seg + subj_name_cur + '_seg.nii.gz'

                        _compute_stats_file(path_cur_pred, path_cur_gold, path_cur_gold_seg, folder_subpkl_out, fname_subpkl_out)

                elif ff == 'time.txt':
                    with open(path_local_nii + f + '/' + ff) as text_file:
                        time_info = round(float(text_file.read()),2)

            fname_pkl_out_cur = fname_pkl_out + f + '.pkl'
            if not os.path.isfile(fname_pkl_out_cur):
                _compute_stats_folder(subj_name_lst, training_subj, time_info, folder_subpkl_out, fname_pkl_out_cur)

# ******************************************************************************************


# ****************************      STEP 4 FUNCTIONS      *******************************


def plot_violin(fname_pkl):

    with open(fname_pkl) as outfile:    
        metrics = pickle.load(outfile)
        outfile.close()

    sns.set(style="whitegrid", palette="pastel", color_codes=True)

    if 'avg_mse' in metrics:
        metric_list = ['avg_mse', 'avg_maxmove', 'cmpt_fail_subj_test', 'avg_zcoverage', 'boostrap_time']
        metric_name_list = ['MSE [mm]', 'Max Move [mm]', 'Fail [%]', 'Ctr In SegManual [%]', 'Time [s]']
    else:
        metric_list = ['mse', 'maxmove', 'zcoverage']
        metric_name_list = ['MSE [mm]', 'Max Move [mm]', 'Ctr In SegManual [%]']

    fig = plt.figure(figsize=(50, 10))
    cmpt=0
    for m, n in zip(metric_list, metric_name_list):
        a = plt.subplot(1,len(metric_list),cmpt+1)
        # sns.violinplot(metrics[m], inner="quartile", orient="v", cut=0)

        sns.violinplot(data=metrics[m], inner="quartile", cut=0, scale="count")
        sns.swarmplot(data=metrics[m], palette='deep', size=4)

        stg = 'Mean: ' + str(round(np.mean(metrics[m]),2))
        stg += '\nStd: ' + str(round(np.std(metrics[m]),2))
        if m != 'zcoverage' and m != 'avg_zcoverage':
            stg += '\nMax: ' + str(round(np.max(metrics[m]),2))
        else:
            stg += '\nMin: ' + str(round(np.min(metrics[m]),2))
        
        a.text(0.3,np.max(metrics[m]),stg,fontsize=15)
        plt.xlabel(n)

        cmpt += 1
    
    plt.savefig(fname_pkl.split('.')[0] + '.png')
    plt.close()


def run_plot_violin(path_local, cc, nb_img, prefixe_folder_out):

    path_folder_pkl = path_local + 'output_pkl_' + cc + '_'+ str(nb_img) + '/'
    path_out = path_local + prefixe_folder_out + '/'

    # dataset_pkl = '/'.join(path_folder_pkl.split('/')[:-1]) + '/dataset_lst_' + contrast + '.pkl'

    create_folders_local([path_out])

    metrics2plot_dct = {}
    outlier_dct = {}
    for file in os.listdir(path_folder_pkl):
        if file.endswith('.pkl'):
            #### IF SPECIFICATION
            with open(path_folder_pkl+file) as outfile:    
                metrics = pickle.load(outfile)
                outfile.close()

            for metric in metrics:
                if not metric in metrics2plot_dct:
                    metrics2plot_dct[metric] = []
                if not metric in outlier_dct:
                    outlier_dct[metric] = []

                value = metrics[metric]
                if 'mse' in metric or 'move' in metric or 'fail' in metric:
                    if value > 10:
                        outlier_dct[metric].append(file.split('res_')[1].split('.')[0])
                elif 'zcoverage' in metric:
                    if value < 90:
                        outlier_dct[metric].append(file.split('res_')[1].split('.')[0])
                metrics2plot_dct[metric].append(metrics[metric])

    rdn_nb = random.randint(0,10000)
    fname_pkl_out = path_out + str(rdn_nb) + '.pkl'
    pickle.dump(metrics2plot_dct, open(fname_pkl_out, "wb"))

    outlier_lst = []
    for metric in outlier_dct:
        if len(outlier_dct[metric]):
            outlier_lst.append(outlier_dct[metric])
            print '\n******'
            print 'Outliers (#=' + str(len(outlier_dct[metric])) +') for metric: ' + metric
            for fname in outlier_dct[metric]:
                print fname

    if len(outlier_lst):
        bad_boys_lst = [elt for elt in outlier_lst[0] for otherlist in outlier_lst[1:] if elt in otherlist]
        bad_boys_lst = np.unique(bad_boys_lst).tolist()
        print '\n******'
        print '# of Bad Boys: ' + str(len(bad_boys_lst))
        for bb in bad_boys_lst:
            print bb
    plot_violin(fname_pkl_out)


# ******************************************************************************************

# ****************************      STEP 5 FUNCTIONS      *******************************

def partition_resol(path_local, cc):

    fname_pkl_out = path_local + 'resol_dct_' + cc + '.pkl'
    if not os.path.isfile(fname_pkl_out):
        path_dataset_pkl = path_local + 'dataset_lst_' + cc + '.pkl'
        dataset = pickle.load(open(path_dataset_pkl, 'r'))
        dataset_subj_lst = [f.split('.img')[0].split('_'+cc)[0] for f in dataset]
        dataset_path_lst = [path_local + 'input_nii_' + cc + '/' + f.split('.img')[0]+'.nii.gz' for f in dataset]

        resol_dct = {'sag': [], 'ax': [], 'iso': []}
        for img_path, img_subj in zip(dataset_path_lst, dataset_subj_lst):
            img = Image(img_path)

            resol_lst = [round(dd) for dd in img.dim[4:7]]
            if resol_lst.count(resol_lst[0]) == len(resol_lst):
                resol_dct['iso'].append(img_subj)
            elif resol_lst[2]<resol_lst[0] or resol_lst[2]<resol_lst[1]:
                resol_dct['sag'].append(img_subj)
            else:
                resol_dct['ax'].append(img_subj)

            del img

        pickle.dump(resol_dct, open(fname_pkl_out, "wb"))
    else:
        with open(fname_pkl_out) as outfile:    
            resol_dct = pickle.load(outfile)
            outfile.close()

    return resol_dct


def compute_best_trainer(path_local, cc, nb_img, mm_lst, img_dct):

    path_pkl = path_local + 'output_pkl_' + cc + '_' + str(nb_img) + '/'

    campeones_dct = {}

    for interest in img_dct:
        img_lst = img_dct[interest]
        test_subj_dct = {}

        for folder in os.listdir(path_pkl):
            path_folder_cur = path_pkl + folder + '/'
            if os.path.exists(path_folder_cur):

                res_mse_cur_lst, res_move_cur_lst, res_zcoverage_cur_lst = [], [], []
                for pkl_file in os.listdir(path_folder_cur):
                    if '.pkl' in pkl_file:
                        pkl_id = pkl_file.split('_'+cc)[0].split('res_')[1]
                        if pkl_id in img_lst:
                            res_cur = pickle.load(open(path_folder_cur+pkl_file, 'r'))
                            res_mse_cur_lst.append(res_cur['mse'])
                            res_move_cur_lst.append(res_cur['maxmove'])
                            res_zcoverage_cur_lst.append(res_cur['zcoverage'])
                
                test_subj_dct[folder] = {'mse': [np.mean(res_mse_cur_lst), np.std(res_mse_cur_lst)],
                                         'maxmove': [np.mean(res_move_cur_lst), np.std(res_move_cur_lst)],
                                         'zcoverage': [np.mean(res_zcoverage_cur_lst), np.std(res_zcoverage_cur_lst)]}


        candidates_dct = {}
        for mm in mm_lst:
            candidates_lst = [[ss, test_subj_dct[ss][mm][0], test_subj_dct[ss][mm][1]] for ss in test_subj_dct]
            best_candidates_lst=sorted(candidates_lst, key = lambda x: float(x[1]))
            
            if mm == 'zcoverage':
                best_candidates_lst=best_candidates_lst[::-1]
                thresh_value = 90.0
                # thresh_value = best_candidates_lst[0][1] - float(best_candidates_lst[0][2])
                # candidates_dct[mm] = [cand[0] for cand in best_candidates_lst if cand[1]>thresh_value]
                candidates_dct[mm] = {}
                for cand in best_candidates_lst:
                    if cand[1]>thresh_value:
                        candidates_dct[mm][cand[0]] = {'mean':cand[1], 'std': cand[2]}
            else:
                thresh_value = 5.0
                # thresh_value = best_candidates_lst[0][1] + float(best_candidates_lst[0][2])
                # candidates_dct[mm] = [cand[0] for cand in best_candidates_lst if cand[1]<thresh_value]
                candidates_dct[mm] = {}
                for cand in best_candidates_lst:
                    if cand[1]<thresh_value:
                        candidates_dct[mm][cand[0]] = {'mean':cand[1], 'std': cand[2]}

        campeones_dct[interest] = candidates_dct
    
    pickle.dump(campeones_dct, open(path_local + 'best_trainer_' + cc + '_' + str(nb_img) + '_' + '_'.join(list(img_dct.keys())) + '.pkl', "wb"))

def find_best_trainer(path_local, cc, nb_img, mm, criteria_lst):

    with open(path_local + 'best_trainer_' + cc + '_' + str(nb_img) + '_' + '_'.join(criteria_lst) + '.pkl') as outfile:    
        campeones_dct = pickle.load(outfile)
        outfile.close()

    with open(path_local + 'resol_dct_' + cc + '.pkl') as outfile:    
        resol_dct = pickle.load(outfile)
        outfile.close()

    with open(path_local + 'patho_dct_' + cc + '.pkl') as outfile:    
        patho_dct = pickle.load(outfile)
        outfile.close()

    tot_subj = sum([len(resol_dct[ll]) for ll in resol_dct])

    good_trainer_condition = {'mse': 'Mean MSE < 4mm', 
                                'maxmove': 'Mean max move < 4mm', 
                                'zcoverage': '90% of predicted centerline is located in the manual segmentation'}

    criteria_candidat_dct = {}
    for criteria in criteria_lst:
        good_trainer_lst = [cand.split('_'+cc)[0] for cand in campeones_dct[criteria][mm]]
        criteria_candidat_dct[criteria] = good_trainer_lst
        nb_good_trainer = len(good_trainer_lst)

        print '\nTesting Population: ' + criteria
        print 'Metric of Interest: ' + mm
        print 'Condition to be considered as a good trainer: '
        print good_trainer_condition[mm]
        print '...% of good trainers in the whole ' + cc + ' dataset ' + str(round(nb_good_trainer*100.0/tot_subj))
        print '...Are considered as good trainer: '
        for resol in resol_dct:
            tot_resol = len(resol_dct[resol])
            cur_resol = len(set(good_trainer_lst).intersection(resol_dct[resol]))
            print '... ... ' + str(round(cur_resol*100.0/tot_resol,2)) + '% of our ' + resol + ' resolution images (#=' + str(tot_resol) + ')'
        for patho in patho_dct:
            tot_patho = len(patho_dct[patho])
            cur_patho = len(set(good_trainer_lst).intersection(patho_dct[patho]))
            print '... ... ' + str(round(cur_patho*100.0/tot_patho,2)) + '% of our ' + patho + ' subjects (#=' + str(tot_patho) + ')'




    # candidat_lst = list(set([x for x in campeones_ofInterest_names_lst if campeones_ofInterest_names_lst.count(x) == len(criteria_lst)]))

def inter_group(path_local, cc, nb_img, mm, criteria_dct):

    path_pkl = path_local+'output_pkl_'+cc+'_'+str(nb_img)+'/'

    group_dct = {}
    for train_subj in os.listdir(path_pkl):
        for group_name in criteria_dct:
            if train_subj.split('_'+cc)[0] in criteria_dct[group_name]:
                if not group_name in group_dct:
                    group_dct[group_name] = []
                group_dct[group_name].append(train_subj)

    inter_group_dct = {}
    for train_group in group_dct:
        for test_group in group_dct:
            print '\nTraining group: ' + train_group
            print 'Testing group: ' + test_group

            train_group_res = []
            for i,train_subj in enumerate(group_dct[train_group]):
                path_train_cur = path_pkl + group_dct[train_group][i] + '/'

                train_cur_res = []
                for j,test_subj in enumerate(group_dct[test_group]):
                    if group_dct[train_group][i] != group_dct[test_group][j]:
                        path_pkl_cur = path_pkl + group_dct[train_group][i] + '/res_' +  group_dct[test_group][j] + '.pkl'
                        with open(path_pkl_cur) as outfile:    
                            res_dct = pickle.load(outfile)
                            outfile.close()
                        train_cur_res.append(res_dct[mm])

                train_group_res.append(np.mean(train_cur_res))

            inter_group_dct[train_group+'_'+test_group] = [np.mean(train_group_res), np.std(train_group_res)]

    print inter_group_dct

    criteria_lst = list(criteria_dct.keys())
    res_mat = np.zeros((len(criteria_dct), len(criteria_dct)))
    for inter_group_res in inter_group_dct:
        train_cur = [s for s in criteria_lst if inter_group_res.startswith(s)][0]
        test_cur = [s for s in criteria_lst if inter_group_res.endswith(s)][0]
        res_mat[criteria_lst.index(train_cur), criteria_lst.index(test_cur)] = inter_group_dct[inter_group_res][0]

    print res_mat

    fig, ax = plt.subplots()
    if mm == 'zcoverage':
        plt.imshow(res_mat, interpolation='nearest', cmap=plt.cm.Blues)
    else:
        plt.imshow(res_mat, interpolation='nearest', cmap=cm.Blues._segmentdata)
    plt.title(mm, fontsize=15)
    plt.colorbar()
    tick_marks = np.arange(len(criteria_lst))
    plt.xticks(tick_marks, criteria_lst, rotation=45)
    plt.yticks(tick_marks, criteria_lst)


    thresh = res_mat.min()+(res_mat.max()-res_mat.min()) / 2.
    print thresh
    for i, j in itertools.product(range(res_mat.shape[0]), range(res_mat.shape[1])):
        plt.text(j, i, round(res_mat[i, j],2),color="white" if res_mat[i, j] > thresh else "black")

    # plt.tight_layout()
    plt.ylabel('Training image')
    plt.xlabel('Testing dataset')
    # plt.setp(ax.get_xticklabels(),visible=False)
    # plt.setp(ax.get_yticklabels(),visible=False)
    
    plt.show()



def plot_best_trainer_results(path_local, cc, nb_img, mm):

    lambda_rdn = 0.14

    path_plot = path_local + 'plot_best_train_' + cc + '_' + str(nb_img) + '_' + mm + '/'
    create_folders_local([path_plot])


    with open(path_local + 'resol_dct_' + cc + '.pkl') as outfile:    
        resol_dct = pickle.load(outfile)
        outfile.close()

    with open(path_local + 'patho_dct_' + cc + '.pkl') as outfile:    
        patho_dct = pickle.load(outfile)
        outfile.close()

    path_pkl = path_local + 'output_pkl_' + cc + '_' + str(nb_img) + '/'
    dataset_names_lst = [f for f in os.listdir(path_pkl) if os.path.exists(path_pkl + f + '/')]
    random.shuffle(dataset_names_lst, lambda: lambda_rdn)

    testing_dataset_lst = dataset_names_lst[:int(80.0*len(dataset_names_lst)/100.0)]
    validation_dataset_lst = dataset_names_lst[int(80.0*len(dataset_names_lst)/100.0):]

    subj_test_dct = {}
    for subj_test in testing_dataset_lst:
        path_folder_cur = path_pkl + subj_test + '/'

        for subj_test_test in testing_dataset_lst:
            if subj_test != subj_test_test:
                pkl_file = path_folder_cur + 'res_' + subj_test_test + '.pkl'
                res_cur = pickle.load(open(pkl_file, 'r'))
                if not subj_test in subj_test_dct:
                    subj_test_dct[subj_test] = []
                subj_test_dct[subj_test].append(res_cur[mm])

    best_lst = []
    for subj in subj_test_dct:
        best_lst.append([subj, np.mean(subj_test_dct[subj])])

    best_name = best_lst[[item[1] for item in best_lst].index(max([item[1] for item in best_lst]))]
    path_folder_best = path_pkl + best_name[0] + '/'

    res_dct = {}

    res_dct['validation'] = []
    for subj_val in validation_dataset_lst:
        pkl_file = path_folder_best + 'res_' + subj_val + '.pkl'
        res_cur = pickle.load(open(pkl_file, 'r'))
        res_dct['validation'].append(res_cur[mm])

    for pkl_file in os.listdir(path_folder_best):
        if '.pkl' in pkl_file:
            pkl_id = pkl_file.split('_'+cc)[0].split('res_')[1]
            res_cur = pickle.load(open(path_folder_best+pkl_file, 'r'))
            if not 'all' in res_dct:
                res_dct['all'] = []
            res_dct['all'].append(res_cur[mm])
            for patho in patho_dct:
                if pkl_id.split('_'+cc)[0] in patho_dct[patho]:
                    if str(patho) == 'HC':
                        patho = 'HC'
                    else:
                        patho = 'Patient'
                    if not patho in res_dct:
                        res_dct[patho] = []
                    res_dct[patho].append(res_cur[mm])
            for resol in resol_dct:
                if pkl_id.split('_'+cc)[0] in resol_dct[resol]:
                    if not resol in res_dct:
                        res_dct[resol] = []
                    res_dct[resol].append(res_cur[mm])

    print res_dct.keys()

    sns.set(style="whitegrid", palette="pastel", color_codes=True)
    group_labels = [['validation', 'all'], ['ax', 'iso'], ['HC', 'Patient']]
    if 'sag' in res_dct:
        if len(res_dct['sag']) > 20:
            nb_col = 3
            group_labels[1].append('sag')
        else:
            nb_col = 2
    else:
        nb_col = 2
    for gg in group_labels:
        fig, axes = plt.subplots(1, nb_col, sharey='col', figsize=(nb_col*10, 10))
        for i,group in enumerate(gg):
            if len(res_dct[group]) > 20:
                a = plt.subplot(1,nb_col,i+1)
                sns.violinplot(data=res_dct[group], inner="quartile", cut=0, scale="count", sharey=True)
                sns.swarmplot(data=res_dct[group], palette='deep', size=4)

                stg = 'Effectif: ' + str(len(res_dct[group]))
                stg += '\nMean: ' + str(round(np.mean(res_dct[group]),2))
                stg += '\nStd: ' + str(round(np.std(res_dct[group]),2))
                if mm != 'zcoverage' and mm != 'avg_zcoverage':
                    stg += '\nMax: ' + str(round(np.max(res_dct[group]),2))
                    a.text(0.3,np.max(res_dct[group]),stg,fontsize=15)
                    plt.title('Best Trainer: ' + best_name[0] + ' - ' + group + ' Dataset - Metric = ' + mm + '[mm]')
                else:
                    if cc == 't2':
                        a.set_ylim([60,105])
                    elif cc == 't1':
                        a.set_ylim([85,101])
                    stg += '\nMin: ' + str(round(np.min(res_dct[group]),2))
                    a.text(0.3,np.min(res_dct[group]),stg,fontsize=15)
                    a.set_title('Best Trainer: ' + best_name[0] + ' - ' + group + ' Dataset - Metric = Ctr_pred in Seg_manual [%]')
        plt.savefig(path_plot + '_'.join(gg) + '_' + str(lambda_rdn) + '.png')
        plt.close()


# ******************************************************************************************

# ****************************      USER CASE      *****************************************

def readCommand(  ):
    "Processes the command used to run from the command line"
    parser = argparse.ArgumentParser('Sdika Pipeline')
    parser.add_argument('-ofolder', '--output_folder', help='Output Folder', required = False)
    parser.add_argument('-c', '--contrast', help='Contrast of Interest', required = False)
    parser.add_argument('-n', '--nb_train_img', help='Nb Training Images', required = False)
    parser.add_argument('-s', '--step', help='Prepare (step=0) or Push (step=1) or Pull (step 2) or Compute metrics (step=3) or Display results (step=4)', 
                                        required = False)
    arguments = parser.parse_args()
    return arguments


USAGE_STRING = """
  USAGE:      python sct_sdika.py -ofolder '/Users/chgroc/data/data_sdika/' <options>
  EXAMPLES:   (1) python sct_sdika.py -ofolder '/Users/chgroc/data/data_sdika/' -c t2
                  -> Run Sdika Algorithm on T2w images dataset...
              (2) python sct_sdika.py -ofolder '/Users/chgroc/data/data_sdika/' -c t2 -n 3
                  -> ...Using 3 training images...
              (3) python sct_sdika.py -ofolder '/Users/chgroc/data/data_sdika/' -c t2 -n 3 -s 1
                  -> ...s=0 >> Prepare dataset
                  -> ...s=1 >> Push data to Ferguson
                  -> ...s=2 >> Pull data from Ferguson
                  -> ...s=3 >> Evaluate Sdika algo by computing metrics
                  -> ...s=4 >> Display results
                 """

if __name__ == '__main__':

    # Read input
    parse_arg = readCommand()

    if not parse_arg.output_folder:
        print USAGE_STRING
    else:
        path_local_sdika = parse_arg.output_folder
        create_folders_local([path_local_sdika])

        # Extract config
        with open(path_local_sdika + 'config.pkl') as outfile:    
            config_file = pickle.load(outfile)
            outfile.close()
        fname_local_script = config_file['fname_local_script']
        path_ferguson = config_file['path_ferguson']
        path_sct_testing_large = config_file['path_sct_testing_large']
        contrast_lst = config_file['contrast_lst']

        if not parse_arg.contrast:
            # List and prepare available T2w, T1w, T2sw data
            prepare_dataset(path_local_sdika, contrast_lst, path_sct_testing_large)

        else:
            # Format of parser arguments
            contrast_of_interest = str(parse_arg.contrast)
            if not parse_arg.nb_train_img:
                nb_train_img = 1
            else:
                nb_train_img = int(parse_arg.nb_train_img)
            if not parse_arg.step:
                step = 0
            else:
                step = int(parse_arg.step)            

            if not step:
                # Prepare [contrast] data
                prepare_dataset(path_local_sdika, [contrast_of_interest], path_sct_testing_large)
                
                # Send Script to Ferguson Station
                os.system('scp ' + fname_local_script + ' ferguson:' + path_ferguson)

            elif step == 1:
                # Send Data to Ferguson station
                send_data2ferguson(path_local_sdika, path_ferguson, contrast_of_interest, nb_train_img)

            elif step == 2:
                # Pull Results from ferguson
                pull_img_convert_nii_remove_img(path_local_sdika, path_ferguson, contrast_of_interest, nb_train_img)

            elif step == 3:
                # Compute metrics / Evaluate performance of Sdika algorithm
                compute_dataset_stats(path_local_sdika, contrast_of_interest, nb_train_img)

            elif step == 4:
                # Plot dataset results
                run_plot_violin(path_local_sdika, contrast_of_interest, nb_train_img, 'plot_'+contrast_of_interest+'_'+str(nb_train_img)+'_all')

            elif step == 5:
                # Partition dataset into ISO, AX and SAG
                resol_dct = partition_resol(path_local_sdika, contrast_of_interest)

                # Partition dataset into HC // DCM // MS 
                with open(path_local_sdika + 'patho_dct_' + contrast_of_interest + '.pkl') as outfile:    
                    patho_dct = pickle.load(outfile)
                    outfile.close()

                # compute_best_trainer(path_local_sdika, contrast_of_interest, nb_train_img, ['mse', 'maxmove', 'zcoverage'],
                #                         {'HC': patho_dct['HC'], 'MS': patho_dct['MS'], 'CSM': patho_dct['CSM']})
                # find_best_trainer(path_local_sdika, contrast_of_interest, nb_train_img, 'mse', ['CSM', 'HC', 'MS'])
                
                # compute_best_trainer(path_local_sdika, contrast_of_interest, nb_train_img, ['mse', 'maxmove', 'zcoverage'],
                #                         {'AX': resol_dct['ax'], 'SAG': resol_dct['sag'], 'ISO': resol_dct['iso']})
                # find_best_trainer(path_local_sdika, contrast_of_interest, nb_train_img, 'mse', ['AX', 'SAG', 'ISO'])


                inter_group(path_local_sdika, contrast_of_interest, nb_train_img, 'zcoverage', resol_dct)
            elif step == 6:
                plot_best_trainer_results(path_local_sdika, contrast_of_interest, nb_train_img, 'zcoverage')
            else:
                print USAGE_STRING

    print TODO_STRING




# python sct_sdika.py -ofolder '/Users/chgroc/data/data_sdika/' -c t2 -n 1 -s 5







# ****************************      TO BE CLEANED      ****************************   

#     fname_pkl = 'res_' + contrast + '_' + seg_ctr + '_' + str(nb_image_train) + '.pkl'
#     # fail_list_t2_1_seg = ['twh_e24751', 'twh_e23699', 'bwh_CIS1_t2_sag', 'bwh_SP4_t2_sag', 'bwh_SP4_t2_sag_stir',
#     #                         'paris_hc_42', 'paris_hc_84', 'paris_hc_82', 'paris_hc_116',
#     #                         'amu_PAM50_VP', 'amu_PAM50_GB', 'amu_PAM50_ALT', '20151025_emil_t2',
#     #                         'unf_pain_08']
#     # fail_list_t2_1_ctr = ['twh_e24751', 'twh_e23699', 'bwh_SP4_t2_sag', 'bwh_SP4_t2_sag_stir',
#     #                         'paris_hc_42', 'paris_hc_82', 'paris_hc_116',
#     #                         'amu_PAM50_VP', 'amu_PAM50_GB', 'amu_PAM50_ALT',
#     #                         'unf_pain_08', 'unf_pain_07', 'unf_pain_20']
#     # display_stats(path_local_res_pkl, fname_pkl, [])
#     plot_violin(path_local_res_pkl, fname_pkl)




# elif part == 2:



#     def display_stats(path_local_pkl, fname_out, fail_list=[]):

#         mse, move, fail, cov, time, it = [], [], [], [], [], []
#         for f in os.listdir(path_local_pkl):
#             if not f == fname_out and not f.startswith('.'):
#                 print path_local_pkl + f
#                 with open(path_local_pkl + f) as outfile:    
#                     res = pickle.load(outfile)
#                     outfile.close()

#                 if not any(x in f for x in fail_list):
#                     mse.append(res['avg_mse'])
#                     move.append(res['avg_max_move'])
#                     fail.append(res['cmpt_fail_subj_test'])
#                     cov.append(res['slice_coverage'])
#                     time.append(res['boostrap_time'])
#                     it.append(res['iteration'][0])

#         if nb_image_train > 1:
#             it = [i for i in range(len(mse))]
#         stats_dict = {'iteration': it, 'avg_mse': mse, 'avg_max_move': move, 'cmpt_fail_subj_test': fail, 'slice_coverage': cov, 'boostrap_time': time}
#         pickle.dump(stats_dict, open(path_local_pkl + fname_out, "wb"))

#         if nb_image_train > 1:
#             it = [str(i).zfill(3) for i in it]

#         mean = ['Mean', str(round(np.mean(mse),2)), str(round(np.mean(move),2)), str(round(np.mean(fail),2)), str(round(np.mean(cov),2)), str(round(np.mean(time),2))]
#         std = ['Std', str(round(np.std(mse),2)), str(round(np.std(move),2)), str(round(np.std(fail),2)), str(round(np.std(cov),2)), str(round(np.std(time),2))]
#         maxx = ['Extremum', str(round(np.max(mse),2)), str(round(np.max(move),2)), str(round(np.max(fail),2)), str(round(np.min(cov),2)), str(round(np.max(time),2))]
        
#         mse = [str(i) for i in mse]
#         move = [str(i) for i in move]
#         fail = [str(i) for i in fail]
#         cov = [str(i) for i in cov]
#         time = [str(i) for i in time]

#         head2print = ['It. #', 'Avg. MSE [mm]', 'Avg. Max Move [mm]', 'Cmpt. Fail [%]', 'zCoverage [%]', 'Time [s]']
#         scape = [' ']
#         if nb_image_train > 1:
#             col_width = max(len(word) for word in head2print) + 2
#         else:
#             col_width = max(len(word) for word in it) + 2
#         data2plot = [[ff, mm, mmmm, ss, cc, tt] for ff, mm, mmmm, ss, cc, tt in zip(it, mse, move, fail, cov, time)]
#         data2plot = [head2print] + [scape] + [mean] + [std] + [maxx] + [scape] + data2plot

#         for row in data2plot:
#             print "".join(str(word).ljust(col_width) for word in row)


#     def plot_violin(path, fname_pkl):

#         data = pickle.load(open(path + fname_pkl))
#         import seaborn as sns
#         import matplotlib.pyplot as plt
#         sns.set(style="whitegrid", palette="pastel", color_codes=True)

#         metric_list = ['avg_mse', 'avg_max_move', 'cmpt_fail_subj_test', 'slice_coverage', 'boostrap_time']
#         metric_name_list = ['Avg. MSE [mm]', 'Avg. Max Move [mm]', 'Cmpt. Fail [%]', 'zCoverage [%]', 'Time [s]']
#         for m, n in zip(metric_list, metric_name_list):
#             fig = plt.figure(figsize=(10, 10))
#             a = plt.subplot(111)
#             sns.violinplot(data[m], inner="point", orient="v")
#             stg = 'Mean: ' + str(round(np.mean(data[m]),2))
#             stg += '\nStd: ' + str(round(np.std(data[m]),2))
#             if m != 'slice_coverage':
#                 stg += '\nMax: ' + str(round(np.max(data[m]),2))
#             else:
#                 stg += '\nMin: ' + str(round(np.min(data[m]),2))
#             a.text(0.3,np.max(data[m]),stg,fontsize=15)
#             plt.xlabel(n)
#             plt.savefig(path + 'plot_' + m + '.png')
#             plt.close()
