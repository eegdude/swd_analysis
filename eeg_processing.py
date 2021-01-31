import mne
import pathlib
from scipy import signal, stats
import numpy as np
from matplotlib import pyplot as plt

def read_xdf_file(filename:pathlib.Path=None):
    if filename.suffix == '.bdf':
        raw = mne.io.read_raw_bdf(filename, preload=True)
    elif filename.suffix == '.edf':
        raw = mne.io.read_raw_edf(filename, preload=True)
    return raw

def filter_eeg(eeg:mne.io.RawArray):
    if eeg is not None:
        eeg = eeg.filter(3, 40, verbose=0)
    return eeg

def welch_spectrum(swds:dict, swd_state:dict, fs:float=250, nperseg:int=1000, noverlap:int=200, max_freq:float=30, normalize:bool=False):
    x = None
    welch_total = {}
    spectrum_id_total = {}
    for n, swd_file in enumerate(swds):
        if sum(swd_state[swd_file]):
            welch_single_file = []
            spectrum_id_single_file = []
            
            active_swd = [a for a, b in zip(swds[swd_file], swd_state[swd_file]) if b]
            for swd_id, swd in enumerate(active_swd):
                if len(swd) < nperseg:
                    print (f'dropped swd: length {len(swd)} samples is less than welch length {nperseg}')
                else:
                    w = signal.welch(swd, fs=fs, 
                        nperseg=nperseg, noverlap=noverlap, detrend=False)
                    x = w[0]
                    w = w[1]
                    
                    welch_single_file.append(w)
                    spectrum_id_single_file.append(swd_id)

            cutoff = sum(x <= max_freq)
            welch_single_file = np.array(welch_single_file)
            welch_single_file = welch_single_file[:,:cutoff]
            x = x[:cutoff]
            # welch_single_file = np.average(welch_single_file, axis=0).ravel()
            if normalize:
                welch_single_file/=np.max(welch_single_file)
            welch_total[swd_file] = welch_single_file
            spectrum_id_total[swd_file] = spectrum_id_single_file
    return {'x':x, 'spectrums':welch_total, 'spectrum_id':spectrum_id_total}

def plot_conditions(data:dict, swd_names:dict, canvas):
    canvas.axes.clear()
    x = data['x']
    if 'significance' in list(data.keys()):
        for a in data['significance']:
            canvas.axes.axvline(x[a], color='grey', alpha=0.5)
    for condition in data['spectrums'].items():
        upper = np.quantile(condition[1], 0.75, axis=0)
        lower = np.quantile(condition[1], 0.25, axis=0)
        avg = np.median(condition[1], axis=0)
        canvas.axes.plot(x, avg, label=swd_names[condition[0]])
        canvas.axes.fill_between(x, avg-lower, avg+upper, alpha=0.2)
    canvas.axes.legend(bbox_to_anchor=(0.5, 1), fontsize='xx-small')
    canvas.draw()
    canvas.flush_events()

def statistics_nonparametric(data:dict, correction:bool=True):
    if len(list(data['spectrums'].keys())) < 2:
        return [], []
    cc = [condition[1] for condition in data['spectrums'].items()] # only two
    aaa = [(cc[0][:,a], cc[1][:,a]) for a in range(cc[0].shape[1])]
    mw = [stats.ttest_ind(cc[0][:,a], cc[1][:,a]) for a in range(cc[0].shape[1])]
    # print (mw)
    p = np.array([a[1] for a in mw])
    if correction:
        p*=cc[0].shape[1]
    significant_values = (np.where(p<0.05))[0]
    if not significant_values.shape[0]:
        print ('no signifncant values found')
    return significant_values, mw