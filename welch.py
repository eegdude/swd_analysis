#%%
import pathlib
import pickle
import mne
from scipy import signal, stats
import argparse
import numpy as np
from matplotlib import pyplot as plt


def load_pickle(filepath:pathlib.Path=None):
    with open(filepath, 'rb') as f:
        l = pickle.load(f)
        return l

def average_welch(swds:list):
    ws = []
    for sw in swds:
        w = signal.welch(sw.get_data(), fs=sw.info['sfreq'], 
            nperseg=int(1*sw.info['sfreq']), noverlap=int(7*sw.info['sfreq']/8))
        ws.append(w)
    ws=[ws[0][0], np.array([a[1].ravel() for a in ws]).T]
    return ws

def plot_welch(welchs, labels:list, stats=None):
    for ws, label in zip(welchs, labels):
        print (ws[1].shape)
        y=np.average(ws[1], axis=0)
        std=np.std(ws[1], axis=0)

        # plt.plot(ws[0], ws[1])
        plt.fill_between(ws[0], y-std, y+std, alpha=0.8, label=label)
        plt.plot(ws[0], y, color='black')
    if stats:
        for s in stats:
            print(s, ws[0][s])
            
            plt.axvline(ws[0][s], alpha=0.2)
        pass
    
    plt.legend()
    plt.show()

def stats_welch(welchs):
    sign = []
    for b in range(welchs[0][1].shape[1]):
        st = stats.mannwhitneyu(welchs[0][1][:,b], welchs[1][1][:,b])
        if st[1]<0.05:#/welchs[0][1].shape[1]:
            sign.append(b)
    return sign

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('folder1', type=pathlib.Path, help='folder with pickles')
    parser.add_argument('folder2', type=pathlib.Path, help='folder with pickles')

    args = parser.parse_args()
    print (args.folder1)
    print (args.folder2)


    # for folder in args:
    #     print (folder)
    ww = []
    f1 = args.folder1.glob('*.pickle')
    f2 = args.folder2.glob('*.pickle')
    for folder in [f1, f2]:
        folder_w=[]
        for pickl in folder:
            l = load_pickle(pickl)
            w = average_welch(l)
            folder_w.append(w)
        ww.append(folder_w)
 
    ww_avg = []
    for folder in ww:
        ww_avg.append( [folder[0][0], 
                        np.array([np.average(a[1], axis=1) for a in folder])])

    s = stats_welch(ww_avg)
    plot_welch(ww_avg, labels=[args.folder1.name, args.folder2.name], stats=s)

#%%
