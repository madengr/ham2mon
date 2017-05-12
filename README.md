# HAM2MON
This is a GNU Radio (GR) based SDR scanner with a Curses interface, primarily meant for monitoring amateur radio narrow-band FM modulation and air-band AM modulation.  It should work with any GrOsmoSDR source capable of at least 1 Msps.  Unlike conventional radio scanners that lock and demodulate a single channel, this SDR scanner can demodulate and record audio from N channels in parallel within the digitizing bandwidth.  The N (number of) channels is basically just limited by processor speed.  A video detailing the project may be found here:

http://youtu.be/BXptQFSV8E4

![GUI screenshot](https://github.com/madengr/ham2mon/blob/master/ham2mon.png)

## Tested with:
- Ettus B200 at 16 Msps (http://www.ettus.com)
- NooElec RTL2832 + R820T at 2 Msps (http://www.nooelec.com)
- GNU Radio 3.7.10 (https://github.com/gnuradio/gnuradio)
- GrOsmoSDR 0.1.4 (http://sdr.osmocom.org/trac/wiki/GrOsmoSDR)
- Ettus UHD 3.10.0 (https://github.com/EttusResearch/uhd)

## Contributors:

m0mik:
- Added HackRF IF/BB gain parameters
- Added 1dB shift option to threshold and gain settings

atpage:
- Fixed typos

john:
- Frequency correction option switch
- Read from I/Q file documentation
- Bits per audio sample (bps) option switch

lachesis:
- Mute switch
- Simplified TunerDemod class
- Removed 44 byte header-only files

madengr:
- Initial code
- AM demodulation
- Priority channels

## Console Operation:

The following is an example of the option switches for UHD with NBFM demodulation, although omission of any will use default values (shown below) that are optimal for the B200:

./ham2mon.py -a "uhd" -n 8 -d 0 -f 146E6 -r 4E6 -g 30 -s -60 -v 0 -t 10 -w

The following is an example of the option switches for UHD with AM demodulation, primarily meant for VHF air band reception.  Note the squelch has been lowered 10 dB to aid with weak AM detection:

./ham2mon.py -a "uhd" -n 8 -d 1 -f 135E6 -r 4E6 -g 30 -s -70 -v 0 -t 10 -w

The following is an example of the option switches for RTL2832U.  Note the sample rate, squelch, and threshold have changed to reflect the reduced (8-bit) dynamic range of the RTL dongles compared to Ettus SDRs.  In addition, these devices have poor IMD and image suppression, so strong signals may cause false demodulator locks:

./ham2mon.py -a "rtl" -n 4 -f 145E6 -r 2E6 -g 20 -s -40 -v 0 -t 30 -w

Note that sometimes default RTL kernel driver (for receiving dvb) must be disabled.  Google "rtl sdr blacklist" to read more about this issue, or just do this:

sudo rmmod dvb_usb_rtl28xxu

Example of reading from an IQ file:

./ham2mon.py -a "file=gqrx.raw,rate=8E6,repeat=false,throttle=true,freq=466E6" -r 8E6 -w

## GUI Controls:

`t/r = Detection threshold +/- 5 dB. (T/R for +/- 1dB)`

`p/o = Spectrum upper scale +/- 10 dB`

`w/q = Spectrum lower scale +/- 10 dB`

`g/f = RF gain +/- 10 dB (G/F for +/- 1dB)`

`u/y = IF Gain +/- 10 dB (U/Y for +/- 1dB)`

`]/[ = BB Gain +/- 10 dB (}/{ for +/- 1dB)`

`s/a = Squelch +/- 1 dB`

`./, = Volume +/- 1 dB`

`k/j = RF center frequency +/- 100 kHz`

`m/n = RF center frequency +/- 1 MHz`

`v/c = RF center frequency +/- 10 MHz`

`x/z = RF center frequency +/- 100 MHz`

`0..9 = Lockout channel (must press during reception)`

`l = Clear lockouts`

`CTRL-C = quit`

## Help Menu

`Usage: ham2mon.py [options]`

`Options:`

`  -h, --help            show this help message and exit`

`  -a HW_ARGS, --args=HW_ARGS`
`                        Hardware args`

`  -n NUM_DEMOD, --demod=NUM_DEMOD`
`                        Number of demodulators`

`  -d TYPE_DEMOD, --demodulator=TYPE_DEMOD`
`                        Type of demodulator (0=NBFM, 1=AM)`

`  -f CENTER_FREQ, --freq=CENTER_FREQ`
`                        Hardware RF center frequency in Hz`

`  -r ASK_SAMP_RATE, --rate=ASK_SAMP_RATE`
`                        Hardware ask sample rate in sps (1E6 minimum)`

`  -g GAIN_DB, --gain=GAIN_DB`
`                        Hardware RF gain in dB`

`  -i IF_GAIN_DB, --if_gain=IF_GAIN_DB`
`                        Hardware IF gain in dB`

`  -o BB_GAIN_DB, --bb_gain=BB_GAIN_DB`
`                        Hardware BB gain in dB`

`  -s SQUELCH_DB, --squelch=SQUELCH_DB`
`                        Squelch in dB`

`  -v VOLUME_DB, --volume=VOLUME_DB`
`                        Volume in dB`

`  -t THRESHOLD_DB, --threshold=THRESHOLD_DB`
`                        Threshold in dB`

`  -w, --write           Record (write) channels to disk`

`  -l LOCKOUT_FILE_NAME, --lockout=LOCKOUT_FILE_NAME`
`                        File of EOL delimited lockout channels in Hz`

`  -p PRIORITY_FILE_NAME, --priority=PRIORITY_FILE_NAME`
`                        File of EOL delimited priority channels in Hz`

`  -c FREQ_CORRECTION, --correction=FREQ_CORRECTION`
`                        Frequency correction in ppm`

`  -m, --mute-audio      Mute audio from speaker (still allows recording)`

`  -b AUDIO_BPS, --bps=AUDIO_BPS`
`                        Audio bit depth (bps)`


## Description:
The high speed signal processing is done in GR and the logic & control in Python. There are no custom GR blocks.  The GUI is written in Curses and is meant to be lightweight.  See the video for a basic overview.  I attempted to make the program very object oriented and “Pythonic”.  Each module runs on it's own for testing purposes.

![GRC screenshot](https://github.com/madengr/ham2mon/blob/master/flow_example.png)

See the flow_example.grc for an example of the GR flow, and receiver.py for the Python coded flow.  The complex samples are grouped into a vector of length 2^n and then decimated by keeping “1 in N” vectors. The FFT is taken followed by magnitude-squared to form a power spectrum.  The FFT length is chosen, based on sample rate, to span about 3 RBW bins across a 12.5 kHz FM channel.  The spectrum vectors are then integrated and further decimated for a video average, akin to the VBW of a spectrum analyzer.  The spectrum is then probed by the Python code at ~10 Hz rate.

The demodulator blocks are put into a hierarchical GR block so multiple can be instantiated in parallel.  A frequency translating FIR filter tunes the channel, followed by two more decimating FIR filters to 12.5 kHz channel bandwidth.  For sample rates 1 Msps or greater, the total decimation for the first three stages takes the rate to 40-80 ksps.  A non-blocking power squelch silences the channel, followed by quadrature (FM) demodulation, or AGC and AM demodulation.  The audio stream is filtered to 3.5 kHz bandwidth and further decimated to 8-16 ksps.  A polyphase arbitrary resampler takes the final audio rate to a constant 8 ksps.  The audio can then be mixed with other streams, or sunk to WAV file via a blocking squelch to remove dead audio.

The scanner.py contains the control code, and may be run on on it's own non-interactively.  It instantiates the receiver.py with N demodulators and probes the average spectrum at ~10 Hz.  The spectrum is processed with estimate.py, which takes a weighted average of the spectrum bins that are above a threshold.  This weighted average does a fair job of estimating the modulated channel center to sub-kHz resolution given the RBW is several kHz.  The estimate.py returns a list of baseband channels that are rounded to the nearest 5 kHz (for NBFM band plan ambiguity).

The lockout channels are removed from the list, priority channels bumped to the front, and the list used to tune the demodulators.  The demodulators are only tuned if the channel has ceased activity from the last probe, otherwise the demodulator is held on the channel.  Files, thus time stamps, are only re-written when the demodulator has moved, therefore priority channels are only time stamped at program start.  The demodulators are parked at 0 Hz baseband when not tuned, as this provides a constant, low amplitude signal due to FM demod of LO leakage.

The ham2mon.py interfaces the scanner.py with the curses.py GUI.  The GUI provides a spectral display with adjustable scaling and detector threshold line.  The center frequency, gain, squelch, and volume can be adjusted in real time, as well as adding channel lockouts.  The hardware arguments, sample rate, number of demodulators, recording status, and lockout file are set via switches at run time.

The default settings are optimized for an Ettus B200.  The RTL dongle will require raising the squelch and adjustment of the spectrum scale and threshold.

The next iteration of this program will probably use gr-dsd to decode P25 public safety in the 800 MHz band.
