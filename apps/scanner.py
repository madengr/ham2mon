#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Fri Jul  3 13:38:36 2015

@author: madengr
"""

import receiver as recvr
import estimate
import parser as prsr
import time
import numpy as np
import sys
import types
import datetime
import errors as err

PY3 = sys.version_info[0] == 3
PY2 = sys.version_info[0] == 2

if PY3:
    import builtins
    # list-producing versions of the major Python iterating functions
    def lrange(*args, **kwargs):
        return list(range(*args, **kwargs))

    def lzip(*args, **kwargs):
        return list(zip(*args, **kwargs))

    def lmap(*args, **kwargs):
        return list(map(*args, **kwargs))

    def lfilter(*args, **kwargs):
        return list(filter(*args, **kwargs))
else:
    import __builtin__
    # Python 2-builtin ranges produce lists
    lrange = __builtin__.range
    lzip = __builtin__.zip
    lmap = __builtin__.map
    lfilter = __builtin__.filter


class Scanner(object):
    """Scanner that controls receiver

    Estimates channels from FFT power spectrum that are above threshold
    Rounds channels to nearest 5 kHz
    Removes channels that are locked out
    Tunes demodulators to new channels
    Holds demodulators on channels between scan cycles

    Args:
        ask_samp_rate (float): Asking sample rate of hardware in sps (1E6 min)
        num_demod (int): Number of parallel demodulators
        type_demod (int): Type of demodulator (0=NBFM, 1=AM)
        hw_args (string): Argument string to pass to harwdare
        freq_correction (int): Frequency correction in ppm
        record (bool): Record audio to file if True
        lockout_file_name (string): Name of file with channels to lockout
        priority_file_name (string): Name of file with channels for priority
        channel_log_file_name (string): Name of file with channel log entries
        channel_log_timeout (int): Timeout delay between active channel entries in log
        audio_bps (int): Audio bit depth in bps (bits/samples)
        max_demod_length (int): Maximum demod time in seconds (0=disable)
        center_freq (int): initial center frequency for receiver (Hz)
        freq_low (int): Freq below which we won't tune a receiver (Hz)
        freq_high (int): Freq above which we won't tune a receiver (Hz)
        spacing (int): granularity of frequency quantization

    Attributes:
        center_freq (float): Hardware RF center frequency in Hz
        low_bound (int): Freq below which we won't tune a receiver (Hz)
        high_bound (int): Freq above which we won't tune a receiver (Hz)
        samp_rate (float): Hardware sample rate in sps (1E6 min)
        gains : Enumerated gain types and values
        squelch_db (int): Squelch in dB
        volume_dB (int): Volume in dB
        threshold_dB (int): Threshold for channel detection in dB
        spectrum (numpy.ndarray): FFT power spectrum data in linear, not dB
        lockout_channels [float]: List of baseband lockout channels in Hz
        priority_channels [float]: List of baseband priority channels in Hz
        gui_tuned_channels [str] List of tuned RF channels in MHz for GUI
        gui_active_channels [str] List of active RF channels in MHz for GUI (currently above threshold)
        gui_tuned_lockout_channels [str]: List of lockout channels in MHz GUI
        channel_spacing (float):  Spacing that channels will be rounded
        lockout_file_name (string): Name of file with channels to lockout
        priority_file_name (string): Name of file with channels for priority
        channel_log_file_name (string): Name of file with channel log entries
        channel_log_timeout (int): Timeout delay between active channel entries in log
        log_timeout_last (int): Last timestamp when recently active channels were logged and cleared
        max_demod_length (int): Maximum demod time in seconds (0=disable)
    """
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments

    def __init__(self, ask_samp_rate=4E6, num_demod=4, type_demod=0,
                 hw_args="uhd", freq_correction=0, record=True,
                 lockout_file_name="", priority_file_name="",
                 channel_log_file_name="", channel_log_timeout=15,
                 play=True,
                 audio_bps=8, max_demod_length=0, channel_spacing=5000,
                 min_file_size=0, center_freq=0, freq_low=0, freq_high=2000000000):

        # Default values
        self.squelch_db = -60
        self.volume_db = 0
        self.threshold_db = 10
        self.record = record
        self.play = play
        self.audio_bps = audio_bps
        self.freq_low = freq_low
        self.freq_high = freq_high
        self.center_freq = center_freq
        self.spectrum = []
        self.lockout_channels = []
        self.priority_channels = []
        self.active_channels = []
        self.unordered_active_channels = []
        self.ordered_active_channels = []
        self.power_ordered_active_channels = []
        self.ordered_active_channels_freqs = []
        self.gui_tuned_channels = []
        self.gui_active_channels = []
        self.gui_lockout_channels = []
        self.channel_spacing = channel_spacing
        self.lockout_file_name = lockout_file_name
        self.priority_file_name = priority_file_name
        self.channel_log_file_name = channel_log_file_name
        self.channel_log_file = None
        self.channel_log_timeout = channel_log_timeout
        self.log_recent_channels = []
        self.log_timeout_last = int(time.time())
        self.log_mode = ""
        self.max_demod_length = max_demod_length
        self.min_file_size = min_file_size
        self.low_bound = freq_low
        self.high_bound = freq_high
        self.hang_time = 1.0

        # Create receiver object
        self.receiver = recvr.Receiver(ask_samp_rate, num_demod, type_demod,
                                       hw_args, freq_correction, record, play,
                                       audio_bps,
                                       min_file_size)

        # Set the initial center frequency here to allow setting min/max and low/high bounds
        self.receiver.set_center_freq(center_freq)

        # Open channel log file for appending data, if it is specified
        if channel_log_file_name != "":
            self.channel_log_file = open(channel_log_file_name, 'a')
            if self.channel_log_file != None:
                self.log_mode = "file"
            else:
                # Opening log file failed so cannot perform this log mode
                # Either raise exception or continue without logging, second preferable
                self.log_mode = "none"
                #raise(LogError("file","Cannot open log file"))
        else:
            self.channel_log_file = None

        # Get the hardware sample rate and center frequency in Hz
        self.samp_rate = self.receiver.samp_rate
        self.center_freq = self.receiver.center_freq
        self.min_freq = (self.center_freq - self.samp_rate/2)
        self.max_freq = (self.center_freq + self.samp_rate/2)
        # cannot set channel freq lower than min sampled freq
        if (self.freq_low < self.min_freq):
            self.freq_low = self.min_freq
        # cannot set channel freq higher than max sampled freq
        if (self.freq_high > self.max_freq):
            self.freq_high = self.max_freq
        self.low_bound = self.freq_low - self.center_freq
        self.high_bound = self.freq_high - self.center_freq

        # Start the receiver and wait for samples to accumulate
        self.receiver.start()
        time.sleep(1)

        if self.channel_log_file != None :
           self.channel_log_file.flush()

    def __del__(self):
        if self.channel_log_file != None :
           self.channel_log_file.close()

    def __print_channel_log_active__(self, freq, state):
        if self.log_mode is not None and self.log_mode != "none" and state is True:
            state_str = {True: "act", False: "off"}
            now = datetime.datetime.now()
            if self.log_mode == "file" and self.channel_log_file is not None:
                self.channel_log_file.write(
                        "{}: {:<4}{:>13}{:>7} dB {:>7} dB timeout {:>3}\n".format(
                            now.strftime("%Y-%m-%d, %H:%M:%S.%f"),
                            state_str[state],
                            freq,
                            0,
                            #self.gain_db,
                            self.threshold_db,
                            self.channel_log_timeout))
            elif self.log_mode == "db":
                # write log to db
                raise(err.LogError("db","no db mode implemented"))
            else:
                # cannot log unknown mode
                raise(err.LogError("unknown","no log mode defined"))

    def __print_channel_log__(self, freq, state, idx):
        if self.log_mode is not None and self.log_mode != "none":
            state_str = {True: "on", False: "off"}
            if state == False:
                freq = 0
            now = datetime.datetime.now()
            if self.log_mode == "file" and self.channel_log_file is not None:
                self.channel_log_file.write(
                        "{}: {:<4}{:>13}{:>7} dB {:>7} dB channel {:>3}\n".format(
                            now.strftime("%Y-%m-%d, %H:%M:%S.%f"),
                            state_str[state],
                            freq,
                            0,
                            #self.gain_db,
                            self.threshold_db,
                            idx))
            elif self.log_mode == "db":
                # write log to db
                raise(err.LogError("db","no db mode implemented"))
            else:
                # cannot log unknown mode
                raise(err.LogError("unknown","no log mode defined"))


    def scan_cycle(self):
        """Execute one scan cycle

        Should be called no more than 10 Hz rate
        Estimates channels from FFT power spectrum that are above threshold
        Rounds channels to nearest 5 kHz
        Removes channels that are already a priority
        Moves priority channels in front
        Removes channels that are locked out
        Tunes demodulators to new channels
        Holds demodulators on channels between scan cycles
        Creates RF channel lists for GUI
        """
        # pylint: disable=too-many-branches

        # Grab the FFT data, set threshold, and estimate baseband signal centers for defining channels
        self.spectrum = self.receiver.probe_signal_vf.level()
        threshold = 10**(self.threshold_db/10.0)
        signal_bins = np.array(estimate.channel_estimate(self.spectrum, threshold))

        # Convert detected signal peaks from bin indices to baseband frequency in Hz
        signal_freqs = (signal_bins - len(self.spectrum)/2) * self.samp_rate / len(self.spectrum)

        # keep signal power with each channel for scanner prioritization (close call priority)
        signal_powers = []
        for bindx in range(len(signal_bins)):
            signal_powers.append(self.spectrum[bindx])

        # Round channels to channel spacing
        # Note this affects tuning the demodulators
        # 5000 Hz is adequate for NBFM
        # Note that channel spacing is with respect to the center + baseband offset,
        # not just the offset itself
        
        # TODO should find channels that are less than half channel-spacing away from a provided priority channel
        # and replace with priority channel center rather than fixed spacings
        #signal_channelized = signal_freqs + self.center_freq
        #signal_channelized = np.round(signal_channels / self.channel_spacing) * self.channel_spacing
        #signal_channelized = signal_channels - self.center_freq
        # in baseband
        signal_channels = []
        for fidx in range(len(signal_freqs)):
            signal_channels.append(np.round(signal_freqs[fidx] / self.channel_spacing) * self.channel_spacing)
        #    signal_channels.append((np.round((signal_freqs[fidx] + self.center_freq) / self.channel_spacing) \
        #            + self.channel_spacing) - self.center_freq)

        # set active channels for gui highlight before filtering down lockout or adding priority
        # TODO revisit how gui highlights active vs priority, use tuple to inform channel, pwr, type(priority/continuing/closecall/regular)
        # in baseband
        self.active_channels = signal_channels

        #
        #sys.stderr.write("\n\n ** gothere **\n\n")
        #

        # create list of tuples for bin index, channel frequency, channel power, channel type
        # channel type will be enum (priority, continuing, close, normal)
        # priority = in priority list from file
        # continuing = demod already assigned, signal continues
        # close = power more than YYdb above threshold (this is future revision, nothing done for close currently, YY undefined)
        # new = power above threshold

        channel_type = ["priority", "continuing", "new"]
        channel_type_gui = ["+", " ", "^"]

        # empty list of tuples
        # channels_tuple_key = ("index", "signal frequency channel", "signal power", "spectrum bin")
        # in baseband
        self.unordered_active_channels = []
        for idx in range(len(signal_channels)):
            self.unordered_active_channels.append((idx,signal_channels[idx],signal_powers[idx],signal_bins[idx]))

        self.ordered_active_channels = []

        # Remove channels that are locked out
        # Remove channels that are outside the requested freq range
        for a_chan in self.unordered_active_channels:
            if a_chan[1] in self.lockout_channels or a_chan[1] < self.low_bound or a_chan[1] > self.high_bound:
                self.unordered_active_channels.remove(a_chan)

        # Put the channels in priority order
        # 1 - channels in priority list
        # 2 - channels already being monitored that are still active
        # 3 - new channels in highest power order

        # 1 - channels in the priority list
        # Check active channels for any priority channels
        # Check in priority channel order to insure we select higher 
        # priority channels over lower priority channels per file order
        for a_chan in self.unordered_active_channels:
            if a_chan[1] in self.priority_channels:
                self.ordered_active_channels.append((a_chan[0], a_chan[1], a_chan[2], a_chan[3], channel_type[0], channel_type_gui[0]))
                self.unordered_active_channels.remove(a_chan)

        # 2 - channels already being monitored
        active_demods = [freq for freq in self.receiver.get_demod_freqs() if freq > 0]
        # check on-going signals
        for a_chan in self.unordered_active_channels:
            if a_chan[1] in active_demods:
                self.ordered_active_channels.append((a_chan[0], a_chan[1], a_chan[2], a_chan[3], channel_type[1], channel_type_gui[1]))
                self.unordered_active_channels.remove(a_chan)

        # 3 - new channels in highest power order
        # take remaining unordered channels, get spectrum power for that channel freq, and reorder

        # for sorting the channel tuples by power level, list.sort(reverse=True,key=sortPwr)
        # the sortPwr function returns the third element of the tuple, which is signal power
        
        self.power_ordered_active_channels = sorted(self.unordered_active_channels, key=lambda a: a[1], reverse=True)

        for a_chan in self.power_ordered_active_channels:
            self.ordered_active_channels.append((a_chan[0], a_chan[1], a_chan[2], a_chan[3], channel_type[2], channel_type_gui[2]))
            self.unordered_active_channels.remove(a_chan)
            self.power_ordered_active_channels.remove(a_chan)

        # channels are ordered
        # from this point on we work with ordered_active_channels as channel tuples
        # but a simple list of the ordered frequencies is faster for several operations remaining
        self.ordered_active_channels_freqs = []
        for a_chan in self.ordered_active_channels:
            self.ordered_active_channels_freqs.append(a_chan[1])

        # Update demodulator last heards and expire old ones
        the_now = time.time()
        for idx, demod in enumerate(self.receiver.demodulators):
            if (demod.tuner_freq != 0) and (demod.tuner_freq not in self.ordered_active_channels_freqs):
                if the_now - demod.last_heard > self.hang_time:
                    demod.set_tuner_freq(0, self.center_freq)
            else:
                # maintain active demod
                demod.set_last_heard(the_now)
                # Write in channel log file that the channel is off
                self.__print_channel_log__(demod.tuner_freq + self.center_freq, False, idx)

        # priority relative to this round of assignments only
        demod_priority = [99999] * len(self.receiver.demodulators)

        # mark demodulators already servicing active channels with their relative priority
        # priority is index of ordered channels, lower is better
        active_channel_covered_flags= [False] * len(self.ordered_active_channels)
        for idx, a_chan in enumerate(self.ordered_active_channels):
            for jdx, demod in enumerate(self.receiver.demodulators):
                if demod.tuner_freq == a_chan[1]:
                    demod_priority[jdx] = idx
                    active_channel_covered_flags[idx] = True

        # assign uncovered channels to demodulators in priority order
        # should stop this when reaching the max num of demodulators, do not keep replacing last lowest priority
        # the lowest priority channel that can be serviced will be the max number of demodulators
        num_demod = len(self.receiver.demodulators)
        for idx, a_chan in enumerate(self.ordered_active_channels):
            if not active_channel_covered_flags[idx] and idx <= num_demod:
                # locate lowest prio demod available, with priority lower than current channel priority idx
                # low priority is a high priority value, because ordered channel indexes are used as priorities (1 is highest priority)
                lowest_prio_demod_idx = -1
                lowest_prio_demod_prio = idx
                for kdx, demod in enumerate(self.receiver.demodulators):
                    if demod_priority[kdx] > lowest_prio_demod_prio:
                        lowest_prio_demod_prio = demod_priority[kdx]
                        lowest_prio_demod_idx = kdx
                        lowest_prio_demod = demod

                # if a lower priority demod was found, replace it with current idx ordered channel, else cannot service this channel
                if (lowest_prio_demod_prio > idx):
                    lowest_prio_demod.set_tuner_freq(a_chan[1], self.center_freq)
                    active_channel_covered_flags[idx] = True
                    demod_priority[lowest_prio_demod_idx] = idx
                else:
                    break

        # this resets demodulators to the same frequency when running length is exceeded, which is a file size control
        for demod in self.receiver.demodulators:
                if demod.time_stamp > 0 and \
                      time.time() - demod.time_stamp > \
                      self.max_demod_length:
                    temp_freq = demod.tuner_freq
                    # clear the demod to reset file
                    demod.set_tuner_freq(0, self.center_freq)
                    # reset the demod to its frequency to restart file
                    demod.set_tuner_freq(temp_freq, self.center_freq) 

        # Create tuned channel list of strings for the GUI in MHz
        # If channel is a zero then use an empty string
        self.gui_tuned_channels = []
        for demod_freq in self.receiver.get_demod_freqs():
            if demod_freq == 0:
                text = ""
            else:
                # Calculate actual RF frequency in MHz
                gui_tuned_channel = (demod_freq + self.center_freq)/1E6
                text = '{:.3f}'.format(gui_tuned_channel)
            self.gui_tuned_channels.append(text)

        # Should there be a priority active channel list for GUI? could display other color when priority channel is active versus normal active

        # Create active channel list of strings for the GUI in MHz
        # This is any channel above threshold
        # do not include priority if not above threshold
        # do include lockout if above threshold, this would highlight the active lockout freq for visual info only
        self.gui_active_channels = []
        for channel in self.active_channels:
            # calculate active channel freq in MHz
            gui_active_channel = (channel + self.center_freq)/1E6
            text = '{:.3f}'.format(gui_active_channel)
            self.gui_active_channels.append(text)
            # Add active channel to recent list for logging if not already there
            if gui_active_channel not in self.log_recent_channels:
                self.log_recent_channels.append(gui_active_channel)

        # log recently active channels if we are beyond timeout delay from last logging
        # clear list of recently active channels after logging
        # reset timeout (a low fidelity/effort timer)
        cur_timestamp = int(time.time())
        # if cur_timestamp > timeout_timestamp + timeout
        if cur_timestamp > (self.log_timeout_last + self.channel_log_timeout):
            # set last timeout to this timestamp
            self.log_timeout_last = cur_timestamp
            # iterate all recent channels print to log
            for channel in self.log_recent_channels:
                # Write in channel log file that the channel is on
                self.__print_channel_log_active__(float(channel)*1E6, True)
            # clear recent channels
            self.log_recent_channels = []



    def add_lockout(self, idx):
        """Adds baseband frequency to lockout channels and updates GUI list

        Args:
            idx (int): Index of tuned channel
        """
        # Check to make sure index is within the number of demodulators
        if idx < len(self.receiver.demodulators):
            # Lockout if not zero and not already locked out
            demod_freq = self.receiver.demodulators[idx].tuner_freq
            if (demod_freq != 0) and (demod_freq not in self.lockout_channels):
                self.lockout_channels = np.append(self.lockout_channels,
                                                  demod_freq)

        # Retune demodulators that are locked out
        for demod in self.receiver.demodulators:
            if demod.tuner_freq in self.lockout_channels:
                demod.set_tuner_freq(0, self.center_freq)
            else:
                pass

        # Create a lockout channel list of strings for the GUI in MHz
        self.gui_lockout_channels = []
        for lockout_channel in self.lockout_channels:
            # lockout channel in MHz
            gui_lockout_channel = (lockout_channel + \
                                    self.receiver.center_freq)/1E6
            text = '{:.3f}'.format(gui_lockout_channel)
            self.gui_lockout_channels.append(text)

    def clear_lockout(self):
        """Clears lockout channels and updates GUI list
        """
        # Clear the lockout channels
        self.lockout_channels = []

        # Process lockout file if it was provided
        if self.lockout_file_name != "":
            # Open file, split to list, remove empty strings
            with open(self.lockout_file_name) as lockout_file:
                lines = lockout_file.read().splitlines()
                lockout_file.close()
                if PY3:
                    lines = builtins.filter(None, lines)
                else:
                    lines = __builtin__.filter(None, lines)
            # Convert to baseband frequencies, round, and append
            for freq in lines:
                bb_freq = float(freq) - self.center_freq
                bb_freq = round(bb_freq/self.channel_spacing)*\
                                        self.channel_spacing
                self.lockout_channels.append(bb_freq)
        else:
            pass

        # Create a lockout channel list of strings for the GUI in MHz
        self.gui_lockout_channels = []
        for lockout_channel in self.lockout_channels:
            # lockout channel in MHz
            gui_lockout_channel = (lockout_channel + \
                                    self.receiver.center_freq)/1E6
            text = '{:.3f}'.format(gui_lockout_channel)
            self.gui_lockout_channels.append(text)

    def update_priority(self):
        """Updates priority channels
        """
        # Clear the priority channels
        self.priority_channels = []

        # Process priority file if it was provided
        if self.priority_file_name != "":
            # Open file, split to list, remove empty strings
            with open(self.priority_file_name) as priority_file:
                lines = priority_file.read().splitlines()
                priority_file.close()
                if PY3:
                    lines = builtins.filter(None, lines)
                else:
                    lines = __builtin__.filter(None, lines)

            # Convert to baseband frequencies, round, and append if within BW
            for freq in lines:
                bb_freq = float(freq) - self.center_freq
                bb_freq = round(bb_freq/self.channel_spacing)*\
                                        self.channel_spacing
                if abs(bb_freq) <= self.samp_rate/2.0:
                    self.priority_channels.append(bb_freq)
                else:
                    pass
        else:
            pass

    def set_center_freq(self, center_freq):
        """Sets RF center frequency of hardware and clears lockout channels
           Sets low and high demod frequency limits based on provided bounds in command line

        Args:
            center_freq (float): Hardware RF center frequency in Hz
        """
        # Tune the receiver then update with actual frequency
        self.receiver.set_center_freq(center_freq)
        self.center_freq = self.receiver.center_freq

        # reset min/max based on sample rate
        self.min_freq = (self.center_freq - self.samp_rate/2)
        self.max_freq = (self.center_freq + self.samp_rate/2)
        # reset low/high freq for demod based on new center and bounds from original provided
        self.freq_low = self.low_bound + self.center_freq
        self.freq_high = self.high_bound + self.center_freq
        # cannot set channel freq lower than min sampled freq
        if (self.freq_low < self.min_freq):
            self.freq_low = self.min_freq
        # cannot set channel freq higher than max sampled freq
        if (self.freq_high > self.max_freq):
            self.freq_high = self.max_freq

        # Update the priority since frequency is changing
        self.update_priority()

        # Clear the lockout since frequency is changing
        self.clear_lockout()

    def filter_and_set_gains(self, all_gains):
        """Set the supported gains and return them

        Args:
            all_gains (list of dictionary): Supported gains in dB
        """
        self.gains = self.receiver.filter_and_set_gains(all_gains)
        return self.gains

    def set_squelch(self, squelch_db):
        """Sets squelch of all demodulators

        Args:
            squelch_db (float): Squelch in dB
        """
        self.receiver.set_squelch(squelch_db)
        self.squelch_db = self.receiver.squelch_db

    def set_volume(self, volume_db):
        """Sets volume of all demodulators

        Args:
            volume_db (float): Volume in dB
        """
        self.receiver.set_volume(volume_db)
        self.volume_db = self.receiver.volume_db

    def set_threshold(self, threshold_db):
        """Sets threshold in dB for channel detection

        Args:
            threshold_db (float): Threshold in dB
        """
        self.threshold_db = threshold_db

    def stop(self):
        """Stop the receiver
        """
        self.receiver.stop()
        self.receiver.wait()


def main():
    """Test the scanner

    Gets options from parser
    Sets up the scanner
    Assigns a channel to lockout
    Executes scan cycles
    Prints channels as they change
    """

    # Create parser object
    parser = prsr.CLParser()

    if len(parser.parser_args) != 0:
        parser.print_help() #pylint: disable=maybe-no-member
        raise(SystemExit, 1)

    # Create scanner object
    ask_samp_rate = parser.ask_samp_rate
    num_demod = parser.num_demod
    type_demod = parser.type_demod
    hw_args = parser.hw_args
    freq_correction = parser.freq_correction
    record = parser.record
    lockout_file_name = parser.lockout_file_name
    priority_file_name = parser.priority_file_name
    channel_log_file_name = parser.channel_log_file_name
    audio_bps = parser.audio_bps
    max_demod_length = parser.max_demod_length
    channel_spacing = parser.channel_spacing
    min_file_size = parser.min_file_size
    center_freq = parser.center_freq
    freq_low = parser.freq_low
    freq_high = parser.freq_high
    scanner = Scanner(ask_samp_rate, num_demod, type_demod, hw_args,
                      freq_correction, record, lockout_file_name,
                      priority_file_name, channel_log_file_name,
                      audio_bps, max_demod_length, channel_spacing,
                      min_file_size, center_freq, freq_low, freq_high)

    # Set frequency, gain, squelch, and volume
    scanner.set_center_freq(center_freq)
    print("\n")
    print("Started %s at %.3f Msps" % (hw_args, scanner.samp_rate/1E6))
    print("RX at %.3f MHz" % (scanner.center_freq/1E6))
    scanner.filter_and_set_gains(parser.gains)
    for gain in scanner.gains:
        print("gain %s at %d dB" % (gain["name"], gain["value"]))
    scanner.set_squelch(parser.squelch_db)
    scanner.set_volume(parser.volume_db)
    print("%d demods of type %d at %d dB squelch and %d dB volume" % \
        (num_demod, type_demod, scanner.squelch_db, scanner.volume_db))

    # Create this epmty list to allow printing to screen
    old_gui_tuned_channels = []

    while 1:
        # No need to go faster than 10 Hz rate of GNU Radio probe
        time.sleep(0.1)

        # Execute a scan cycle
        scanner.scan_cycle()

        # Print the GUI tuned channels if they have changed
        if scanner.gui_tuned_channels != old_gui_tuned_channels:
            sys.stdout.write("Tuners at: ")
            for text in scanner.gui_tuned_channels:
                sys.stdout.write(text + " ")
            sys.stdout.write("\n")
        else:
            pass
        old_gui_tuned_channels = scanner.gui_tuned_channels


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
