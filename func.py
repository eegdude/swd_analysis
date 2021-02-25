import mne
import pathlib
import pickle
from scipy import signal, stats
import numpy as np

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from matplotlib import pyplot as plt

import config

def open_file_dialog(ftype:str='raw', multiple_files:bool=False):
    if ftype == 'raw':
        window_name ='Select *DF file'
        ftype_filter = 'EEG (*.edf, *.bdf) ;; All files(*)'
    elif ftype == 'pickle':
        window_name ='Select .pickle file'
        ftype_filter = 'preprocessed EEG (*.pickle) ;; All files(*)'
    elif ftype == 'csv':
        window_name ='Select .csv file'
        ftype_filter = 'exported SWD (*.csv) ;; All files(*)'
    
    if multiple_files:
        filenames, _ = QFileDialog.getOpenFileNames(None, window_name, str(config.settings.value('LAST_FILE_LOCATION')), ftype_filter)
    else:
        filename, _ = QFileDialog.getOpenFileName(None, window_name, str(config.settings.value('LAST_FILE_LOCATION')), ftype_filter)
        filenames = [filename]
    
    if filenames:
        filenames = [pathlib.Path(f) for f in filenames]
        config.settings.setValue('LAST_FILE_LOCATION', filenames[0].parent)
    if pathlib.WindowsPath('.') in filenames:                                   # фигня с точкой происходит из-за пустого пути
        return []
    if multiple_files:
        return filenames
    else:
        return filenames[0]

def check_filename_exists(filename):
    if filename:
        if filename.exists():
            return True
        else:
            return
    else:
        return

def open_data_file(filename):
    if not check_filename_exists(filename):
        return None

    if filename.suffix == '.pickle':
        with open(filename, 'rb') as f:
            intermediate = pickle.load(f)
            eeg_file_path = pathlib.Path(intermediate['filename'])
            if not check_filename_exists(eeg_file_path):
                buttonReply = QMessageBox.question(None, "No valid EEG for this annotation", f"No file at {eeg_file_path}\nSelect another xdf file?")
                if buttonReply == QMessageBox.Yes:
                    data = open_data_file(open_file_dialog('raw'))
                    if data:
                        data = data['data']
                    else:
                        return None
                else:
                    return None
            else:
                data = read_xdf_file(eeg_file_path)

            eeg = {'data':data,
                'filename':str(filename)}
            eeg['data'].annotation_dict = intermediate['annotation_dict']

    elif filename.suffix == '.bdf' or filename.suffix == '.edf':
        eeg = {'data': read_xdf_file(filename),
                'filename':str(filename)}
    else:
        QMessageBox.about(None, "No valid EEG", f"No vaild EEG file at {filename}\nYou can load .pickle or .xdf file")
        return None
    return eeg

def write_csv_line(file_object, line):
    file_object.write(';'.join([str(a).replace('.',config.decimal_separator) for a in line]) + '\n')

def read_xdf_file(filename:pathlib.Path=None):
    if filename.suffix == '.bdf':
        raw = mne.io.read_raw_bdf(filename, preload=True)
    elif filename.suffix == '.edf':
        raw = mne.io.read_raw_edf(filename, preload=True)
    return raw

def filter_eeg(eeg:mne.io.RawArray):
    if eeg is not None:
        eeg = eeg.filter(config.l_freq, config.h_freq, verbose=0)
    return eeg

def welch_spectrum(swd_data:dict, swd_state:dict, fs:float=250, 
    nperseg_sec:int=config.nperseg_sec, noverlap:int=config.noverlap_fraction, 
    max_freq:float=config.max_freq, normalize:bool=config.normalize):

    nperseg_samples = int(nperseg_sec*fs)
    noverlap_samples = int(nperseg_samples*noverlap)
    x = None
    welch_total = {}
    spectrum_id_total = {}
    rejected_swd = {}
    for n, swd_file in enumerate(swd_data):
        if sum(swd_state[swd_file]):
            welch_single_file = []
            spectrum_id_single_file = []
            rejected_swd_single_file = []
            # active_swd = [a for a, b in zip(swds[swd_file], swd_state[swd_file]) if b]
            for swd_id, swd in enumerate(swd_data[swd_file]['data']):
                if swd_state[swd_file][swd_id]:
                    if len(swd) < nperseg_samples:
                        print (f'dropped swd #{swd_id}: length {len(swd)} samples is less than welch length {nperseg_samples}')
                        swd_state[swd_file][swd_id] = False
                        rejected_swd_single_file.append(swd_id)
                    else:
                        w = signal.welch(swd, fs=fs, 
                            nperseg=nperseg_samples, noverlap=noverlap, detrend=False)
                        x = w[0]
                        w = w[1]
                        
                        welch_single_file.append(w)
                        spectrum_id_single_file.append(swd_id)
                else:
                    print (f'swd #{swd_id} excluded')

            cutoff = sum(x <= max_freq)
            welch_single_file = np.array(welch_single_file)
            welch_single_file = welch_single_file[:,:cutoff]
            x = x[:cutoff]
            # welch_single_file = np.average(welch_single_file, axis=0).ravel()
            if normalize:
                welch_single_file/=np.max(welch_single_file)
            welch_total[swd_file] = welch_single_file
            
            spectrum_id_total[swd_file] = spectrum_id_single_file
            rejected_swd[swd_file] = rejected_swd_single_file

    return {'x':x, 'spectrums':welch_total, 'spectrum_id':spectrum_id_total, 'rejected_swd':rejected_swd}

def plot_conditions(data:dict, swd_names:dict, swd_state:dict, canvas, plot_quantiles):
    canvas.axes.clear()
    x = data['x']
    if 'significance' in list(data.keys()):
        for a in data['significance']:
            canvas.axes.axvline(x[a], color='grey', alpha=0.5)
    for label in data['spectrums'].keys():
        sample = data['spectrums'][label]
        mask = [swd_state[label][i] for i in data['spectrum_id'][label]]
        sample = sample[mask,:]
        if sample.shape[0]:
            avg = np.median(sample, axis=0)
            canvas.axes.plot(x, avg, label=swd_names[label])
            if plot_quantiles:
                upper = np.quantile(sample, 0.75, axis=0)
                lower = np.quantile(sample, 0.25, axis=0)
                canvas.axes.fill_between(x, avg-lower, avg+upper, alpha=0.2)
    canvas.axes.legend(bbox_to_anchor=(0.5, 1), fontsize='xx-small')
    canvas.draw()
    canvas.flush_events()

def statistics_nonparametric(data:dict, swd_state:dict, correction:bool=True):
    if len(list(data['spectrums'].keys())) < 2:
        return [], []
    
    data_subset = {}
    for swd_filepath_key in swd_state.keys():
        mask = [True if swd_state[swd_filepath_key][a] else False for a in data['spectrum_id'][swd_filepath_key] ]
        data_subset[swd_filepath_key] = data['spectrums'][swd_filepath_key][mask]
    data_list = [condition for condition in data_subset.values()]

    mw = [stats.ttest_ind(data_list[0][:,a], data_list[1][:,a]) for a in range(data_list[0].shape[1])] # only 2!!!
    p = np.array([a[1] for a in mw])

    if correction:
        p*=data_list[0].shape[1]
    significant_values = (np.where(p<0.05))[0]
    if not significant_values.shape[0]:
        print ('no signifncant values found')
    return significant_values, mw