#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Fri Jul  3 13:38:36 2015

@author: madengr
"""
try:
    import builtins
except:
    import __builtin__
import receiver as recvr
import estimate
import parser as prsr
import time
import numpy as np
import sys

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
        audio_bps (int): Audio bit depth in bps (bits/samples)

    Attributes:
        center_freq (float): Hardware RF center frequency in Hz
        samp_rate (float): Hardware sample rate in sps (1E6 min)
        gain_db (int): Hardware RF gain in dB
        squelch_db (int): Squelch in dB
        volume_dB (int): Volume in dB
        threshold_dB (int): Threshold for channel detection in dB
        spectrum (numpy.ndarray): FFT power spectrum data in linear, not dB
        lockout_channels [float]: List of baseband lockout channels in Hz
        priority_channels [float]: List of baseband priority channels in Hz
        gui_tuned_channels [str] List of tuned RF channels in MHz for GUI
        gui_tuned_lockout_channels [str]: List of lockout channels in MHz GUI
        channel_spacing (float):  Spacing that channels will be rounded
        lockout_file_name (string): Name of file with channels to lockout
        priority_file_name (string): Name of file with channels for priority
    """
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments

    def __init__(self, ask_samp_rate=4E6, num_demod=4, type_demod=0,
                 hw_args="uhd", freq_correction=0, record=True,
                 lockout_file_name="", priority_file_name="", play=True,
                 audio_bps=8):

        # Default values
        self.gain_db = 0
        self.if_gain_db = 16
        self.bb_gain_db = 16
        self.squelch_db = -60
        self.volume_db = 0
        self.threshold_db = 10
        self.record = record
        self.play = play
        self.spectrum = []
        self.lockout_channels = []
        self.priority_channels = []
        self.gui_tuned_channels = []
        self.gui_lockout_channels = []
        self.channel_spacing = 5000
        self.lockout_file_name = lockout_file_name
        self.priority_file_name = priority_file_name

        # Create receiver object
        self.receiver = recvr.Receiver(ask_samp_rate, num_demod, type_demod,
                                       hw_args, freq_correction, record, play,
                                       audio_bps)

        # Get the hardware sample rate and center frequency
        self.samp_rate = self.receiver.samp_rate
        self.center_freq = self.receiver.center_freq

        # Start the receiver and wait for samples to accumulate
        self.receiver.start()
        time.sleep(1)

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

        # Retune demodulators that are locked out
        for demodulator in self.receiver.demodulators:
            if demodulator.center_freq in self.lockout_channels:
                demodulator.set_center_freq(0, self.center_freq)
            else:
                pass

        # Grab the FFT data, set threshold, and estimate baseband channels
        self.spectrum = self.receiver.probe_signal_vf.level()
        threshold = 10**(self.threshold_db/10.0)
        channels = np.array(estimate.channel_estimate(self.spectrum,
                                                      threshold))

        # Convert channels from bin indices to baseband frequency in Hz
        channels = (channels-len(self.spectrum)/2)*\
            self.samp_rate/len(self.spectrum)

        # Round channels to channel spacing
        # Note this affects tuning the demodulators
        # 5000 Hz is adequate for NBFM
        channels = np.round(channels / self.channel_spacing) * self.channel_spacing

        # Remove channels that are already in the priority list
        temp = []
        for channel in channels:
            if channel not in self.priority_channels:
                temp = np.append(temp, channel)
            else:
                pass
        channels = temp

        # Put the priority channels in front
        channels = np.append(self.priority_channels, channels)

        # Remove channels that are locked out
        temp = []
        for channel in channels:
            if channel not in self.lockout_channels:
                temp = np.append(temp, channel)
            else:
                pass
        channels = temp

        # Set demodulators that are no longer in channel list to 0 Hz
        for demodulator in self.receiver.demodulators:
            if demodulator.center_freq not in channels:
                demodulator.set_center_freq(0, self.center_freq)
            else:
                pass

        # Add new channels to demodulators
        for channel in channels:
            # If channel not in demodulators
            if channel not in self.receiver.get_demod_freqs():
                # Sequence through each demodulator
                for demodulator in self.receiver.demodulators:
                    # If demodulator is empty and channel not already there
                    if (demodulator.center_freq == 0) and \
                            (channel not in self.receiver.get_demod_freqs()):
                        # Assing channel to empty demodulator
                        demodulator.set_center_freq(channel, self.center_freq)
                    else:
                        pass
            else:
                pass

        # Create an tuned channel list of strings for the GUI
        # If channel is a zero then use an empty string
        self.gui_tuned_channels = []
        for demod_freq in self.receiver.get_demod_freqs():
            if demod_freq == 0:
                text = ""
            else:
                # Calculate actual RF frequency
                gui_tuned_channel = (demod_freq + \
                                    self.center_freq)/1E6
                text = '{:.3f}'.format(gui_tuned_channel)
            self.gui_tuned_channels.append(text)

    def add_lockout(self, idx):
        """Adds baseband frequency to lockout channels and updates GUI list

        Args:
            idx (int): Index of tuned channel
        """
        # Check to make sure index is within the number of demodulators
        if idx < len(self.receiver.demodulators):
            # Lockout if not zero and not already locked out
            demod_freq = self.receiver.demodulators[idx].center_freq
            if (demod_freq != 0) and (demod_freq not in self.lockout_channels):
                self.lockout_channels = np.append(self.lockout_channels,
                                                  demod_freq)

        # Create a lockout channel list of strings for the GUI
        self.gui_lockout_channels = []
        for lockout_channel in self.lockout_channels:
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
                lines = __builtin__.filter(None, lines)
            # Convert to baseband frequencies, round, and append
            for freq in lines:
                bb_freq = float(freq) - self.center_freq
                bb_freq = round(bb_freq/self.channel_spacing)*\
                                        self.channel_spacing
                self.lockout_channels.append(bb_freq)
        else:
            pass

        # Create a lockout channel list of strings for the GUI
        self.gui_lockout_channels = []
        for lockout_channel in self.lockout_channels:
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

        Args:
            center_freq (float): Hardware RF center frequency in Hz
        """
        # Tune the receiver then update with actual frequency
        self.receiver.set_center_freq(center_freq)
        self.center_freq = self.receiver.center_freq

        # Update the priority since frequency is changing
        self.update_priority()

        # Clear the lockout since frequency is changing
        self.clear_lockout()

    def set_gain(self, gain_db):
        """Sets gain of RF hardware

        Args:
            gain_db (float): Hardware RF gain in dB
        """
        self.receiver.set_gain(gain_db)
        self.gain_db = self.receiver.gain_db

    def set_if_gain(self, if_gain_db):
        """Sets IF gain of RF hardware

        Args:
            if_gain_db (float): Hardware IF gain in dB
        """
        self.receiver.set_if_gain(if_gain_db)
        self.if_gain_db = self.receiver.if_gain_db

    def set_bb_gain(self, bb_gain_db):
        """Sets BB gain of RF hardware

        Args:
            bb_gain_db (float): Hardware BB gain in dB
        """
        self.receiver.set_bb_gain(bb_gain_db)
        self.bb_gain_db = self.receiver.bb_gain_db

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
    audio_bps = parser.audio_bps
    scanner = Scanner(ask_samp_rate, num_demod, type_demod, hw_args,
                      freq_correction, record, lockout_file_name,
                      priority_file_name, audio_bps)

    # Set frequency, gain, squelch, and volume
    scanner.set_center_freq(parser.center_freq)
    scanner.set_gain(parser.gain_db)
    scanner.set_if_gain(parser.if_gain_db)
    scanner.set_bb_gain(parser.bb_gain_db)
    print("\n")
    print("Started %s at %.3f Msps" % (hw_args, scanner.samp_rate/1E6))
    print("RX at %.3f MHz with %d dB gain" % (scanner.center_freq/1E6,
                                              scanner.gain_db))
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
