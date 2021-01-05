#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Sat Jul 18 15:21:33 2015

@author: madengr
"""

from optparse import OptionParser
from gnuradio.eng_option import eng_option

class CLParser(object):
    """Command line parser

    Attributes:
        hw_args (string): Argument string to pass to harwdare
        num_demod (int): Number of parallel demodulators
        center_freq (float): Hardware RF center frequency in Hz
        ask_samp_rate (float): Asking sample rate of hardware in sps (1E6 min)
        gain_db (int): Hardware RF gain in dB
        squelch_db (int): Squelch in dB
        volume_dB (int): Volume in dB
        threshold_dB (int): Threshold for channel detection in dB
        record (bool): Record audio to file if True
        play (bool): Play audio through speaker if True
        lockout_file_name (string): Name of file with channels to lockout
        priority_file_name (string): Name of file with channels to for priority
        channel_log_file_name (string): Name of file for channel logging
        channel_log_timeout (int): Timeout delay between active channel log entries
        freq_correction (int): Frequency correction in ppm
        audio_bps (int): Audio bit depth in bps
        max_db (float): Spectrum max dB for display
        min_db (float): Spectrum min dB for display
    """
    # pylint: disable=too-few-public-methods
    # pylint: disable=too-many-instance-attributes

    def __init__(self):

        # Setup the parser for command line arguments
        parser = OptionParser(option_class=eng_option)

        parser.add_option("-a", "--args", type="string", dest="hw_args",
                          default='uhd',
                          help="Hardware args")

        parser.add_option("-n", "--demod", type="int", dest="num_demod",
                          default=4,
                          help="Number of demodulators")

        parser.add_option("-d", "--demodulator", type="int", dest="type_demod",
                          default=0,
                          help="Type of demodulator (0=NBFM, 1=AM)")

        parser.add_option("-f", "--freq", type="string", dest="center_freq",
                          default=146E6,
                          help="Hardware RF center frequency in Hz")

        parser.add_option("-r", "--rate", type="string", dest="ask_samp_rate",
                          default=4E6,
                          help="Hardware ask sample rate in sps (1E6 minimum)")

        parser.add_option("-g", "--gain", type="eng_float", dest="rf_gain_db",
                          default=0, help="Hardware RF gain in dB")

        parser.add_option("-i", "--if_gain", type="eng_float", dest="if_gain_db",
                          default=16, help="Hardware IF gain in dB or index (driver dependent)")

        parser.add_option("-o", "--bb_gain", type="eng_float", dest="bb_gain_db",
                          default=16, help="Hardware BB gain in dB")

        parser.add_option("-j", "--lna_gain", type="eng_float", dest="lna_gain_db",
                          default=8, help="Hardware LNA gain index")

        parser.add_option("-x", "--mix_gain", type="eng_float", dest="mix_gain_db",
                          default=5, help="Hardware MIX gain index")

        parser.add_option("-s", "--squelch", type="eng_float",
                          dest="squelch_db", default=-60,
                          help="Squelch in dB")

        parser.add_option("-v", "--volume", type="eng_float",
                          dest="volume_db", default=0,
                          help="Volume in dB")

        parser.add_option("-t", "--threshold", type="eng_float",
                          dest="threshold_db", default=10,
                          help="Threshold in dB")

        parser.add_option("-w", "--write",
                          dest="record", default=False, action="store_true",
                          help="Record (write) channels to disk")

        parser.add_option("-l", "--lockout", type="string",
                          dest="lockout_file_name",
                          default="",
                          help="File of EOL delimited lockout channels in Hz")

        parser.add_option("-p", "--priority", type="string",
                          dest="priority_file_name",
                          default="",
                          help="File of EOL delimited priority channels in Hz")

        parser.add_option("-L", "--log_file", type="string",
                           dest="channel_log_file_name",
                           default="",
                           help="Log file for channel detection")

        parser.add_option("-A", "--log_active_timeout", type="int",
                           dest="channel_log_timeout",
                           default=15,
                           help="Timeout delay for active channel log entries")

        parser.add_option("-c", "--correction", type="int", dest="freq_correction",
                          default=0,
                          help="Frequency correction in ppm")

        parser.add_option("-m", "--mute-audio", dest="play",
                          action="store_false", default=True,
                          help="Mute audio from speaker (still allows recording)")

        parser.add_option("-b", "--bps", type="int", dest="audio_bps",
                          default=8,
                          help="Audio bit depth (bps)")
        
        parser.add_option("-M", "--max_db", type="float", dest="max_db",
                          default=50,
                          help="Spectrum window max dB for display")
        
        parser.add_option("-N", "--min_db", type="float", dest="min_db",
                          default=-10,
                          help="Spectrum window min dB for display (no greater than -10dB from max")
        
        parser.add_option("-k", "--max-demod-length", type="int", dest="max_demod_length",
                          default=0,
                          help="Maxumum length for a demodulation (sec)")

        options = parser.parse_args()[0]
        self.parser_args = parser.parse_args()[1]

        self.hw_args = str(options.hw_args)
        self.num_demod = int(options.num_demod)
        self.type_demod = int(options.type_demod)
        self.center_freq = float(options.center_freq)
        self.ask_samp_rate = float(options.ask_samp_rate)

        self.gains = [
            { "name": "RF", "value": float(options.rf_gain_db),  "query": "yes" },
            { "name": "LNA","value": float(options.lna_gain_db), "query": "no" },
            { "name": "MIX","value": float(options.mix_gain_db), "query": "no" },
            { "name": "IF", "value": float(options.if_gain_db),  "query": "no" },
            { "name": "BB", "value": float(options.bb_gain_db),  "query": "no" }
        ]

        self.squelch_db = float(options.squelch_db)
        self.volume_db = float(options.volume_db)
        self.threshold_db = float(options.threshold_db)
        self.record = bool(options.record)
        self.play = bool(options.play)
        self.lockout_file_name = str(options.lockout_file_name)
        self.priority_file_name = str(options.priority_file_name)
        self.channel_log_file_name = str(options.channel_log_file_name)
        self.channel_log_timeout = int(options.channel_log_timeout)
        self.freq_correction = int(options.freq_correction)
        self.audio_bps = int(options.audio_bps)
        self.max_db = float(options.max_db)
        self.min_db = float(options.min_db)
        self.max_demod_length = int(options.max_demod_length)


def main():
    """Test the parser"""

    parser = CLParser()

    if len(parser.parser_args) != 0:
        parser.print_help() #pylint: disable=maybe-no-member
        raise(SystemExit, 1)

    print("hw_args:             " + parser.hw_args)
    print("num_demod:           " + str(parser.num_demod))
    print("type_demod:          " + str(parser.type_demod))
    print("center_freq:         " + str(parser.center_freq))
    print("ask_samp_rate:       " + str(parser.ask_samp_rate))
    for gain in parser.gains:
        print("gain %s at %d dB" % (gain["name"], gain["value"]))
    print("squelch_db:          " + str(parser.squelch_db))
    print("volume_db:           " + str(parser.volume_db))
    print("threshold_db:        " + str(parser.threshold_db))
    print("record:              " + str(parser.record))
    print("lockout_file_name:   " + str(parser.lockout_file_name))
    print("priority_file_name:  " + str(parser.priority_file_name))
    print("channel_log_file_name:  " + str(parser.channel_log_file_name))
    print("channel_log_timeout:  " + str(parser.channel_log_timeout))
    print("freq_correction:     " + str(parser.freq_correction))
    print("audio_bps:           " + str(parser.audio_bps))
    print("max_db:              " + str(parser.max_db))
    print("min_db:              " + str(parser.min_db))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

