#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Fri Jul  3 13:38:36 2015

@author: madengr
"""

from gnuradio import gr
import osmosdr
from gnuradio import filter as grfilter # Don't redefine Python's filter()
from gnuradio import blocks
from gnuradio import fft
from gnuradio.fft import window
from gnuradio import analog
from gnuradio import audio
import os
import time
import numpy as np
from gnuradio.filter import pfb

class BaseTuner(gr.hier_block2):
    """Some base methods that are the same between the known tuner types.

    See TunerDemodNBFM and TunerDemodAM for better documentation.
    """

    def __init__(self):
        # Default values
        self.last_heard = 0
        self.file_name = None

    def get_last_heard():
        return self.last_heard

    def set_last_heard(self, a_time):
        self.last_heard = a_time

    def set_tuner_freq(self, tuner_freq, rf_center_freq):
        """Sets baseband center frequency and file name

        Sets baseband center frequency of frequency translating FIR filter
        Also sets file name of wave file sink
        If tuner is tuned to zero Hz then set to file name to None
        Otherwise set file name to tuned RF frequency in MHz

        Args:
            tuner_freq (float): Baseband tuner frequency in Hz
            rf_center_freq (float): RF center in Hz (for file name)
        """
        # Since the frequency (hence file name) changed, then close it
        if (self.record and self.file_name and 
                self.file_name != None):
            self.blocks_wavfile_sink.close()

        # If we did not write enough data to the wavfile sink, delete the file
        self._delete_wavfile_if_empty()

        # Set the frequency of the tuner
        self.tuner_freq = tuner_freq
        self.rf_center_freq = rf_center_freq
        self.freq_xlating_fir_filter_ccc.set_center_freq(self.tuner_freq)

        # Set the file name if recording
        if self.tuner_freq == 0 or not self.record:
            # If tuner at zero Hz, or record false, then file name to None
            self.file_name = None
        else:
            self.set_file_name(rf_center_freq)

        if (self.file_name != None and self.record):
            self.blocks_wavfile_sink.open(self.file_name)

    def set_file_name(self, rf_center_freq):
        self.rf_center_freq = rf_center_freq
        # Otherwise use frequency and time stamp for file name
        timestamp = int(time.time())
        tstamp = time.strftime("%Y%m%d_%H%M%S", time.localtime()) + "{:.3f}".format(time.time()%1)[1:]
        file_freq = (self.rf_center_freq + self.tuner_freq)/1E6
        file_freq = np.round(file_freq, 4)
        file_name = 'wav/' + '{:.4f}'.format(file_freq) + "_" + tstamp + ".wav"

        # Make sure the 'wav' directory exists
        # a better approach likely is checking existence instead of failing to create it
        try:
            os.mkdir('wav')
        except OSError:  # will need to add something here for Win support
            pass  # directory already exists

        self.file_name = file_name
        # timestamp the demod update to match filename
        self.time_stamp = timestamp

    def _delete_wavfile_if_empty(self):
        """Delete the current wavfile if it's empty."""
        if (not self.record or not self.file_name or
                self.file_name == None):
            return

        # If we never wrote any data to the wavfile sink, or its smaller than
        # the minimum defined size, then delete the (empty) wavfile
        if os.stat(self.file_name).st_size < (self.min_file_size):
            os.unlink(self.file_name)  # delete the file

    def set_squelch(self, squelch_db):
        """Sets the threshold for both squelches

        Args:
            squelch_db (float): Squelch in dB
        """
        self.analog_pwr_squelch_cc.set_threshold(squelch_db)

    def __del__(self):
        """Called when the object is destroyed."""
        # Make a best effort attempt to clean up our wavfile if it's empty
        try:
            self._delete_wavfile_if_empty()
        except Exception:
            pass  # oh well, we're dying anyway

class TunerDemodNBFM(BaseTuner):
    """Tuner, demodulator, and recorder chain for narrow band FM demodulation

    Kept as it's own class so multiple can be instantiated in parallel
    Accepts complex baseband samples at 1 Msps minimum
    Frequency translating FIR filter tunes from -samp_rate/2 to +samp_rate/2
    The following sample rates assume 1 Msps input
    First two stages of decimation are 5 each for a total of 25
    Thus first two stages brings 1 Msps down to 40 ksps
    The third stage decimates by int(samp_rate/1E6)
    Thus output rate will vary from 40 ksps to 79.99 ksps
    The channel is filtered to 12.5 KHz bandwidth followed by squelch
    The squelch is non-blocking since samples will be added with other demods
    The quadrature demod is followed by a fourth stage of decimation by 5
    This brings the sample rate down to 8 ksps to 15.98 ksps
    The audio is low-pass filtered to 3.5 kHz bandwidth
    The polyphase resampler resamples by samp_rate/(decims[1] * decims[0]**3)
    This results in a constant 8 ksps, irrespective of RF sample rate
    This 8 ksps audio stream may be added to other demod streams
    The audio is run through an additional blocking squelch at -200 dB
    This stops the sample flow so squelched audio is not recorded to file
    The wav file sink stores 8-bit samples (default/grainy quality but compact)
    Default demodulator center frequency is 0 Hz
    This is desired since hardware DC removal reduces sensitivity at 0 Hz
    NBFM demod of LO leakage will just be 0 amplitude

    Args:
        samp_rate (float): Input baseband sample rate in sps (1E6 minimum)
        audio_rate (float): Output audio sample rate in sps (8 kHz minimum)
        record (bool): Record audio to file if True
        audio_bps (int): Audio bit depth in bps (bits/samples)
        min_file_size (int): Minimum saved wav file size

    Attributes:
        center_freq (float): Baseband center frequency in Hz
        record (bool): Record audio to file if True
        time_stamp (int): Time stamp of demodulator start for timing run length
    """
    # pylint: disable=too-many-instance-attributes

    def __init__(self, samp_rate=4E6, audio_rate=8000, record=True,
                 audio_bps=8, min_file_size=0):
        gr.hier_block2.__init__(self, "TunerDemodNBFM",
                                gr.io_signature(1, 1, gr.sizeof_gr_complex),
                                gr.io_signature(1, 1, gr.sizeof_float))

        # Default values
        self.tuner_freq = 0
        self.rf_center_freq = 0
        self.time_stamp = 0
        squelch_db = -60
        self.quad_demod_gain = 0.050
        self.file_name = None
        self.record = record
        self.min_file_size = min_file_size
        self.last_heard = 0

        # Decimation values for four stages of decimation
        decims = (5, int(samp_rate/1E6))

        # Low pass filter taps for decimation by 5
        low_pass_filter_taps_0 = \
            grfilter.firdes.low_pass(1, 1, 0.090, 0.010,
                    window.WIN_HAMMING)

        # Frequency translating FIR filter decimating by 5
        self.freq_xlating_fir_filter_ccc = \
            grfilter.freq_xlating_fir_filter_ccc(decims[0],
                                                 low_pass_filter_taps_0,
                                                 self.tuner_freq, samp_rate)

        # FIR filter decimating by 5
        fir_filter_ccc_0 = grfilter.fir_filter_ccc(decims[0],
                                                   low_pass_filter_taps_0)

        # Low pass filter taps for decimation from samp_rate/25 to 40-79.9 ksps
        # In other words, decimation by int(samp_rate/1E6)
        # 12.5 kHz cutoff for NBFM channel bandwidth
        low_pass_filter_taps_1 = grfilter.firdes.low_pass(
            1, samp_rate/decims[0]**2, 12.5E3, 1E3, window.WIN_HAMMING)

        # FIR filter decimation by int(samp_rate/1E6)
        fir_filter_ccc_1 = grfilter.fir_filter_ccc(decims[1],
                                                   low_pass_filter_taps_1)

        # Non blocking power squelch
        self.analog_pwr_squelch_cc = analog.pwr_squelch_cc(squelch_db,
                                                           1e-1, 0, False)

        # Quadrature demod with gain set for decent audio
        # The gain will be later multiplied by the 0 dB normalized volume
        self.analog_quadrature_demod_cf = \
            analog.quadrature_demod_cf(self.quad_demod_gain)

        # 3.5 kHz cutoff for audio bandwidth
        low_pass_filter_taps_2 = grfilter.firdes.low_pass(1,\
                        samp_rate/(decims[1] * decims[0]**2),\
                        3.5E3, 500, window.WIN_HAMMING)

        # FIR filter decimating by 5 from 40-79.9 ksps to 8-15.98 ksps
        fir_filter_fff_0 = grfilter.fir_filter_fff(decims[0],
                                                   low_pass_filter_taps_2)

        # Polyphase resampler allows arbitary RF sample rates
        # Takes 8-15.98 ksps to a constant 8 ksps for audio
        pfb_resamp = audio_rate/float(samp_rate/(decims[1] * decims[0]**3))
        pfb_arb_resampler_fff = pfb.arb_resampler_fff(pfb_resamp, taps=None,
                                                      flt_size=32)

        # Connect the blocks for the demod
        self.connect(self, self.freq_xlating_fir_filter_ccc)
        self.connect(self.freq_xlating_fir_filter_ccc, fir_filter_ccc_0)
        self.connect(fir_filter_ccc_0, fir_filter_ccc_1)
        self.connect(fir_filter_ccc_1, self.analog_pwr_squelch_cc)
        self.connect(self.analog_pwr_squelch_cc,
                     self.analog_quadrature_demod_cf)
        self.connect(self.analog_quadrature_demod_cf, fir_filter_fff_0)
        self.connect(fir_filter_fff_0, pfb_arb_resampler_fff)
        self.connect(pfb_arb_resampler_fff, self)

        # Need to set this to a very low value of -200 since it is after demod
        # Only want it to gate when the previous squelch has gone to zero
        analog_pwr_squelch_ff = analog.pwr_squelch_ff(-200, 1e-1, 0, True)

        # Connect the blocks for recording
        self.connect(pfb_arb_resampler_fff, analog_pwr_squelch_ff)

        # File sink with single channel and bits/sample
        if (self.record):
            self.set_file_name(self.tuner_freq)
            self.blocks_wavfile_sink = blocks.wavfile_sink(self.file_name, 1,
                                                       audio_rate,
                                                       blocks.FORMAT_WAV,
                                                       blocks.FORMAT_PCM_16,
                                                       False)
            self.connect(analog_pwr_squelch_ff, self.blocks_wavfile_sink)
        else:
            null_sink1 = blocks.null_sink(gr.sizeof_float)
            self.connect(analog_pwr_squelch_ff, null_sink1)

    def set_volume(self, volume_db):
        """Sets the volume

        Args:
            volume_db (float): Volume in dB
        """
        gain = self.quad_demod_gain * 10**(volume_db/20.0)
        self.analog_quadrature_demod_cf.set_gain(gain)

class TunerDemodAM(BaseTuner):
    """Tuner, demodulator, and recorder chain for AM demodulation

    Kept as it's own class so multiple can be instantiated in parallel
    Accepts complex baseband samples at 1 Msps minimum
    Frequency translating FIR filter tunes from -samp_rate/2 to +samp_rate/2
    The following sample rates assume 1 Msps input
    First two stages of decimation are 5 each for a total of 25
    Thus first two stages brings 1 Msps down to 40 ksps
    The third stage decimates by int(samp_rate/1E6)
    Thus output rate will vary from 40 ksps to 79.99 ksps
    The channel is filtered to 12.5 KHz bandwidth followed by squelch
    The squelch is non-blocking since samples will be added with other demods
    The AGC sets level (volume) prior to AM demod
    The AM demod is followed by a fourth stage of decimation by 5
    This brings the sample rate down to 8 ksps to 15.98 ksps
    The audio is low-pass filtered to 3.5 kHz bandwidth
    The polyphase resampler resamples by samp_rate/(decims[1] * decims[0]**3)
    This results in a constant 8 ksps, irrespective of RF sample rate
    This 8 ksps audio stream may be added to other demod streams
    The audio is run through an additional blocking squelch at -200 dB
    This stops the sample flow so squelced audio is not recorded to file
    The wav file sink stores 8-bit samples (default/grainy quality but compact)
    Default demodulator center frequency is 0 Hz
    This is desired since hardware DC removal reduces sensitivity at 0 Hz
    AM demod of LO leakage will just be 0 amplitude

    Args:
        samp_rate (float): Input baseband sample rate in sps (1E6 minimum)
        audio_rate (float): Output audio sample rate in sps (8 kHz minimum)
        record (bool): Record audio to file if True
        audio_bps (int): Audio bit depth in bps (bits/samples)
        min_file_size (int): Minimum saved wav file size

    Attributes:
        tuner_freq (float): Baseband center frequency in Hz
        rf_center_freq (float): RF center frequency in Hz
        record (bool): Record audio to file if True
        time_stamp (int): Time stamp of demodulator start for timing run length
    """
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-locals

    def __init__(self, samp_rate=4E6, audio_rate=8000, record=True,
                 audio_bps=16):
        gr.hier_block2.__init__(self, "TunerDemodAM",
                                gr.io_signature(1, 1, gr.sizeof_gr_complex),
                                gr.io_signature(1, 1, gr.sizeof_float))

        # Default values
        self.tuner_freq = 0
        self.rf_center_freq = 0
        self.time_stamp = 0
        squelch_db = -60
        self.agc_ref = 0.1
        self.file_name = None
        self.record = record
        self.min_file_size = min_file_size
        self.last_heard = 0


        # Decimation values for four stages of decimation
        decims = (5, int(samp_rate/1E6))

        # Low pass filter taps for decimation by 5
        low_pass_filter_taps_0 = \
            grfilter.firdes.low_pass(1, 1, 0.090, 0.010,
                                     window.WIN_HAMMING)

        # Frequency translating FIR filter decimating by 5
        self.freq_xlating_fir_filter_ccc = \
            grfilter.freq_xlating_fir_filter_ccc(decims[0],
                                                 low_pass_filter_taps_0,
                                                 self.tuner_freq, samp_rate)

        # FIR filter decimating by 5
        fir_filter_ccc_0 = grfilter.fir_filter_ccc(decims[0],
                                                   low_pass_filter_taps_0)

        # Low pass filter taps for decimation from samp_rate/25 to 40-79.9 ksps
        # In other words, decimation by int(samp_rate/1E6)
        # 12.5 kHz cutoff for NBFM channel bandwidth
        low_pass_filter_taps_1 = grfilter.firdes.low_pass(
            1, samp_rate/decims[0]**2, 12.5E3, 1E3, window.WIN_HAMMING)

        # FIR filter decimation by int(samp_rate/1E6)
        fir_filter_ccc_1 = grfilter.fir_filter_ccc(decims[1],
                                                   low_pass_filter_taps_1)

        # Non blocking power squelch
        # Squelch level needs to be lower than NBFM or else choppy AM demod
        self.analog_pwr_squelch_cc = analog.pwr_squelch_cc(squelch_db,
                                                           1e-1, 0, False)

        # AGC with reference set for nomninal 0 dB volume
        # Paramaters tweaked to prevent impulse during squelching
        self.agc3_cc = analog.agc3_cc(1.0, 1E-4, self.agc_ref, 10, 1)
        self.agc3_cc.set_max_gain(65536)

        # AM demod with complex_to_mag()
        # Can't use analog.am_demod_cf() since it won't work with N>2 demods
        am_demod_cf = blocks.complex_to_mag(1)

        # 3.5 kHz cutoff for audio bandwidth
        low_pass_filter_taps_2 = grfilter.firdes.low_pass(1,\
                        samp_rate/(decims[1] * decims[0]**2),\
                        3.5E3, 500, window.WIN_HAMMING)

        # FIR filter decimating by 5 from 40-79.9 ksps to 8-15.98 ksps
        fir_filter_fff_0 = grfilter.fir_filter_fff(decims[0],
                                                   low_pass_filter_taps_2)

        # Polyphase resampler allows arbitary RF sample rates
        # Takes 8-15.98 ksps to a constant 8 ksps for audio
        pfb_resamp = audio_rate/float(samp_rate/(decims[1] * decims[0]**3))
        pfb_arb_resampler_fff = pfb.arb_resampler_fff(pfb_resamp, taps=None,
                                                      flt_size=32)

        # Connect the blocks for the demod
        self.connect(self, self.freq_xlating_fir_filter_ccc)
        self.connect(self.freq_xlating_fir_filter_ccc, fir_filter_ccc_0)
        self.connect(fir_filter_ccc_0, fir_filter_ccc_1)
        self.connect(fir_filter_ccc_1, self.analog_pwr_squelch_cc)
        self.connect(self.analog_pwr_squelch_cc, self.agc3_cc)
        self.connect(self.agc3_cc, am_demod_cf)
        self.connect(am_demod_cf, fir_filter_fff_0)
        self.connect(fir_filter_fff_0, pfb_arb_resampler_fff)
        self.connect(pfb_arb_resampler_fff, self)

        # Need to set this to a very low value of -200 since it is after demod
        # Only want it to gate when the previous squelch has gone to zero
        analog_pwr_squelch_ff = analog.pwr_squelch_ff(-200, 1e-1, 0, True)

        # Connect the blocks for recording
        self.connect(pfb_arb_resampler_fff, analog_pwr_squelch_ff)

        # File sink with single channel and 8 bits/sample
        if (self.record):
            self.set_file_name(self.tuner_freq, self.rf_center_freq)
            self.blocks_wavfile_sink = blocks.wavfile_sink(self.file_name, 1,
                                                       audio_rate,
                                                       blocks.FORMAT_WAV,
                                                       blocks.FORMAT_PCM_16,
                                                       False)
            self.connect(analog_pwr_squelch_ff, self.blocks_wavfile_sink)
        else:
            null_sink1 = blocks.null_sink(gr.sizeof_float)
            self.connect(analog_pwr_squelch_ff, null_sink1)

    def set_volume(self, volume_db):
        """Sets the volume

        Args:
            volume_db (float): Volume in dB
        """
        agc_ref = self.agc_ref * 10**(volume_db/20.0)
        self.agc3_cc.set_reference(agc_ref)

class Receiver(gr.top_block):
    """Receiver for NBFM and AM modulation

    Controls hardware and instantiates multiple tuner/demodulators
    Generates FFT power spectrum for channel estimation

    Args:
        ask_samp_rate (float): Asking sample rate of hardware in sps (1E6 min)
        num_demod (int): Number of parallel demodulators
        type_demod (int): Type of demodulator (0=NBFM, 1=AM)
        hw_args (string): Argument string to pass to hardware
        freq_correction (int): Frequency correction in ppm
        record (bool): Record audio to file if True
        audio_bps (int): Audio bit depth in bps (bits/samples)

    Attributes:
        center_freq (float): Hardware RF center frequency in Hz
        samp_rate (float): Hardware sample rate in sps (1E6 min)
        gain_db (int): Hardware RF gain in dB
        squelch_db (int): Squelch in dB
        volume_dB (int): Volume in dB
    """
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-arguments

    def __init__(self, ask_samp_rate=4E6, num_demod=4, type_demod=0,
                 hw_args="uhd", freq_correction=0, record=True, play=True,
                 audio_bps=16, min_file_size=0):

        # Call the initialization method from the parent class
        gr.top_block.__init__(self, "Receiver")

        # Default values
        self.center_freq = 146E6
        self.gain_db = 0
        self.squelch_db = -60
        self.volume_db = 0
        audio_rate = 8000
        self.min_file_size = min_file_size

        # Setup the USRP source, or use the USRP sim
        self.src = osmosdr.source(args="numchan=" + str(1) + " " + hw_args)
        self.src.set_sample_rate(ask_samp_rate)
        self.src.set_center_freq(self.center_freq)
        self.src.set_freq_corr(freq_correction)

        # Get the sample rate and center frequency from the hardware
        self.samp_rate = self.src.get_sample_rate()
        self.center_freq = self.src.get_center_freq()

        # Set the I/Q bandwidth to 80 % of sample rate
        self.src.set_bandwidth(0.8 * self.samp_rate)

        # NBFM channel is about 10 KHz wide
        # Want  about 3 FFT bins to span a channel
        # Use length FFT so 4 Msps / 1024 = 3906.25 Hz/bin
        # This also means 3906.25 vectors/second
        # Using below formula keeps FFT size a power of two
        # Also keeps bin size constant for power of two sampling rates
        # Use of 256 sets 3906.25 Hz/bin; increase to reduce bin size
        samp_ratio = self.samp_rate / 1E6
        fft_length = 256 * int(pow(2, np.ceil(np.log(samp_ratio)/np.log(2))))

        # -----------Flow for FFT--------------

        # Convert USRP steam to vector
        stream_to_vector = blocks.stream_to_vector(gr.sizeof_gr_complex*1,
                                                   fft_length)

        # Want about 1000 vector/sec
        amount = int(round(self.samp_rate/fft_length/1000))
        keep_one_in_n = blocks.keep_one_in_n(gr.sizeof_gr_complex*
                                             fft_length, amount)

        # Take FFT
        fft_vcc = fft.fft_vcc(fft_length, True,
                              window.blackmanharris(fft_length), True, 1)

        # Compute the power
        complex_to_mag_squared = blocks.complex_to_mag_squared(fft_length)

        # Video average and decimate from 1000 vector/sec to 10 vector/sec
        integrate_ff = blocks.integrate_ff(100, fft_length)

        # Probe vector
        self.probe_signal_vf = blocks.probe_signal_vf(fft_length)

        # Connect the blocks
        self.connect(self.src, stream_to_vector, keep_one_in_n,
                     fft_vcc, complex_to_mag_squared,
                     integrate_ff, self.probe_signal_vf)

        # -----------Flow for Demod--------------

        # Create N parallel demodulators as a list of objects
        # Default to NBFM demod
        self.demodulators = []
        for idx in range(num_demod):
            if type_demod == 1:
                self.demodulators.append(TunerDemodAM(self.samp_rate,
                                                      audio_rate, record,
                                                      audio_bps, self.min_file_size))
            else:
                self.demodulators.append(TunerDemodNBFM(self.samp_rate,
                                                        audio_rate, record,
                                                        audio_bps, self.min_file_size))

        if play:
            # Create an adder
            add_ff = blocks.add_ff(1)

            # Connect the demodulators between the source and adder
            for idx, demodulator in enumerate(self.demodulators):
                self.connect(self.src, demodulator, (add_ff, idx))

            # Audio sink
            audio_sink = audio.sink(audio_rate)

            # Connect the summed outputs to the audio sink
            self.connect(add_ff, audio_sink)
        else:
            # Just connect each demodulator to the receiver source
            for demodulator in self.demodulators:
                self.connect(self.src, demodulator)

    def set_center_freq(self, center_freq):
        """Sets RF center frequency of hardware

        Args:
            center_freq (float): Hardware RF center frequency in Hz
        """
        # Tune the hardware
        self.src.set_center_freq(center_freq)

        # Update center frequency with hardware center frequency
        # Do this to account for slight hardware offsets
        self.center_freq = self.src.get_center_freq()

    def get_gain_names(self):
        """Get the list of suppoted gain elements
        """
        return self.src.get_gain_names()

    def filter_and_set_gains(self, all_gains):
        """Remove unsupported gains and set them
        Args:
            all_gains (list of dictionary): Supported gains in dB
        """
        gains = []
        names = self.get_gain_names()
        for gain in all_gains:
            if gain["name"] in names:
                gains.append(gain)
        return self.set_gains(gains)

    def set_gains(self, gains):
        """Set all the gains
        Args:
            gains (list of dictionary): Supported gains in dB
        """
        for gain in gains:
            self.src.set_gain(gain["value"], gain["name"])
            if gain["query"] == "yes":
                gain["value"] = self.src.get_gain(gain["name"])
        self.gains = gains
        return self.gains

    def set_squelch(self, squelch_db):
        """Sets squelch of all demodulators and clamps range

        Args:
            squelch_db (float): Squelch in dB
        """
        self.squelch_db = max(min(0, squelch_db), -100)
        for demodulator in self.demodulators:
            demodulator.set_squelch(self.squelch_db)

    def set_volume(self, volume_db):
        """Sets volume of all demodulators and clamps range

        Args:
            volume_db (float): Volume in dB
        """
        self.volume_db = max(min(20, volume_db), -20)
        for demodulator in self.demodulators:
            demodulator.set_volume(self.volume_db)

    def get_demod_freqs(self):
        """Gets baseband frequencies of all demodulators

        Returns:
            List[float]: List of baseband center frequencies in Hz
        """
        tuner_freqs = []
        for demodulator in self.demodulators:
            tuner_freqs.append(demodulator.tuner_freq)
        return tuner_freqs


def main():
    """Test the receiver

    Sets up the hardware
    Tunes a couple of demodulators
    Prints the max power spectrum
    """

    # Create receiver object
    ask_samp_rate = 2E6
    num_demod = 4
    type_demod = 0
    hw_args = "uhd"
    freq_correction = 0
    record = False
    play = True
    audio_bps = 8
    min_file_size = 0
    receiver = Receiver(ask_samp_rate, num_demod, type_demod, hw_args,
                        freq_correction, record, play, audio_bps, min_file_size)

    # Start the receiver and wait for samples to accumulate
    receiver.start()
    time.sleep(1)

    # Set frequency, gain, squelch, and volume
    center_freq = 144.5E6
    receiver.set_center_freq(center_freq)
    print("\n")
    print("Started %s at %.3f Msps" % (hw_args, receiver.samp_rate/1E6))
    print("RX at %.3f MHz" % (receiver.center_freq/1E6))
    receiver.filter_and_set_gains(parser.gains)
    for gain in receiver.gains:
        print("gain %s at %d dB" % (gain["name"], gain["value"]))
    receiver.set_squelch(-60)
    receiver.set_volume(0)
    print("%d demods of type %d at %d dB squelch and %d dB volume" % \
        (num_demod, type_demod, receiver.squelch_db, receiver.volume_db))

    # Create some baseband channels to tune based on 144 MHz center
    channels = np.zeros(num_demod)
    channels[0] = 144.39E6 - receiver.center_freq # APRS
    channels[1] = 144.6E6 - receiver.center_freq

    # Tune demodulators to baseband channels
    # If recording on, this creates empty wav file since manually tuning.
    for idx, demodulator in enumerate(receiver.demodulators):
        demodulator.set_tuner_freq(channels[idx], center_freq)

    # Print demodulator info
    for idx, channel in enumerate(channels):
        print("Tuned demod %d to %.3f MHz" % (idx,
                                              (channel+receiver.center_freq)
                                              /1E6))

    while 1:
        # No need to go faster than 10 Hz rate of GNU Radio probe
        # Just do 1 Hz here
        time.sleep(1)

        # Grab the FFT data and print max value
        spectrum = receiver.probe_signal_vf.level()
        print("Max spectrum of %.3f" % (np.max(spectrum)))

    # Stop the receiver
    receiver.stop()
    receiver.wait()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
