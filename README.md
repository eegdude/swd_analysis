# super-chainsaw
Software for semi-manual segment spectal analysis of EEG signal.
Created for epileptic spike-wave discharge (SWD) analysis in rats.

## Analysis pipeline

Open EEG file (.edf), create annotations of fragment of interest. Fragments are saved in intermediate files.
Each created fragment is marked with its unique UUID for the rest of the analysis for traceablilty.
At the processing stage, spectral features may be calculated, and are stored in the same intermediate file. 
At the batch processing stage, groups of files are selected and average spectral features per file are treted as independent samples for comparison (with multiple comparison correction)


