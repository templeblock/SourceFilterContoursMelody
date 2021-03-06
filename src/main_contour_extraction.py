'''
Created on Sep 2, 2016

@author: georgid
'''
import os
import json
from melodyExtractionFromSalienceFunction import MEFromSF
from HarmonicSummationSF import calculateSpectrum, calculateSF
import sys
import pandas as pd
from Parameters import Parameters
import numpy as np
from contour_classification.experiment_utils import get_data_files
from contour_classification.contour_utils import contours_from_contour_data
from timbreFeatures import compute_timbre_features
from melodyExtractionFromSalienceFunction import saveContours
import parsing
from timbreFeatures import contour_to_audio
from numpy import isnan
from timbreFeatures import load_timbre_features


# mel_type = 1
#     #  for iKala
# if Parameters.datasetIKala:
#         with open('contour_classification/melody_trackids_iKala.json', 'r') as fhandle:
#             track_list = json.load(fhandle)
# tracks = track_list['tracks']



def create_contours_and_store(tracks, contours_output_path):
    '''
    extract contours with essentia with SAL features
    
    output .pitch.ctr in folder contours_output_path
    '''
    import parsing
    
    (args,options) = parsing.parseOptions(sys.argv)
    
    options.pitchContinuity = 27.56
    options.peakDistributionThreshold = 1.3
#     options.peakDistributionThreshold = 0.9
    options.peakFrameThreshold = 0.7
#     options.peakFrameThreshold = 0.9
    options.timeContinuity = 100

#     options.timeContinuity = 50     # medley DB
    options.minDuration = 300
    options.voicingTolerance = 1
    options.useVibrato = False
    
    options.Fs = 44100
    options.extractionMethod = 'PCC'
    options.plotting = False
    
    
    

           
    for fileName in tracks:

        options.pitch_output_file    = contours_output_path + fileName
        wavfile_  = os.path.join(Parameters.iKala_URI, 'Wavfile', fileName + '.wav')
        spectogram, fftgram = calculateSpectrum(wavfile_, options.hopsizeInSamples)
        timesHSSF, HSSF = calculateSF(spectogram,  options.hopsizeInSamples)
        HSSF = HSSF.T
        print("Extracting melody from salience function ")
        times, pitch = MEFromSF(timesHSSF, HSSF, fftgram, options)
        

def add_timbre_features_and_save(track, contours_output_path, options):
    
    '''
    load extracted ctrs,  
    add timbre features and save contours in 
    same format .pitch.ctr
    '''
        
    contour_data_frame, contours_bins_SAL, contours_saliences_SAL, contours_start_times_SAL = load_contour(track, options)

    wavfile_  = os.path.join(Parameters.iKala_URI, 'Wavfile', track + '.wav')
    _, fftgram = calculateSpectrum(wavfile_, options.hopsizeInSamples)
    timestamps_recording = np.arange(len(fftgram)) * float(options.hopsizeInSamples) / options.Fs
    
    
    options.saveContours = True
    options.track = track
    
    options.pitch_output_file    = os.path.join(contours_output_path, track)
    

    
    options.contours_output_path = contours_output_path
    contourTimbre = compute_timbre_features(contours_bins_SAL, contours_start_times_SAL, fftgram, timestamps_recording, options)
    
    if Parameters.read_features_from_MATLAB:
        path_ = options.contours_output_path + Parameters.features_MATLAB_URI
        contours_vvs_matlab =  load_timbre_features(contour_data_frame, path_, track)
        
        #  take median  and put in  numpoy array 
        contourTimbre_matlab_vv =  np.zeros([len(contours_vvs_matlab), Parameters.dim_vv]) # compute timbral features
        for i, contour_vvs in enumerate(contours_vvs_matlab):
            median_timbre_features = np.median(contour_vvs, axis = 0)
            contourTimbre[i,:] = median_timbre_features
        
        
        
        contourTimbre[:, 0:contourTimbre_matlab_vv.shape[1]] = contourTimbre_matlab_vv
        
    
    if isnan(contourTimbre).any():
        print 'contour for file {} has nans'.format(options.pitch_output_file)
    
    
    saveContours(options, options.stepNotes, contours_bins_SAL, contours_saliences_SAL, contours_start_times_SAL, \
                 contourTimbre, old_contour_data=contour_data_frame)
        



def load_contour(track, options):
    '''
    utility function to load contour as pandas data frame and 
    store as simple list of bins 
    
    ------------
    Return: contours_bins_list of bins 
    '''

        
    contour_data_frame, adat = get_data_files(track, meltype=1)
    
    contours_start_times_df, contours_bins_df, contours_saliences_SAL_df = contours_from_contour_data(contour_data_frame)
    
    contours_bins_SAL = []
    contours_saliences_SAL = []
    for (freqs, saliences) in zip(contours_bins_df.iterrows(), contours_saliences_SAL_df.iterrows()) :
        freqs = freqs[1].values
        freqs = freqs[~np.isnan(freqs)] # remove trailing nans
        contours_bins_SAL.append(freqs)
        
        saliences = saliences[1].values
        saliences = saliences[~np.isnan(saliences)] # remove trailing nans
        contours_saliences_SAL.append(saliences)
        
    contours_start_times_SAL = contours_start_times_df.values[:,0]
    return contour_data_frame, contours_bins_SAL, contours_saliences_SAL, contours_start_times_SAL


def contours_to_audio(track, contours_output_path, options):
    '''
    sonify only the harmonic partials from the contour
    take spectral part with f0 at contour 
    '''
        
    contour_data_frame, contours_bins_SAL, contours_saliences_SAL, contours_start_times_SAL = load_contour(track, options)

    wavfile_  = os.path.join(Parameters.iKala_URI, 'Wavfile', track + '.wav')
    _, fftgram = calculateSpectrum(wavfile_, options.hopsizeInSamples)
    timestamps_recording = np.arange(len(fftgram)) * float(options.hopsizeInSamples) / options.Fs
    
    options.contours_output_path = contours_output_path
    options.track = track
    spectogram_contours = contour_to_audio(contours_bins_SAL, contours_start_times_SAL, fftgram, timestamps_recording, options)
    return     spectogram_contours

def label_contours_and_store(output_contours_path, tracks, normalize):
    '''
    overlap all contours with ground truth and serialize to pandas pickle
    added as a separate function to be able to run statistics of labels 
    before contour training
    
    Parameters
    -------------------
    normalize: 
        normalize the SAL features when loading contours
    
    '''
    mel_type = 1 # this work is restriced to only melody type = 1
    

    # mdb_files, splitter = eu.create_splits(test_size=0.15)
    import contour_classification.experiment_utils as eu
    ########################### 3.1 Contour labeling
    dset_contour_dict, dset_annot_dict = eu.compute_all_overlaps(tracks, normalize=normalize, meltype=mel_type)
    
    
      
    dset_contour_dict_labeled, _, _ = \
            eu.label_all_contours(dset_contour_dict, dset_contour_dict, \
                                  dset_contour_dict, olap_thresh=Parameters.OLAP_THRESH)
    
    mix = ''
    if Parameters.medleyDb:
        mix = 'MIX'
    for track in dset_contour_dict_labeled.keys():
        contour_data =  dset_contour_dict_labeled[track]
        picklefile = os.path.join(output_contours_path, track + mix + Parameters.CONTOUR_EXTENSION)
        from pickle import dump
        with open(picklefile, 'wb') as handle:
            dump(contour_data, handle)
            print 'stored contours as ' + picklefile
    
    print 'labeling finished...'
    return dset_contour_dict_labeled, dset_annot_dict



if __name__ == '__main__':
    
    if len(sys.argv) != 4:
        sys.exit('usage: {} <path-to-root-dir-of-dataset>  <path-contours> <create_contours=1, extracttimbre=2, contour_to_audio=3> '.format(sys.argv[0]))
    path_ = sys.argv[1]
    Parameters.iKala_URI = path_
    Parameters.set_paths()  
    whichStep_ = int(sys.argv[3]) #
    Parameters.with_MATPLOTLIB = True # set to False if running on hpc, becasue it might create problems
    
    Parameters.contour_URI = sys.argv[2]
    args, options = parsing.parseOptions(sys.argv)
    
#     tracks = ['61647_verse']
    tracks = Parameters.tracks
#     Parameters.contour_URI += '/vv_hopS-0.5/'
    if whichStep_ == 1:
        if not os.path.exists(Parameters.contour_URI):
            os.mkdir(Parameters.contour_URI)
            
        create_contours_and_store(tracks, Parameters.contour_URI)
    
    elif whichStep_ == 2:
       
        Parameters.extract_timbre = True
        for track in tracks:
            add_timbre_features_and_save(track, Parameters.contour_URI, options)
    
    elif whichStep_ == 3: # simply resynth to audio
        for track in tracks:
            spectogram_contours =  contours_to_audio(track, Parameters.contour_URI, options)
            if Parameters.with_MATPLOTLIB: # visualize spectogram with contours 
                from matplotlib import pyplot as plt
                from matplotlib import cm
                for contour_spec in spectogram_contours:
                    plt.imshow(np.rot90(contour_spec[:,1:140]), interpolation = 'none', cmap=cm.coolwarm)
                    ax = plt.gca()
                    ax.grid(False)
                    plt.show()
    
    # in all cases label contours according annotations
    dset_contour_dict_labeled, dset_annot_dict = label_contours_and_store(Parameters.contour_URI, tracks, normalize=False)

    

#     MEFromFileNumInFolder('../test/', 'output', 1 , options)
# #     MEFromFileNumInFolder(sys.argv[1], sys.argv[2], int(sys.argv[3]), options)
    