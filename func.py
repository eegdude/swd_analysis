from locale import normalize
import stat
from sys import float_repr_style
import mne
import pathlib
import pickle
from scipy import signal, stats, interpolate, integrate
import numpy as np

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from matplotlib import pyplot as plt

import datetime
import warnings

import config

from tqdm.auto import tqdm

class EEG:
    '''
    add activity state here
    '''
    def __init__(self, eeg=None):
        pass
    
    def read_eeg_file(self, filename):
        self.raw = read_xdf_file(filename=filename)
        self.raw._data *= 1e6 # fix for different units

    def apply_filter(self, l:float_repr_style=config.l_freq, h:float_repr_style=config.h_freq):
        if hasattr(self, 'raw'):
            if self.raw:
                self.raw = filter_eeg(self.raw, l, h)
                return
        warnings.warn("Valid EEG data is not loaded, nothing to filter", Warning)

    
    def set_params_from_dict(self, intermediate:dict):
        for key in intermediate.keys():
            if key not in ['raw', 'filename']:
                setattr(self, key, intermediate[key])
            if key == 'raw_info': # pickles and jsons without loaded EEG don't have raw attrubute
                try:
                    self.apply_filter(intermediate['raw_info']['info']['highpass'], intermediate['raw_info']['info']['lowpass']) # raw_info can in theory not match raw?
                except ValueError as e:
                    print(f"{e} \nskipping filtration")

def open_file_dialog(ftype:str='raw', multiple_files:bool=False):
    if ftype == 'raw':
        window_name ='Select *DF file'
        ftype_filter = 'EEG (*.edf *.bdf) ;; All files(*)'
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

    if pathlib.WindowsPath('.') in filenames:                                   # фигня с точкой происходит из-за пустого пути
        return []
    else:
        if len(filenames)>0:
            config.settings.setValue('LAST_FILE_LOCATION', filenames[0].parent) # update last file location if filename not empty
    
    if multiple_files:
        return filenames
    else:
        return filenames[0]

def check_filename_exists(filename):
    if filename:
        if filename.is_file():
            return True
    return

def open_intermediate_file(filename):
   
    if filename.suffix == '.h5':
        raise NotImplementedError
    elif filename.suffix == '.pickle':
        warnings.warn("pickles are being deprecated", Warning)
        open_file = pickle.load
    else:
        return
    with open(filename, 'rb') as f:
        intermediate = open_file(f)
    
    return intermediate

def open_data_file(filename:pathlib.Path):
    # refactor
    if not filename:
        return None
    if not check_filename_exists(filename):
        print(f'filename {filename} doesn\'t exist')
        return None

    if filename.suffix in ['.json', '.pickle']:
        intermediate = open_intermediate_file(filename)
        eeg_file_path = pathlib.Path(intermediate['filename'])
        if not check_filename_exists(eeg_file_path):
            buttonReply = QMessageBox.question(None, "No valid EEG for this annotation", f"No file at {eeg_file_path}\nSelect another xdf file?")
            if buttonReply == QMessageBox.Yes:
                eeg = open_data_file(open_file_dialog('raw'))
            else:
                return None
        else:
            eeg = open_data_file(eeg_file_path)

        if eeg:
            eeg.set_params_from_dict(intermediate)

    elif filename.suffix == '.bdf' or filename.suffix == '.edf':
        eeg = EEG()
        eeg.read_eeg_file(filename)
        eeg.filename = str(filename)
    else:
        QMessageBox.about(None, "No valid EEG", f"No vaild EEG file at {filename}\nYou can load .pickle or .xdf file")
        return None
    return eeg

def write_csv_line(file_object, line):
    file_object.write(config.csv_sep.join([str(a).replace('.',config.decimal_separator) for a in line]) + '\n')

def read_xdf_file(filename:pathlib.Path=None):
    if filename.suffix == '.bdf':
        raw = mne.io.read_raw_bdf(filename, preload=True)
    elif filename.suffix == '.edf':
        raw = mne.io.read_raw_edf(filename, preload=True)
    return raw

def filter_eeg(eeg:mne.io.RawArray, l=config.l_freq, h=config.h_freq, n=config.notch_freq):
    if eeg is not None:
        eeg = eeg.notch_filter(np.arange(n, eeg.info['sfreq']/2, n), verbose=0) 
        eeg = eeg.filter(l, h, verbose=0) 
    return eeg

def welch_spectrum(container, 
    nperseg_sec:int=config.nperseg_sec, noverlap:int=config.noverlap_fraction, 
    fmax:float=config.fmax, fmin:float=0): #SWDTabContainer
    # noverlap_samples = int(nperseg_samples*config.noverlap_fraction)
    
    if not sum(container.swd_state.values()):
        return
    else:
        container.welch = {}
    
    nperseg_samples = int(nperseg_sec*container.raw_info['info']['sfreq'])
    freqs = np.arange(nperseg_samples // 2 + 1, dtype=float) * (container.raw_info['info']['sfreq'] / nperseg_samples)
    freq_mask = (freqs >= fmin) & (freqs <= fmax)


    for swd_uuid in container.swd_data.keys():
        # if container.swd_state[swd_uuid]:
        if len(container.swd_data[swd_uuid]) < nperseg_samples:
            # print (f'dropped swd #{swd_uuid}: length {len(container.swd_data[swd_uuid])} samples is less than welch length {nperseg_samples}')
            container.swd_state[swd_uuid] = False
        else:
            pass
            
            w = signal.welch(container.swd_data[swd_uuid], fs=container.raw_info['info']['sfreq'], 
                nperseg=nperseg_samples, noverlap=config.noverlap_fraction, detrend=False, 
                average='median')
            container.spectrum_x = w[0][freq_mask]
            container.welch[swd_uuid] = w[1][freq_mask]


def check_spectrum_x_equal(channels_containers):
    x_ = [a.spectrum_x for a in  channels_containers.values()]
    try:
        for i in range(len(x_)):
            decimal = int(np.ceil(np.abs(np.log10(np.average(np.diff(x_[0])))))) # ?????? 
            np.testing.assert_array_almost_equal(x_[0], x_[i], decimal=decimal)
    except AssertionError as e:
        print (e)
        return
    return True


def average_spectrum(channels_containers, method=np.average):
    if not check_spectrum_x_equal(channels_containers):
        return
    w = filter_data_by_state(channels_containers)
    
    w = {k:method(w[k], axis=0) for k in w}
    return w

def calculate_asymmetry(container, peak_prominence_percentage_from_minmax:float = config.peak_prominence_percentage_from_minmax):
    if not sum(container.swd_state.values()):
        return
    else:
        container.asymmetry = {}
    for swd_uuid in container.swd_data.keys():
        # if container.swd_state[swd_uuid]:
        swd = container.swd_data[swd_uuid]
        if not len(swd):
            container.asymmetry[swd_uuid] = None
            continue
        length = len(swd)/container.raw_info['info']['sfreq']
        minmax = np.max(swd) - np.min(swd)
        peaks_upper = signal.find_peaks(swd, prominence = minmax*config.peak_prominence_percentage_from_minmax )[0]
        peaks_lower = signal.find_peaks(swd*-1, prominence = minmax*config.peak_prominence_percentage_from_minmax )[0]
            
        minmax_mean_peaks = np.mean(swd[peaks_upper]) - np.mean(swd[peaks_lower])
        try:
            swd_u = interpolate.interp1d(peaks_upper, swd[peaks_upper], kind='cubic')(np.arange(peaks_upper[0],peaks_upper[-1]))
            swd_d = interpolate.interp1d(peaks_lower,  swd[peaks_lower], kind='cubic')(np.arange(peaks_lower[0],peaks_lower[-1]))

            # minmax_mean_spline = np.mean(swd_u)-np.mean(swd_d)
            
            u = integrate.trapz(swd_u)
            d = integrate.trapz(swd_d*-1)

            assym_integrated = np.abs(u/d)
            minmax_integrated = np.abs(u-d)

            assym_peaks = np.abs(np.mean(swd[peaks_lower]) / minmax_mean_peaks)*100
            container.asymmetry[swd_uuid] = {
                    'uuid':swd_uuid,
                    'peaks_lower':peaks_lower,
                    'peaks_upper':peaks_upper,
                    
                    'spline_lower':swd_d,
                    'spline_upper':swd_u,
                    
                    'spline_lower_integtal':d,
                    'spline_upper_integtal':u,

                    'assym_peaks':assym_peaks,
                    
                    'minmax':minmax,
                    'minmax_mean_peaks':minmax_mean_peaks,
                    'minmax_spline':minmax_integrated,
                    'length':length
                    }
        except ValueError:
            print(f'Unable to calculate envelope for swd {swd_uuid}')
            container.asymmetry[swd_uuid] = None
        
    # print(container.asymmetry)


def filter_data_by_state(tabs, data_type:str='spectrums') -> dict: 
    
    active_data = {} # filter spectrums by swd_selector checkboxes
    for uuid in tabs:
        tab = tabs[uuid]
        if data_type == 'spectrums':
            data = tab.welch
        elif data_type == 'swd':
            data = tab.swd_data
        else:
            raise NotImplementedError

        if data:
            active_tab = [v for k, v in data.items() if tab.swd_state[k]]

            active_tab = np.array(active_tab)
            if active_tab.size >0:
                active_data[uuid] = active_tab
    return active_data



def plot_conditions(tabs, canvas, 
                    plot_spread=False, plot_avg=False, 
                    plot_significance=False, stats_container = {}, nhst_test=False,
                    method=np.median):
    canvas.axes.clear()
    active_spectrums = filter_data_by_state(tabs) # filter spectrums byswd_selector checkboxes
    for uuid in tabs:
        tab = tabs[uuid]
        active_spectrums_tab = [v for k, v in tab.welch.items() if tab.swd_state[k]]
        active_spectrums_tab = np.array(active_spectrums_tab)
        if active_spectrums_tab.size >0:
            active_spectrums[uuid] = active_spectrums_tab
    avgs = []
    for uuid in active_spectrums:
    # for label in data['spectrums'].keys():
        sample = active_spectrums[uuid]
        x = tabs[uuid].spectrum_x
    # #     mask = [swd_state[label][i] for i in data['spectrum_id'][label]]
    # #     sample = sample[mask,:]
    # #     if sample.shape[0]:
        avg = method(sample, axis=0)
        avgs.append(avg)
        canvas.axes.plot(x, avg, label=tabs[uuid].dataset_name)
        if plot_spread:
            #TODO: different metrics of spread
            upper = np.quantile(sample, 0.75, axis=0)
            lower = np.quantile(sample, 0.25, axis=0)
            # upper = stats.median_abs_deviation(sample, axis=0)/2
            # lower = stats.median_abs_deviation(sample, axis=0)/2

            canvas.axes.fill_between(x, avg-lower, avg+upper, alpha=0.2)
    if len(active_spectrums):
        if plot_avg:
            canvas.axes.plot(x, method(np.array(avgs), axis=0), color='black', linewidth=3,
                                label=method.__name__)
        if plot_significance and nhst_test:
            for a in stats_container[nhst_test][0]:
                canvas.axes.axvline(x[a], color='grey', alpha=0.5)
    
    canvas.axes.legend(bbox_to_anchor=(0.5, 1), fontsize='xx-small')
    canvas.draw()
    canvas.flush_events()


def statistics_kw(container, correction:bool=True):
    fd = filter_data_by_state(container)
    fd = list(fd.values())
    
    kw = [stats.kruskal(*[b[:,a] for b in fd]) for a in range(fd[0].shape[-1])]

    p = np.array([a[1] for a in kw])
    
    if correction:
        p*=fd[0].shape[-1]
    significant_values = (np.where(p<0.05))[0]
    if not significant_values.shape[0]:
        print ('no signifncant values found')
    return significant_values, kw

def statistics_mw(container, correction:bool=True):

    fd = filter_data_by_state(container)
    # data_subset = {}
    # for swd_filepath_key in swd_state.keys():
    #     mask = [True if swd_state[swd_filepath_key][a] else False for a in data['spectrum_id'][swd_filepath_key] ]
    #     data_subset[swd_filepath_key] = data['spectrums'][swd_filepath_key][mask]
    data_list = [condition for condition in fd.values()]
    if len (data_list) <2:
        return [[],[]]

    mw = [stats.ttest_ind(data_list[0][:,a], data_list[1][:,a]) for a in range(data_list[0].shape[1])] # only 2!!!
    p = np.array([a[1] for a in mw])

    if correction:
        p*=data_list[0].shape[1]
    significant_values = (np.where(p<0.05))[0]
    if not significant_values.shape[0]:
        print ('no signifncant values found')
    return significant_values, mw

def timesrting_from_sample(sample_time, sfreq, level=None):
    """Create formatted string for EEG graph xticks with different zoom level

    Args:
        sample_time (_type_): sample number 
        sfreq (_type_): sampling frequency (Hz)
        level (_type_, optional): zoom level. Defaults to None.

    Returns:
        _type_: _description_
    """    
    if level == 'ms':
        ts = datetime.datetime.utcfromtimestamp(sample_time/sfreq).strftime("%H:%M:%S.%f")[:-3]
    elif level == 's':
        ts = datetime.datetime.utcfromtimestamp(sample_time/sfreq).strftime("%H:%M:%S")
    elif level == 'm':
        ts = datetime.datetime.utcfromtimestamp(sample_time/sfreq).strftime("%H:%M")
    return ts